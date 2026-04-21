from __future__ import annotations

import hashlib
import hmac

from sqlalchemy import create_engine, text

from chatbot_api.config import settings


def _hash_password(password: str, salt: str) -> str:
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 120_000)
    return digest.hex()


class AuthService:
    def __init__(self) -> None:
        self._engine = create_engine(settings.database_url, pool_pre_ping=True) if settings.database_url else None

    def authenticate(self, tenant_id: str, email: str, password: str) -> dict | None:
        if not self._engine:
            return None

        normalized_email = email.strip().lower()
        with self._engine.connect() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT TOP 1
                        u.id,
                        u.tenant_id,
                        u.name,
                        u.email,
                        u.role,
                        c.password_hash,
                        c.salt
                    FROM users u
                    JOIN chatbot_user_credentials c ON c.user_id = u.id
                    WHERE LOWER(u.email) = :email
                      AND CAST(u.tenant_id AS NVARCHAR(100)) = :tenant_id
                      AND c.is_active = 1
                    """
                ),
                {"email": normalized_email, "tenant_id": tenant_id},
            ).mappings().first()

        if not row:
            return None

        expected_hash = row["password_hash"]
        salt = row["salt"]
        candidate_hash = _hash_password(password, salt)
        if not hmac.compare_digest(str(expected_hash), candidate_hash):
            return None

        return {
            "user_id": str(row["id"]),
            "tenant_id": str(row["tenant_id"]),
            "name": row["name"],
            "email": row["email"],
            "role": row["role"],
        }


auth_service = AuthService()
