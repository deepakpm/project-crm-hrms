import secrets
import uuid
from datetime import UTC, datetime, timedelta
from hashlib import sha256

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import AppUser, RefreshToken, Tenant
from app.schemas import LoginRequest, RefreshRequest, SignupRequest, TokenResponse
from app.security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


def _hash_token(raw: str) -> str:
    return sha256(raw.encode()).hexdigest()


def _set_tenant_context(db: Session, tenant_id: uuid.UUID) -> None:
    # Tenant comes from a value WE already trust (a slug lookup, or our own stored
    # refresh_token row) -- never from a client-supplied tenant_id field.
    db.execute(text("SELECT set_config('app.tenant_id', :tid, true)"), {"tid": str(tenant_id)})


def _issue_tokens(db: Session, user: AppUser) -> TokenResponse:
    access = create_access_token(user.id, user.tenant_id, user.role)
    raw_refresh = secrets.token_urlsafe(32)
    db.add(
        RefreshToken(
            tenant_id=user.tenant_id,
            user_id=user.id,
            token_hash=_hash_token(raw_refresh),
            expires_at=datetime.now(UTC) + timedelta(days=settings.refresh_token_days),
        )
    )
    return TokenResponse(access_token=access, refresh_token=raw_refresh)


@router.post("/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def signup(body: SignupRequest, db: Session = Depends(get_db)) -> TokenResponse:
    tenant = Tenant(name=body.company_name, slug=body.tenant_slug)
    db.add(tenant)
    try:
        db.flush()
    except IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="slug already taken"
        ) from exc

    _set_tenant_context(db, tenant.id)

    user = AppUser(
        tenant_id=tenant.id,
        email=body.email,
        password_hash=hash_password(body.password),
        role="owner",
    )
    db.add(user)
    try:
        db.flush()
    except IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="email already used"
        ) from exc
    return _issue_tokens(db, user)


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    tenant = db.scalar(select(Tenant).where(Tenant.slug == body.tenant_slug))
    if tenant is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid credentials")

    _set_tenant_context(db, tenant.id)

    user = db.scalar(select(AppUser).where(AppUser.email == body.email))
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid credentials")
    return _issue_tokens(db, user)


@router.post("/refresh", response_model=TokenResponse)
def refresh(body: RefreshRequest, db: Session = Depends(get_db)) -> TokenResponse:
    # refresh_token has no RLS: it's a bearer credential looked up by its own
    # high-entropy hash, before any tenant context can be known.
    token_hash = _hash_token(body.refresh_token)
    row = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
    now = datetime.now(UTC)
    if row is None or row.revoked_at is not None or row.expires_at < now:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid refresh token"
        )

    _set_tenant_context(db, row.tenant_id)  # row.tenant_id is ours, not client input
    row.revoked_at = now  # rotate: one-time use

    user = db.get(AppUser, row.user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid refresh token"
        )

    # Expired/used tokens are dead weight; no job runner yet for a scheduled sweep,
    # so sweep this user's own tokens opportunistically on every refresh instead.
    db.query(RefreshToken).filter(
        RefreshToken.user_id == user.id,
        (RefreshToken.expires_at < now) | (RefreshToken.revoked_at.is_not(None)),
    ).delete(synchronize_session=False)

    return _issue_tokens(db, user)
