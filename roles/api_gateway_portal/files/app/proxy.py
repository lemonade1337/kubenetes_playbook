import os
import json
import httpx
import logging
import asyncio
from datetime import datetime, timezone
from typing import Optional, Dict, Any, AsyncGenerator
from fastapi import Request, HTTPException, status
from fastapi.responses import StreamingResponse, JSONResponse
from sqlalchemy.orm import Session
from models import User, UserBalance, ApiKey, UsageLog
from tracing import get_current_span

logger = logging.getLogger("gateway.proxy")

QWEN_BACKEND_URL = os.getenv("QWEN_BACKEND_URL", "http://qwen-llm-service:11434")
TARGET_MODEL = os.getenv("QWEN_MODEL_NAME", "qwen2.5:3b")

# Active concurrent request tracking (in-flight requests)
ACTIVE_CONCURRENT_REQUESTS = 0
active_requests_lock = asyncio.Lock()

async def increment_active_requests():
    global ACTIVE_CONCURRENT_REQUESTS
    async with active_requests_lock:
        ACTIVE_CONCURRENT_REQUESTS += 1

async def decrement_active_requests():
    global ACTIVE_CONCURRENT_REQUESTS
    async with active_requests_lock:
        ACTIVE_CONCURRENT_REQUESTS = max(0, ACTIVE_CONCURRENT_REQUESTS - 1)

def get_active_requests_count():
    return ACTIVE_CONCURRENT_REQUESTS

def validate_api_key_and_get_user(db: Session, raw_key: str) -> User:
    """Verify API key and retrieve user with balance check."""
    if not raw_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"message": "Missing API Key. Include 'Authorization: Bearer YOUR_API_KEY'", "type": "invalid_request_error"}}
        )

    api_key_obj = db.query(ApiKey).filter_by(api_key=raw_key, is_active=True).first()
    if not api_key_obj:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"message": "Invalid or revoked API key", "type": "invalid_api_key"}}
        )

    # Update last used timestamp
    api_key_obj.last_used_at = datetime.now(timezone.utc)
    db.commit()

    user = api_key_obj.user
    if not user or not user.balance:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"message": "User account or balance record missing", "type": "account_error"}}
        )

    if user.balance.remaining_tokens <= 0:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={
                "error": {
                    "message": f"Token balance exhausted. Current balance: {user.balance.remaining_tokens}. Please contact administrator.",
                    "type": "insufficient_quota",
                    "code": "quota_exceeded"
                }
            }
        )

    return user

def deduct_user_tokens(db: Session, user_id: int, prompt_tokens: int, completion_tokens: int, model: str, endpoint: str):
    """Atomically deduct tokens from user balance and write usage log."""
    total_tokens = prompt_tokens + completion_tokens
    if total_tokens <= 0:
        total_tokens = 1 # Minimum 1 token charge per request

    try:
        balance = db.query(UserBalance).filter_by(user_id=user_id).with_for_update().first()
        if balance:
            balance.remaining_tokens = max(0, balance.remaining_tokens - total_tokens)
            balance.total_consumed += total_tokens
            balance.updated_at = datetime.now(timezone.utc)

            log_entry = UsageLog(
                user_id=user_id,
                model=model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                endpoint=endpoint,
                status_code=200,
                created_at=datetime.now(timezone.utc)
            )
            db.add(log_entry)
            db.commit()
            logger.info(f"User ID {user_id} consumed {total_tokens} tokens. Remaining: {balance.remaining_tokens}")
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to deduct tokens for user {user_id}: {e}")

async def proxy_chat_completion(
    request: Request,
    payload: Dict[str, Any],
    user: User,
    db: Session
):
    """Proxy OpenAI-compatible chat completion to Qwen 2.5 3B backend."""
    # Ensure model is set to Qwen 2.5 3B
    payload["model"] = TARGET_MODEL

    stream = payload.get("stream", False)
    backend_url = f"{QWEN_BACKEND_URL}/v1/chat/completions"

    await increment_active_requests()
    span = get_current_span()
    if span and hasattr(span, "is_recording") and span.is_recording():
        span.set_attribute("llm.user_id", user.id)
        span.set_attribute("llm.username", user.username)
        span.set_attribute("llm.model", TARGET_MODEL)
        span.set_attribute("llm.stream", stream)

    try:
        timeout = httpx.Timeout(connect=10.0, read=300.0, write=10.0, pool=10.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            if not stream:
                # Non-streaming request
                resp = await client.post(backend_url, json=payload)
                if resp.status_code != 200:
                    return JSONResponse(status_code=resp.status_code, content=resp.json() if "application/json" in resp.headers.get("content-type", "") else {"error": resp.text})

                data = resp.json()
                usage = data.get("usage", {})
                prompt_tokens = usage.get("prompt_tokens", 0)
                completion_tokens = usage.get("completion_tokens", 0)
                total_tokens = usage.get("total_tokens", prompt_tokens + completion_tokens)

                # Fallback estimation if engine didn't include usage numbers
                if total_tokens == 0:
                    req_text = json.dumps(payload.get("messages", []))
                    resp_text = json.dumps(data.get("choices", []))
                    prompt_tokens = max(1, len(req_text) // 4)
                    completion_tokens = max(1, len(resp_text) // 4)
                    total_tokens = prompt_tokens + completion_tokens
                    data["usage"] = {
                        "prompt_tokens": prompt_tokens,
                        "completion_tokens": completion_tokens,
                        "total_tokens": total_tokens
                    }

                if span and hasattr(span, "is_recording") and span.is_recording():
                    span.set_attribute("llm.prompt_tokens", prompt_tokens)
                    span.set_attribute("llm.completion_tokens", completion_tokens)
                    span.set_attribute("llm.total_tokens", total_tokens)

                deduct_user_tokens(db, user.id, prompt_tokens, completion_tokens, TARGET_MODEL, "/v1/chat/completions")
                return JSONResponse(content=data)

            else:
                # Streaming response
                async def stream_generator():
                    token_count = 0
                    prompt_len = len(json.dumps(payload.get("messages", []))) // 4
                    try:
                        async with client.stream("POST", backend_url, json=payload) as response:
                            async for chunk in response.aiter_text():
                                if chunk:
                                    token_count += 1
                                    yield chunk
                    finally:
                        completion_tokens = max(1, token_count // 3)
                        prompt_tokens = max(1, prompt_len)
                        total_tokens = prompt_tokens + completion_tokens
                        if span and hasattr(span, "is_recording") and span.is_recording():
                            span.set_attribute("llm.prompt_tokens", prompt_tokens)
                            span.set_attribute("llm.completion_tokens", completion_tokens)
                            span.set_attribute("llm.total_tokens", total_tokens)
                        deduct_user_tokens(db, user.id, prompt_tokens, completion_tokens, TARGET_MODEL, "/v1/chat/completions")

                return StreamingResponse(stream_generator(), media_type="text/event-stream")

    finally:
        await decrement_active_requests()
