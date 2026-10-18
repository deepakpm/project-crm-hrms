from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.deps import CurrentUser, get_tenant_db, require_roles
from app.models import AppUser
from app.schemas import UserCreateIn, UserOut
from app.security import hash_password

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserOut])
def list_users(db: Session = Depends(get_tenant_db)) -> list[AppUser]:
    # No tenant_id filter here on purpose: RLS alone must do the filtering.
    return list(db.scalars(select(AppUser)))


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(
    body: UserCreateIn,
    current_user: CurrentUser = Depends(require_roles("owner")),
    db: Session = Depends(get_tenant_db),
) -> AppUser:
    """Adds a teammate to the current tenant. Only the owner invites -- unlike
    signup, this never creates a new tenant."""
    user = AppUser(
        tenant_id=current_user.tenant_id,
        email=body.email,
        password_hash=hash_password(body.password),
        role=body.role,
    )
    db.add(user)
    try:
        db.flush()
    except IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="email already used"
        ) from exc
    return user
