from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Protocol

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import User, Session, UserSettings, AuditLogEntry, ActorType
from app.models.base import generate_uuid


class AuthService(Protocol):
    async def register(self, email: str, password: str) -> dict: ...
    async def login(self, email: str, password: str) -> str: ...
    async def logout(self, session_id: str) -> None: ...
    async def validate_session(self, session_token: str) -> dict | None: ...
    async def change_password(
        self, user_id: str, old_password: str, new_password: str
    ) -> bool: ...


ph = PasswordHasher()


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class AuthServiceImpl:
    def __init__(self, db: AsyncSession, session_expire_minutes: int = 1440) -> None:
        self._db = db
        self._session_expire_minutes = session_expire_minutes

    async def register(self, email: str, password: str) -> dict:
        existing = await self._db.execute(select(User).where(User.email == email))
        if existing.scalar_one_or_none():
            raise ValueError("Email already registered")

        user = User(
            id=generate_uuid(),
            email=email,
            cred_hash=ph.hash(password),
        )
        self._db.add(user)

        user_settings = UserSettings(
            user_id=user.id,
            appearance={"theme": "system"},
            risk={},
            models={},
        )
        self._db.add(user_settings)

        await self._audit(user.id, "register", "user", user.id)
        await self._db.commit()
        return {"id": user.id, "email": user.email}

    async def login(self, email: str, password: str) -> tuple[str, dict]:
        result = await self._db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if not user:
            raise ValueError("Invalid credentials")

        try:
            ph.verify(user.cred_hash, password)
        except VerifyMismatchError:
            raise ValueError("Invalid credentials")

        if ph.check_needs_rehash(user.cred_hash):
            user.cred_hash = ph.hash(password)

        raw_token = secrets.token_urlsafe(32)
        session = Session(
            id=generate_uuid(),
            user_id=user.id,
            token_hash=_hash_token(raw_token),
            expires_at=datetime.now(timezone.utc)
            + timedelta(minutes=self._session_expire_minutes),
        )
        self._db.add(session)
        await self._audit(user.id, "login", "session", session.id)
        await self._db.commit()
        return raw_token, {"id": user.id, "email": user.email}

    async def logout(self, session_token: str) -> None:
        token_hash = _hash_token(session_token)
        result = await self._db.execute(
            select(Session).where(Session.token_hash == token_hash)
        )
        session = result.scalar_one_or_none()
        if session:
            await self._audit(session.user_id, "logout", "session", session.id)
            await self._db.delete(session)
            await self._db.commit()

    async def validate_session(self, session_token: str) -> dict | None:
        token_hash = _hash_token(session_token)
        result = await self._db.execute(
            select(Session)
            .where(Session.token_hash == token_hash)
            .where(Session.expires_at > datetime.now(timezone.utc))
        )
        session = result.scalar_one_or_none()
        if not session:
            return None

        user_result = await self._db.execute(
            select(User).where(User.id == session.user_id)
        )
        user = user_result.scalar_one_or_none()
        if not user:
            return None

        return {"id": user.id, "email": user.email}

    async def change_password(
        self, user_id: str, old_password: str, new_password: str
    ) -> bool:
        result = await self._db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            return False

        try:
            ph.verify(user.cred_hash, old_password)
        except VerifyMismatchError:
            return False

        user.cred_hash = ph.hash(new_password)
        await self._invalidate_other_sessions(user_id)
        await self._audit(user_id, "change_password", "user", user_id)
        await self._db.commit()
        return True

    async def get_user(self, user_id: str) -> dict | None:
        result = await self._db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            return None
        return {"id": user.id, "email": user.email}

    async def user_count(self) -> int:
        result = await self._db.execute(select(User))
        return len(result.scalars().all())

    async def _invalidate_other_sessions(self, user_id: str) -> None:
        await self._db.execute(
            delete(Session).where(Session.user_id == user_id)
        )

    async def _audit(
        self, user_id: str, action: str, subject_type: str, subject_id: str
    ) -> None:
        entry = AuditLogEntry(
            id=generate_uuid(),
            user_id=user_id,
            actor=ActorType.USER,
            action=action,
            subject_type=subject_type,
            subject_id=subject_id,
        )
        self._db.add(entry)
