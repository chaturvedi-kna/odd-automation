"""
Admin panel API — user management (admin role required for all endpoints).
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from passlib.context import CryptContext

from app.db.deps import get_db
from app.models.user import User
from app.api.deps.auth import require_admin

router = APIRouter(prefix="/users", tags=["users"])

_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")

VALID_ROLES = ("admin", "operator", "viewer")


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=6, max_length=72)
    email: str | None = None
    role: str = "operator"


class UserUpdate(BaseModel):
    email: str | None = None
    role: str | None = None
    password: str | None = Field(default=None, min_length=6, max_length=72)
    is_active: bool | None = None


def _user_out(u: User) -> dict:
    return {
        "id": u.id,
        "username": u.username,
        "email": u.email,
        "role": u.role,
        "is_active": u.is_active,
        "created_at": u.created_at.isoformat() if u.created_at else None,
    }


@router.get("/")
async def list_users(
    db: AsyncSession = Depends(get_db),
    _=Depends(require_admin),
):
    users = (await db.execute(select(User).order_by(User.username))).scalars().all()
    return [_user_out(u) for u in users]


@router.post("/", status_code=201)
async def create_user(
    payload: UserCreate,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_admin),
):
    if payload.role not in VALID_ROLES:
        raise HTTPException(400, f"role must be one of {', '.join(VALID_ROLES)}")

    exists = (await db.execute(
        select(User).where(User.username == payload.username)
    )).scalars().first()
    if exists:
        raise HTTPException(409, "Username already exists")

    user = User(
        id=str(uuid.uuid4()),
        username=payload.username,
        email=payload.email or None,
        role=payload.role,
        hashed_password=_pwd.hash(payload.password),
        is_active=True,
    )
    db.add(user)
    await db.flush()
    return _user_out(user)


@router.patch("/{user_id}")
async def update_user(
    user_id: str,
    payload: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    user = (await db.execute(select(User).where(User.id == user_id))).scalars().first()
    if not user:
        raise HTTPException(404, "User not found")

    if payload.role is not None:
        if payload.role not in VALID_ROLES:
            raise HTTPException(400, f"role must be one of {', '.join(VALID_ROLES)}")
        # Never allow removing the last active admin
        if user.role == "admin" and payload.role != "admin":
            await _guard_last_admin(db, user)
        user.role = payload.role

    if payload.is_active is not None:
        if user.id == current_admin.id and payload.is_active is False:
            raise HTTPException(400, "You cannot deactivate your own account")
        if user.role == "admin" and payload.is_active is False:
            await _guard_last_admin(db, user)
        user.is_active = payload.is_active

    if payload.email is not None:
        user.email = payload.email or None

    if payload.password:
        user.hashed_password = _pwd.hash(payload.password)

    await db.flush()
    return _user_out(user)


@router.delete("/{user_id}")
async def delete_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    user = (await db.execute(select(User).where(User.id == user_id))).scalars().first()
    if not user:
        raise HTTPException(404, "User not found")
    if user.id == current_admin.id:
        raise HTTPException(400, "You cannot delete your own account")
    if user.role == "admin":
        await _guard_last_admin(db, user)

    # Requests reference users via FK — keep history intact by
    # deactivating instead of deleting when the user has activity.
    from app.models.change_request import ChangeRequest
    has_requests = (await db.execute(
        select(func.count(ChangeRequest.id)).where(ChangeRequest.created_by_user_id == user_id)
    )).scalar()
    if has_requests:
        user.is_active = False
        await db.flush()
        return {"id": user_id, "deleted": False, "deactivated": True,
                "detail": "User has change requests; account deactivated to preserve history."}

    await db.delete(user)
    await db.flush()
    return {"id": user_id, "deleted": True}


async def _guard_last_admin(db: AsyncSession, user: User) -> None:
    other_admins = (await db.execute(
        select(func.count(User.id)).where(
            User.role == "admin", User.is_active == True, User.id != user.id  # noqa: E712
        )
    )).scalar()
    if not other_admins:
        raise HTTPException(400, "Cannot remove or demote the last active admin")
