from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session as DBSession

from app.models.base import Base
from app.modules.auth.service import AuthServiceImpl, ph, _hash_token


@pytest.fixture
def sync_engine():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def sync_session(sync_engine):
    with DBSession(sync_engine) as session:
        yield session


class TestPasswordHashing:
    def test_hash_and_verify(self):
        hashed = ph.hash("secure-password")
        assert ph.verify(hashed, "secure-password")

    def test_wrong_password_fails(self):
        from argon2.exceptions import VerifyMismatchError
        hashed = ph.hash("correct")
        with pytest.raises(VerifyMismatchError):
            ph.verify(hashed, "wrong")

    def test_different_hashes_for_same_password(self):
        h1 = ph.hash("same")
        h2 = ph.hash("same")
        assert h1 != h2


class TestTokenHashing:
    def test_hash_is_deterministic(self):
        assert _hash_token("abc") == _hash_token("abc")

    def test_different_tokens_different_hashes(self):
        assert _hash_token("abc") != _hash_token("xyz")
