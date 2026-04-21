from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Cookie, Header, HTTPException, status

from chatbot_api.config import settings


@dataclass
class AuthContext:
    tenant_id: str
    user_id: str
    role: str = "user"


def _parse_bearer_token(token: str) -> AuthContext:
    # Dev format: tenant:<tenant_id>|user:<user_id>|role:<role>
    # Example: tenant:tnt_123|user:usr_456|role:user
    parts = token.split("|")
    parsed: dict[str, str] = {}
    for part in parts:
        if ":" not in part:
            continue
        k, v = part.split(":", 1)
        parsed[k.strip()] = v.strip()

    tenant_id = parsed.get("tenant")
    user_id = parsed.get("user")
    role = parsed.get("role", "user")

    if not tenant_id or not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token format",
        )
    return AuthContext(tenant_id=tenant_id, user_id=user_id, role=role)


def _parse_jwt_token(token: str) -> AuthContext:
    if not settings.jwt_secret:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="JWT secret is not configured",
        )
    try:
        decode_kwargs = {
            "key": settings.jwt_secret,
            "algorithms": [settings.jwt_algorithm],
        }
        if settings.jwt_audience:
            decode_kwargs["audience"] = settings.jwt_audience
        else:
            decode_kwargs["options"] = {"verify_aud": False}

        if settings.jwt_issuer:
            decode_kwargs["issuer"] = settings.jwt_issuer

        payload = jwt.decode(
            token,
            **decode_kwargs,
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid JWT token",
        ) from exc

    tenant_id = payload.get(settings.jwt_claim_tenant_id)
    user_id = payload.get(settings.jwt_claim_user_id)
    if not user_id and settings.jwt_claim_sub_fallback_enabled:
        user_id = payload.get("sub")
    role = payload.get(settings.jwt_claim_role, "user")

    if not tenant_id or not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="JWT missing required claims",
        )
    return AuthContext(tenant_id=str(tenant_id), user_id=str(user_id), role=str(role))


def create_access_token(tenant_id: str, user_id: str, role: str, expires_minutes: int = 480) -> str:
    if not settings.jwt_secret:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="JWT secret is not configured",
        )

    now = datetime.now(timezone.utc)
    payload = {
        "tenant_id": tenant_id,
        "user_id": user_id,
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=expires_minutes)).timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def try_parse_auth_header(authorization: str | None) -> AuthContext | None:
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization.removeprefix("Bearer ").strip()
    try:
        if token.count(".") == 2:
            return _parse_jwt_token(token)
        if settings.allow_dev_token_auth:
            return _parse_bearer_token(token)
    except HTTPException:
        return None
    return None


def require_auth(
    authorization: str | None = Header(default=None),
    access_token: str | None = Cookie(default=None),
) -> AuthContext:
    token: str | None = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization.removeprefix("Bearer ").strip()
    elif access_token:
        token = access_token

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token",
        )

    if token.count(".") == 2:
        return _parse_jwt_token(token)
    if settings.allow_dev_token_auth:
        return _parse_bearer_token(token)
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Dev token auth disabled; provide a JWT bearer token",
    )


def enforce_request_scope(auth: AuthContext, tenant_id: str, user_id: str) -> None:
    if auth.role == "runtime_service":
        return
    if auth.tenant_id != tenant_id or auth.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Request scope does not match authenticated token",
        )
