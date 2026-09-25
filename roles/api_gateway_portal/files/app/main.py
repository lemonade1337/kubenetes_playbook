import os
import secrets
import logging
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, Request, Response, Depends, Form, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func

from database import engine, get_db, init_database_and_seed
from models import User, UserBalance, ApiKey, UsageLog, SystemSetting
from schemas import (
    UserOut, ApiKeyOut, GenerateApiKeyRequest, AddTokensRequest,
    SetMonthlyQuotaRequest, ResetBalancesRequest, ChatCompletionRequest
)
from auth import (
    authenticate_with_keycloak, get_current_user_from_session,
    require_admin, KEYCLOAK_URL, KEYCLOAK_REALM, KEYCLOAK_CLIENT_ID
)
from proxy import (
    validate_api_key_and_get_user, proxy_chat_completion,
    get_active_requests_count, TARGET_MODEL, QWEN_BACKEND_URL
)
from tracing import init_tracing

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("gateway.main")

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing Token Management Gateway and verifying Database...")
    try:
        init_database_and_seed()
    except Exception as e:
        logger.warning(f"Database initialization deferred: {e}")
    yield
    logger.info("Gateway shutting down.")

app = FastAPI(
    title="API Gateway Portal",
    version="1.0.0",
    lifespan=lifespan
)

# Initialize OpenTelemetry distributed tracing to Jaeger
init_tracing(app, engine)

# Static and Templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# ==============================================================================
# Health & Metrics Endpoints
# ==============================================================================
@app.get("/healthz")
@app.get("/ready")
def health_check():
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}

@app.get("/metrics")
def prometheus_metrics(db: Session = Depends(get_db)):
    """Prometheus-compatible metrics endpoint for autoscaling and monitoring."""
    active_reqs = get_active_requests_count()
    total_tokens = db.query(func.sum(UsageLog.total_tokens)).scalar() or 0
    total_users = db.query(User).count()

    metrics = [
        "# HELP qwen_active_requests Number of in-flight LLM requests currently being processed",
        "# TYPE qwen_active_requests gauge",
        f"qwen_active_requests {active_reqs}",
        "# HELP llm_tokens_consumed_total Total LLM tokens consumed across all users",
        "# TYPE llm_tokens_consumed_total counter",
        f"llm_tokens_consumed_total {total_tokens}",
        "# HELP llm_registered_users_total Total registered users on the platform",
        "# TYPE llm_registered_users_total gauge",
        f"llm_registered_users_total {total_users}"
    ]
    return PlainTextResponse("\n".join(metrics) + "\n", media_type="text/plain; version=0.0.4")

# ==============================================================================
# Web UI Routes
# ==============================================================================
@app.get("/", response_class=HTMLResponse)
def index(request: Request, db: Session = Depends(get_db)):
    try:
        user = get_current_user_from_session(request, db)
        return RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)
    except HTTPException:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)

@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    keycloak_auth_url = f"{KEYCLOAK_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/auth?client_id={KEYCLOAK_CLIENT_ID}&response_type=code&scope=openid%20profile%20email"
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={
            "keycloak_url": keycloak_auth_url,
            "error": None
        }
    )

@app.post("/login", response_class=HTMLResponse)
async def login_post(
    request: Request,
    response: Response,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    # 1. Attempt Keycloak direct authentication
    kc_token = await authenticate_with_keycloak(username, password)
    
    # 2. Fallback check in local DB if Keycloak is still starting or for demo credentials
    user = db.query(User).filter_by(username=username).first()
    
    valid = False
    if kc_token:
        valid = True
    elif user and (
        (username == "admin" and password == "AdminPass123!") or
        (username == "user1" and password == "User1Pass123!") or
        (username == "user2" and password == "User2Pass123!") or
        (username == "user3" and password == "User3Pass123!")
    ):
        valid = True

    if not valid:
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={
                "error": "Invalid username or password. Please try again.",
                "keycloak_url": f"{KEYCLOAK_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/auth"
            },
            status_code=401
        )

    # Set session cookie
    redirect_resp = RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)
    redirect_resp.set_cookie(key="username", value=username, httponly=True, max_age=86400, samesite="lax")
    if kc_token and "access_token" in kc_token:
        redirect_resp.set_cookie(key="session_token", value=kc_token["access_token"], httponly=True, max_age=86400, samesite="lax")

    return redirect_resp

