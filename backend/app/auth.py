"""Authentication, RBAC, and Audit Logging utilities."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import bcrypt
import jwt
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import AuditLog, User

security_scheme = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"), hashed_password.encode("utf-8")
        )
    except Exception:
        # Fallback sha256 check if legacy fixture
        return (
            hashlib.sha256(plain_password.encode("utf-8")).hexdigest()
            == hashed_password
        )


def create_access_token(data: dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT access token. Raises ``jwt.PyJWTError`` if invalid."""
    return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])


def seed_default_users(db: Session) -> None:
    """Create standard role-based demo users if they do not exist."""
    existing = db.query(User).count()
    if existing > 0:
        return

    default_users = [
        User(
            username="elena.vance",
            email="elena.vance@manufacturing.local",
            full_name="Elena Vance (VP Procurement)",
            hashed_password=hash_password("Procurement2026!"),
            role="admin",
            is_active=True,
        ),
        User(
            username="marcus.chen",
            email="marcus.chen@manufacturing.local",
            full_name="Marcus Chen (Lead Supply Risk Analyst)",
            hashed_password=hash_password("Analyst2026!"),
            role="procurement_lead",
            is_active=True,
        ),
        User(
            username="priya.nair",
            email="priya.nair@manufacturing.local",
            full_name="Priya Nair (Senior Buyer / Reviewer)",
            hashed_password=hash_password("Reviewer2026!"),
            role="reviewer",
            is_active=True,
        ),
        User(
            username="david.miller",
            email="david.miller@manufacturing.local",
            full_name="David Miller (Plant Operations Viewer)",
            hashed_password=hash_password("Viewer2026!"),
            role="viewer",
            is_active=True,
        ),
    ]
    db.add_all(default_users)
    db.commit()


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    x_demo_role: Optional[str] = Header(default=None),
    x_demo_user: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    """Resolve authenticated user from Bearer token or demo role header."""
    if credentials and credentials.credentials:
        token = credentials.credentials
        try:
            payload = decode_access_token(token)
            username: Optional[str] = payload.get("sub")
            if username:
                user = db.query(User).filter(User.username == username).first()
                if user and user.is_active:
                    return user
        except jwt.PyJWTError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired authentication token",
            ) from exc

    # Support interactive role switching via header in demonstration mode only.
    # When ALLOW_DEMO_MODE=false these headers are ignored entirely so that a
    # valid Bearer token is mandatory (see SECURITY.md).
    if settings.allow_demo_mode:
        if x_demo_user:
            user = db.query(User).filter(User.username == x_demo_user).first()
            if user:
                return user

        if x_demo_role:
            if x_demo_role == "unauthenticated":
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required",
                )
            user = db.query(User).filter(User.role == x_demo_role).first()
            if user:
                return user

        # Default to Lead Supply Risk Analyst for seamless out-of-the-box evaluation
        default_user = (
            db.query(User).filter(User.username == "marcus.chen").first()
            or db.query(User).first()
        )
        if default_user:
            return default_user

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required: provide a valid Bearer token",
        headers={"WWW-Authenticate": "Bearer"},
    )


ROLE_HIERARCHY = {
    "viewer": 1,
    "reviewer": 2,
    "procurement_lead": 3,
    "admin": 4,
}


def require_min_role(min_role: str):
    """Dependency enforcing minimum RBAC role privilege."""

    def _checker(current_user: User = Depends(get_current_user)) -> User:
        user_level = ROLE_HIERARCHY.get(current_user.role, 0)
        required_level = ROLE_HIERARCHY.get(min_role, 99)
        if user_level < required_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Insufficient permissions: role '{current_user.role}' cannot "
                    f"perform action requiring '{min_role}' or higher."
                ),
            )
        return current_user

    return _checker


def record_audit_log(
    db: Session,
    actor: str,
    role: str,
    action: str,
    entity_type: str,
    entity_id: str,
    details: dict[str, Any],
) -> AuditLog:
    """Write an immutable entry to the audit log."""
    entry = AuditLog(
        actor=actor,
        role=role,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id),
        details_json=json.dumps(details, default=str),
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry
