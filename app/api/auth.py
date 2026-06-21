from __future__ import annotations

import secrets

from fastapi import APIRouter, HTTPException, Request, Response, status

from app.config import settings
from app.deps import DB, CurrentUser
from app.modules.auth.service import AuthServiceImpl
from app.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    RegisterRequest,
    UserResponse,
)

router = APIRouter()

SESSION_COOKIE = "session_id"
CSRF_COOKIE = "csrf_token"


def _set_session_cookies(response: Response, token: str) -> None:
    csrf = secrets.token_urlsafe(16)
    response.set_cookie(
        SESSION_COOKIE,
        token,
        httponly=True,
        samesite="lax",
        secure=not settings.debug,
        max_age=settings.session_expire_minutes * 60,
    )
    response.set_cookie(
        CSRF_COOKIE,
        csrf,
        httponly=False,
        samesite="lax",
        secure=not settings.debug,
        max_age=settings.session_expire_minutes * 60,
    )


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, db: DB, response: Response) -> UserResponse:
    auth = AuthServiceImpl(db, settings.session_expire_minutes)
    count = await auth.user_count()
    if count > 0:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Registration disabled — single-user instance already set up",
        )
    try:
        user = await auth.register(body.email, body.password)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

    token, user_data = await auth.login(body.email, body.password)
    _set_session_cookies(response, token)
    return UserResponse(**user_data)


@router.post("/login")
async def login(body: LoginRequest, db: DB, response: Response) -> dict:
    auth = AuthServiceImpl(db, settings.session_expire_minutes)
    try:
        token, user_data = await auth.login(body.email, body.password)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )
    _set_session_cookies(response, token)
    return {"user": user_data}


@router.post("/logout")
async def logout(request: Request, response: Response, db: DB) -> dict:
    session_token = request.cookies.get(SESSION_COOKIE)
    if session_token:
        auth = AuthServiceImpl(db, settings.session_expire_minutes)
        await auth.logout(session_token)
    response.delete_cookie(SESSION_COOKIE)
    response.delete_cookie(CSRF_COOKIE)
    return {"detail": "logged out"}


@router.get("/me", response_model=UserResponse)
async def me(user: CurrentUser) -> UserResponse:
    return UserResponse(**user)


@router.post("/change-password")
async def change_password(
    body: ChangePasswordRequest, db: DB, user: CurrentUser
) -> dict:
    auth = AuthServiceImpl(db, settings.session_expire_minutes)
    success = await auth.change_password(user["id"], body.old_password, body.new_password)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )
    return {"detail": "password changed"}


@router.get("/setup-status")
async def setup_status(db: DB) -> dict:
    """Public endpoint: returns whether the app has been set up (user exists)."""
    auth = AuthServiceImpl(db, settings.session_expire_minutes)
    count = await auth.user_count()
    return {"configured": count > 0}
