#!/usr/bin/env python3
"""
Seed a user account into the database.

Usage:
    python scripts/seed_user.py [--email EMAIL] [--password PASSWORD]

Defaults to email=vkaushik, password=vkaushik.
Idempotent: skips creation if the email is already registered.
Loads .env automatically via app.config.settings.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

# Ensure project root is on sys.path when run directly.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.models.base import Base
from app.modules.auth.service import AuthServiceImpl


async def seed(email: str, password: str) -> None:
    engine = create_async_engine(settings.database_url, echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        svc = AuthServiceImpl(db)
        count = await svc.user_count()
        if count > 0:
            from sqlalchemy import select
            from app.models.models import User

            result = await db.execute(select(User).where(User.email == email))
            existing = result.scalar_one_or_none()
            if existing:
                print(f"User '{email}' already exists — no changes made.")
                await engine.dispose()
                return

        try:
            user = await svc.register(email, password)
            print(f"Created user: email={user['email']}  id={user['id']}")
        except ValueError as exc:
            print(f"Registration failed: {exc}")

    await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed a Quanta user account")
    parser.add_argument("--email", default="vkaushik@quanta.com", help="User email / login id")
    parser.add_argument("--password", default="vkaushik", help="Password")
    args = parser.parse_args()
    asyncio.run(seed(args.email, args.password))


if __name__ == "__main__":
    main()
