from __future__ import annotations

import hmac
import time
from hashlib import sha256

from fastapi import HTTPException, Request, Response, status

SESSION_COOKIE = "mp_session"
SESSION_MAX_AGE = 60 * 60 * 24 * 7


def issue_session(response: Response, *, username: str, secret: str) -> None:
    expires_at = int(time.time()) + SESSION_MAX_AGE
    payload = f"{username}:{expires_at}"
    signature = _sign(payload, secret)
    response.set_cookie(
        SESSION_COOKIE,
        f"{payload}:{signature}",
        max_age=SESSION_MAX_AGE,
        httponly=True,
        samesite="lax",
    )


def clear_session(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE)


def require_session(request: Request) -> None:
    if request.url.path in {
        "/api/health",
        "/api/auth/login",
        "/api/integrations/spotify/callback",
    }:
        return
    token = request.cookies.get(SESSION_COOKIE)
    if token is None or not _is_valid(token, request.app.state.musicpilot.settings.session_secret):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
        )


def _is_valid(token: str, secret: str) -> bool:
    parts = token.split(":")
    if len(parts) != 3:
        return False
    username, expires_at, signature = parts
    payload = f"{username}:{expires_at}"
    if not hmac.compare_digest(signature, _sign(payload, secret)):
        return False
    try:
        return int(expires_at) >= int(time.time())
    except ValueError:
        return False


def _sign(payload: str, secret: str) -> str:
    return hmac.new(secret.encode(), payload.encode(), sha256).hexdigest()
