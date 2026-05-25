from functools import wraps
from typing import Callable

from fastapi import HTTPException, Request, status
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app import models


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def authenticate_user(db: Session, username: str, password: str) -> models.User | None:
    user = db.query(models.User).filter(models.User.username == username, models.User.is_active.is_(True)).first()
    if not user or not verify_password(password, user.password_hash):
        return None
    return user


def login_user(request: Request, user: models.User) -> None:
    request.session["user_id"] = user.id
    request.session["role"] = user.role
    request.session["display_name"] = user.display_name


def logout_user(request: Request) -> None:
    request.session.clear()


def current_user(request: Request, db: Session) -> models.User | None:
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    return db.get(models.User, int(user_id))


def require_user(request: Request, db: Session, roles: set[str] | None = None) -> models.User:
    user = current_user(request, db)
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_303_SEE_OTHER, headers={"Location": "/login"})
    if roles and user.role not in roles:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="没有访问权限")
    return user
