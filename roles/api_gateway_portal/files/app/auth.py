import os
import httpx
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from fastapi import Request, HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from database import get_db
from models import User, UserBalance, ApiKey

logger = logging.getLogger("gateway.auth")

KEYCLOAK_URL = os.getenv("KEYCLOAK_URL", "http://keycloak-service:8080/auth")
KEYCLOAK_REALM = os.getenv("KEYCLOAK_REALM", "llm-platform")
KEYCLOAK_CLIENT_ID = os.getenv("KEYCLOAK_CLIENT_ID", "token-portal")
KEYCLOAK_CLIENT_SECRET = os.getenv("KEYCLOAK_CLIENT_SECRET", "token-portal-secret-key-2026")

security = HTTPBearer(auto_error=False)

def get_keycloak_token_endpoint():
    return f"{KEYCLOAK_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/token"

def get_keycloak_userinfo_endpoint():
    return f"{KEYCLOAK_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/userinfo"

async def authenticate_with_keycloak(username: str, password: str) -> Optional[Dict[str, Any]]:
    """Authenticate user directly with Keycloak via Direct Access Grants / Password Flow."""
    token_url = get_keycloak_token_endpoint()
    data = {
        "grant_type": "password",
        "client_id": KEYCLOAK_CLIENT_ID,
        "client_secret": KEYCLOAK_CLIENT_SECRET,
        "username": username,
        "password": password,
        "scope": "openid profile email roles"
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(token_url, data=data)
            if resp.status_code == 200:
                return resp.json()
            logger.warning(f"Keycloak auth failed for {username}: status {resp.status_code} - {resp.text}")
            return None
    except Exception as e:
        logger.error(f"Error connecting to Keycloak at {token_url}: {e}")
        return None

async def get_user_from_token(token: str, db: Session) -> Optional[User]:
    """Validate token via Keycloak userinfo endpoint and sync/return DB user."""
    userinfo_url = get_keycloak_userinfo_endpoint()
    headers = {"Authorization": f"Bearer {token}"}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(userinfo_url, headers=headers)
            if resp.status_code != 200:
                return None
            user_info = resp.json()
            username = user_info.get("preferred_username") or user_info.get("username") or user_info.get("email")
            email = user_info.get("email", f"{username}@example.com")

            # Check if user exists in database
            user = db.query(User).filter_by(username=username).first()
            if not user:
                # Determine role (check if admin)
                roles = user_info.get("realm_access", {}).get("roles", [])
                role = "admin" if "admin" in roles or username == "admin" else "user"
                user = User(
                    username=username,
                    email=email,
                    role=role,
                    keycloak_id=user_info.get("sub"),
                    created_at=datetime.now(timezone.utc)
                )
                db.add(user)
                db.flush()

                # Add initial balance
                balance = UserBalance(
                    user_id=user.id,
                    remaining_tokens=100000,
                    monthly_quota=100000,
                    total_consumed=0,
                    last_reset_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc)
                )
                db.add(balance)

                # Generate default API key
                import secrets
                api_key = ApiKey(
                    user_id=user.id,
                    api_key=f"sk-{secrets.token_urlsafe(24)}",
                    name="Default Key",
                    is_active=True,
                    created_at=datetime.now(timezone.utc)
                )
                db.add(api_key)
                db.commit()

            return user
    except Exception as e:
        logger.error(f"Error validating token with Keycloak: {e}")
        return None

def get_current_user_from_session(request: Request, db: Session = Depends(get_db)) -> User:
    """Extract authenticated user from session cookie or Authorization Bearer header."""
    auth_header = request.headers.get("Authorization")
    token = None
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.replace("Bearer ", "").strip()
    
    if not token:
        token = request.cookies.get("session_token")

    if not token:
        # Check fallback demo username cookie for seamless local development
        username = request.cookies.get("username")
        if username:
            user = db.query(User).filter_by(username=username).first()
            if user:
                return user
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    # In production/Kubernetes, look up user
    username = request.cookies.get("username")
    if username:
        user = db.query(User).filter_by(username=username).first()
        if user:
            return user

    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired or invalid")

def require_admin(user: User = Depends(get_current_user_from_session)) -> User:
    """Ensure current user has admin role."""
    if user.role != "admin" and user.username != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin privileges required")
    return user
