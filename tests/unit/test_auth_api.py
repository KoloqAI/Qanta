from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_setup_status_unconfigured(client):
    response = await client.get("/auth/setup-status")
    assert response.status_code == 200
    assert response.json()["configured"] is False


@pytest.mark.asyncio
async def test_register_first_user(client):
    response = await client.post(
        "/auth/register",
        json={"email": "admin@quanta.dev", "password": "StrongPass123!"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "admin@quanta.dev"
    assert "id" in data
    assert "session_id" in response.cookies


@pytest.mark.asyncio
async def test_register_second_user_blocked(client):
    await client.post(
        "/auth/register",
        json={"email": "admin@quanta.dev", "password": "StrongPass123!"},
    )
    response = await client.post(
        "/auth/register",
        json={"email": "other@quanta.dev", "password": "OtherPass123!"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_login_success(client):
    await client.post(
        "/auth/register",
        json={"email": "admin@quanta.dev", "password": "StrongPass123!"},
    )
    response = await client.post(
        "/auth/login",
        json={"email": "admin@quanta.dev", "password": "StrongPass123!"},
    )
    assert response.status_code == 200
    assert "session_id" in response.cookies
    assert "csrf_token" in response.cookies


@pytest.mark.asyncio
async def test_login_wrong_password(client):
    await client.post(
        "/auth/register",
        json={"email": "admin@quanta.dev", "password": "StrongPass123!"},
    )
    response = await client.post(
        "/auth/login",
        json={"email": "admin@quanta.dev", "password": "WrongPass!"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_me_authenticated(client):
    reg = await client.post(
        "/auth/register",
        json={"email": "admin@quanta.dev", "password": "StrongPass123!"},
    )
    cookies = reg.cookies
    response = await client.get("/auth/me", cookies=cookies)
    assert response.status_code == 200
    assert response.json()["email"] == "admin@quanta.dev"


@pytest.mark.asyncio
async def test_me_unauthenticated(client):
    response = await client.get("/auth/me")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_protected_route_401_without_session(client):
    """M1 gate: mutating routes return 401 without a session."""
    response = await client.get("/strategies")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_portfolio_401_without_session(client):
    response = await client.get("/portfolio")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_setup_status_after_registration(client):
    await client.post(
        "/auth/register",
        json={"email": "admin@quanta.dev", "password": "StrongPass123!"},
    )
    response = await client.get("/auth/setup-status")
    assert response.status_code == 200
    assert response.json()["configured"] is True


@pytest.mark.asyncio
async def test_no_secret_in_user_response(client):
    """M1 gate: no secret appears in any client response."""
    response = await client.post(
        "/auth/register",
        json={"email": "admin@quanta.dev", "password": "StrongPass123!"},
    )
    data = response.json()
    body_str = str(data).lower()
    assert "password" not in body_str
    assert "cred_hash" not in body_str
    assert "secret_key" not in body_str
    assert "token_hash" not in body_str


@pytest.mark.asyncio
async def test_change_password(client):
    reg = await client.post(
        "/auth/register",
        json={"email": "admin@quanta.dev", "password": "StrongPass123!"},
    )
    cookies = reg.cookies
    response = await client.post(
        "/auth/change-password",
        json={"old_password": "StrongPass123!", "new_password": "NewPass456!"},
        cookies=cookies,
    )
    assert response.status_code == 200

    login_resp = await client.post(
        "/auth/login",
        json={"email": "admin@quanta.dev", "password": "NewPass456!"},
    )
    assert login_resp.status_code == 200


@pytest.mark.asyncio
async def test_change_password_wrong_old(client):
    reg = await client.post(
        "/auth/register",
        json={"email": "admin@quanta.dev", "password": "StrongPass123!"},
    )
    cookies = reg.cookies
    response = await client.post(
        "/auth/change-password",
        json={"old_password": "Wrong!", "new_password": "NewPass456!"},
        cookies=cookies,
    )
    assert response.status_code == 400
