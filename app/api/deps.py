from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.security import TokenError, decode_access_token
from app.db.postgres import get_db
from app.models.user import User
from app.repositories.user_repository import UserRepository


def get_bearer_token(authorization: str | None = Header(default=None)) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing or invalid Authorization header",
        )
    return authorization.split(" ", 1)[1].strip()


def get_current_token_payload(
    token: str = Depends(get_bearer_token),
    settings: Settings = Depends(get_settings),
) -> dict:
    try:
        return decode_access_token(token, settings)
    except TokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid or expired access token",
        ) from exc


def get_current_user(
    payload: dict = Depends(get_current_token_payload),
    db: Session = Depends(get_db),
) -> User:
    user = UserRepository(db).get_by_id(int(payload["sub"]))
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="user not found")
    return user


def require_role(*roles: str):
    def _dependency(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden for this role")
        return user

    return _dependency
