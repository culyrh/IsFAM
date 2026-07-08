from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import User


class UserRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_phone_number(self, phone_number: str) -> User | None:
        return self.db.scalar(select(User).where(User.phone_number == phone_number))

    def get_by_id(self, user_id: int) -> User | None:
        return self.db.get(User, user_id)

    def create(self, *, phone_number: str, display_name: str, role: str) -> User:
        user = User(phone_number=phone_number, display_name=display_name, role=role)
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user
