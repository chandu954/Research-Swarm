"""OAuth callback helpers and Google OAuth endpoints.

Moved from backend/api/auth.py to keep the auth router focused on
email/password and session management.
"""

from __future__ import annotations

import json
from typing import Callable

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from secrets import token_urlsafe

from backend.api.auth import (
    TokenResponse,
    _build_tokens,
    _create_session,
    _find_or_create_user,
    get_session,
)
from backend.auth.providers import get_google_auth_url

router = APIRouter(tags=["auth"])


def _oauth_callback_html(tokens, error: str = "") -> HTMLResponse:
    """Render HTML page that sends tokens to opener popup and closes."""
    from backend.auth.providers import config as oauth_config

    app_url = oauth_config.app_url
    if error:
        script = f"""
          if (window.opener) {{
            window.opener.postMessage({{ error: {json.dumps(error)} }}, "{app_url}");
            window.close();
          }} else {{
            window.location.href = "{app_url}/login?error=" + encodeURIComponent({json.dumps(error)});
          }}
        """
    else:
        script = f"""
          if (window.opener) {{
            window.opener.postMessage({{
              access_token: {json.dumps(tokens.access_token)},
              refresh_token: {json.dumps(tokens.refresh_token)},
              supabase_access_token: {json.dumps(tokens.supabase_access_token)},
              supabase_refresh_token: {json.dumps(tokens.supabase_refresh_token)}
            }}, "{app_url}");
            window.close();
          }} else {{
            window.location.href = "{app_url}/login?oauth=success";
          }}
        """
    html = f"""<!DOCTYPE html>
<html><body><script>{script}</script></body></html>"""
    return HTMLResponse(html)


async def _handle_oauth_callback(
    provider: str,
    code: str,
    exchange_func: Callable,
    userinfo_func: Callable,
    name_key: str,
    email_keys: list[str],
    avatar_key: str,
    id_key: str,
    request: Request,
    session: AsyncSession,
) -> HTMLResponse:
    tokens = await exchange_func(code)
    if not tokens:
        return _oauth_callback_html(
            TokenResponse(access_token="", refresh_token=""),
            error="Failed to exchange authorization code",
        )

    userinfo = await userinfo_func(tokens.get("access_token", ""))
    if not userinfo:
        return _oauth_callback_html(
            TokenResponse(access_token="", refresh_token=""),
            error="Failed to get user info",
        )

    email = ""
    for key in email_keys:
        email = userinfo.get(key, "")
        if email:
            break

    user = await _find_or_create_user(
        email=email,
        name=userinfo.get(name_key, ""),
        provider_data={
            "id": str(userinfo.get(id_key, "")),
            "avatar_url": userinfo.get(avatar_key),
        },
        provider=provider,
        db_session=session,
    )
    refresh_token = await _create_session(user, request, session)
    return _oauth_callback_html(await _build_tokens(user, refresh_token=refresh_token))


@router.get("/google")
async def google_login() -> RedirectResponse:
    state = token_urlsafe(32)
    response = RedirectResponse(url=get_google_auth_url(state=state))
    response.set_cookie(
        key="oauth_state",
        value=state,
        max_age=600,
        httponly=True,
        secure=True,
        samesite="lax",
    )
    return response


@router.get("/google/callback")
async def google_callback(
    code: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
    state: str = Query(None),
) -> HTMLResponse:
    from backend.api import auth as _auth_module

    stored_state = request.cookies.get("oauth_state")
    if not stored_state or not state or stored_state != state:
        return _oauth_callback_html(
            TokenResponse(access_token="", refresh_token=""),
            error="Invalid state parameter",
        )
    resp = await _handle_oauth_callback(
        provider="google",
        code=code,
        exchange_func=_auth_module.exchange_google_code,
        userinfo_func=_auth_module.get_google_userinfo,
        name_key="name",
        email_keys=["email"],
        avatar_key="picture",
        id_key="id",
        request=request,
        session=session,
    )
    resp.delete_cookie("oauth_state")
    return resp
