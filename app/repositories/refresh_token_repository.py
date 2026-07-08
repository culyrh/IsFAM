from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.refresh_token import RefreshToken


class RefreshTokenRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        *,
        user_id: int,
        device_id: int | None,
        token_hash: str,
        issued_at: datetime,
        expires_at: datetime,
    ) -> RefreshToken:
        token = RefreshToken(
            user_id=user_id,
            device_id=device_id,
            token_hash=token_hash,
            issued_at=issued_at,
            expires_at=expires_at,
        )
        self.db.add(token)
        self.db.commit()
        self.db.refresh(token)
        return token

    def get_by_hash(self, token_hash: str) -> RefreshToken | None:
        return self.db.scalar(select(RefreshToken).where(RefreshToken.token_hash == token_hash))

    def get_by_id(self, token_id: int) -> RefreshToken | None:
        return self.db.get(RefreshToken, token_id)

    def revoke(self, token: RefreshToken) -> None:
        token.revoked_at = datetime.now(timezone.utc)
        self.db.add(token)
        self.db.commit()