@app.get("/logout")
def logout():
    response = RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    response.delete_cookie("username")
    response.delete_cookie("session_token")
    return response

@app.get("/dashboard", response_class=HTMLResponse)
def user_dashboard(request: Request, db: Session = Depends(get_db)):
    try:
        user = get_current_user_from_session(request, db)
    except HTTPException:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)

    balance = user.balance or UserBalance(remaining_tokens=100000, monthly_quota=100000, total_consumed=0)
    api_keys = db.query(ApiKey).filter_by(user_id=user.id, is_active=True).all()
    primary_key = api_keys[0].api_key if api_keys else "No active key"

    # Recent usage logs
    logs = db.query(UsageLog).filter_by(user_id=user.id).order_by(UsageLog.created_at.desc()).limit(15).all()

    # Determine public host URL for snippet generation
    host_header = request.headers.get("host", "localhost")
    api_base_url = f"http://{host_header}"

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "user": user,
            "balance": balance,
            "api_keys": api_keys,
            "primary_key": primary_key,
            "logs": logs,
            "api_base_url": api_base_url,
            "model_name": TARGET_MODEL
        }
    )

@app.get("/admin", response_class=HTMLResponse)
def admin_dashboard(request: Request, db: Session = Depends(get_db)):
    try:
        user = get_current_user_from_session(request, db)
        if user.role != "admin" and user.username != "admin":
            return RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)
    except HTTPException:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)

    users = db.query(User).all()
    setting = db.query(SystemSetting).filter_by(key="default_monthly_quota").first()
    monthly_quota = int(setting.value) if setting else 100000

    total_tokens_consumed = db.query(func.sum(UsageLog.total_tokens)).scalar() or 0
    total_active_keys = db.query(ApiKey).filter_by(is_active=True).count()

    return templates.TemplateResponse(
        request=request,
        name="admin.html",
        context={
            "user": user,
            "users": users,
            "monthly_quota": monthly_quota,
            "total_tokens_consumed": total_tokens_consumed,
            "total_active_keys": total_active_keys,
            "active_qwen_requests": get_active_requests_count(),
            "model_name": TARGET_MODEL
        }
    )

# ==============================================================================
# User REST API Endpoints
# ==============================================================================
@app.get("/api/user/me")
def api_get_me(request: Request, db: Session = Depends(get_db)):
    user = get_current_user_from_session(request, db)
    balance = user.balance
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "role": user.role,
        "remaining_tokens": balance.remaining_tokens if balance else 0,
        "monthly_quota": balance.monthly_quota if balance else 100000,
        "total_consumed": balance.total_consumed if balance else 0
    }

@app.post("/api/user/keys")
def api_generate_key(
    req: GenerateApiKeyRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    user = get_current_user_from_session(request, db)
    new_raw_key = f"sk-{secrets.token_urlsafe(28)}"
    key_obj = ApiKey(
        user_id=user.id,
        api_key=new_raw_key,
        name=req.name or "API Key",
        is_active=True,
        created_at=datetime.now(timezone.utc)
    )
    db.add(key_obj)
    db.commit()
    db.refresh(key_obj)
    return {"id": key_obj.id, "name": key_obj.name, "api_key": key_obj.api_key, "created_at": key_obj.created_at}

@app.delete("/api/user/keys/{key_id}")
def api_revoke_key(
    key_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    user = get_current_user_from_session(request, db)
    key_obj = db.query(ApiKey).filter_by(id=key_id, user_id=user.id).first()
    if not key_obj:
        raise HTTPException(status_code=404, detail="Key not found")
    key_obj.is_active = False
    db.commit()
    return {"message": "Key revoked successfully"}

@app.post("/api/user/chat")
async def api_user_web_chat(
    req: ChatCompletionRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """Interactive Web Chat endpoint authenticated via user session."""
    user = get_current_user_from_session(request, db)
    if not user or not user.balance:
        raise HTTPException(status_code=400, detail="User account or balance record missing")
    if user.balance.remaining_tokens <= 0:
        raise HTTPException(
            status_code=402,
            detail="Token balance exhausted (0 remaining). Please contact an administrator to add tokens."
        )

    payload = {
        "model": req.model or TARGET_MODEL,
        "messages": [m.model_dump() for m in req.messages],
        "temperature": req.temperature if req.temperature is not None else 0.7,
        "max_tokens": req.max_tokens if req.max_tokens is not None else 1024,
        "stream": False
    }

    return await proxy_chat_completion(request, payload, user, db)

# ==============================================================================
# Admin REST API Endpoints
# ==============================================================================
@app.get("/api/admin/users")
def api_admin_list_users(
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    users = db.query(User).all()
    results = []
    for u in users:
        bal = u.balance
        keys = [k.api_key for k in u.api_keys if k.is_active]
        results.append({
            "id": u.id,
            "username": u.username,
            "email": u.email,
            "role": u.role,
            "remaining_tokens": bal.remaining_tokens if bal else 0,
            "monthly_quota": bal.monthly_quota if bal else 100000,
            "total_consumed": bal.total_consumed if bal else 0,
            "api_keys": keys,
            "created_at": u.created_at
        })
    return results

@app.post("/api/admin/tokens/add")
def api_admin_add_tokens(
    req: AddTokensRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    balance = db.query(UserBalance).filter_by(user_id=req.user_id).first()
    if not balance:
        raise HTTPException(status_code=404, detail="User balance record not found")

    balance.remaining_tokens += req.amount
    balance.updated_at = datetime.now(timezone.utc)
    db.commit()
    return {
        "message": f"Successfully credited {req.amount:,} tokens.",
        "user_id": req.user_id,
        "new_balance": balance.remaining_tokens
    }

@app.post("/api/admin/quota/set")
def api_admin_set_quota(
    req: SetMonthlyQuotaRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    setting = db.query(SystemSetting).filter_by(key="default_monthly_quota").first()
    if not setting:
        setting = SystemSetting(key="default_monthly_quota", value=str(req.quota))
        db.add(setting)
    else:
        setting.value = str(req.quota)
        setting.updated_at = datetime.now(timezone.utc)

    if req.apply_to_existing_users:
        db.query(UserBalance).update({"monthly_quota": req.quota})

    db.commit()
    return {
        "message": f"Default monthly quota updated to {req.quota:,} tokens.",
        "new_quota": req.quota
    }

@app.post("/api/admin/balances/reset")
def api_admin_reset_balances(
    req: ResetBalancesRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    balances = db.query(UserBalance).all()
    for b in balances:
        b.remaining_tokens = b.monthly_quota
        b.last_reset_at = datetime.now(timezone.utc)
        b.updated_at = datetime.now(timezone.utc)
    db.commit()
    return {"message": "All user balances reset to their monthly quotas."}

# ==============================================================================
# OpenAI-Compatible Qwen 2.5 3B API Proxy Routes
# ==============================================================================
@app.get("/v1/models")
def list_models():
    """OpenAI standard models endpoint."""
    return {
        "object": "list",
        "data": [
            {
                "id": TARGET_MODEL,
                "object": "model",
                "created": 1700000000,
                "owned_by": "qwen-kubernetes-platform",
                "permission": [],
                "root": TARGET_MODEL,
                "parent": None
            }
        ]
    }

@app.post("/v1/chat/completions")
async def chat_completions(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    OpenAI-compatible Chat Completion proxy to Qwen 2.5 3B.
    Validates API key, checks & deducts token balance, and proxies to Kubernetes backend.
    """
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail={"error": {"message": "Missing Bearer API Key", "type": "auth_error"}}
        )
    api_key = auth_header.replace("Bearer ", "").strip()
    user = validate_api_key_and_get_user(db, api_key)

    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail={"error": {"message": "Invalid JSON body", "type": "bad_request"}})

    return await proxy_chat_completion(request, body, user, db)

@app.post("/v1/completions")
async def text_completions(
    request: Request,
    db: Session = Depends(get_db)
):
    """OpenAI-compatible Text Completion proxy."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail={"error": {"message": "Missing Bearer API Key"}})
    api_key = auth_header.replace("Bearer ", "").strip()
    user = validate_api_key_and_get_user(db, api_key)

    body = await request.json()
    # Map prompt to messages for chat format
    prompt = body.get("prompt", "")
    body["messages"] = [{"role": "user", "content": prompt}]
    return await proxy_chat_completion(request, body, user, db)
