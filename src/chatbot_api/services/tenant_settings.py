from __future__ import annotations

import json
from typing import Any

from sqlalchemy import create_engine, text

from chatbot_api.config import settings
from chatbot_api.schemas import TenantRuntimeSettings, TenantRuntimeSettingsPatch


class TenantSettingsService:
    def __init__(self) -> None:
        self._engine = create_engine(settings.database_url, pool_pre_ping=True) if settings.database_url else None
        self._cache: dict[str, TenantRuntimeSettings] = {}
        self._table_ready = False
        if self._engine:
            self._table_ready = self._ensure_table()

    def _ensure_table(self) -> bool:
        if not self._engine:
            return False
        try:
            with self._engine.begin() as conn:
                conn.execute(
                    text(
                        """
                        IF OBJECT_ID('chatbot_tenant_runtime_settings', 'U') IS NULL
                        BEGIN
                            CREATE TABLE chatbot_tenant_runtime_settings (
                                tenant_id NVARCHAR(100) NOT NULL PRIMARY KEY,
                                settings_json NVARCHAR(MAX) NOT NULL,
                                updated_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
                            );
                        END
                        """
                    )
                )
            return True
        except Exception:
            return False

    def _default(self, tenant_id: str) -> TenantRuntimeSettings:
        return TenantRuntimeSettings(tenant_id=tenant_id)

    def get_settings(self, tenant_id: str) -> TenantRuntimeSettings:
        if tenant_id in self._cache:
            return self._cache[tenant_id]

        if not self._engine or not self._table_ready:
            value = self._default(tenant_id)
            self._cache[tenant_id] = value
            return value

        with self._engine.connect() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT TOP 1 settings_json
                    FROM chatbot_tenant_runtime_settings
                    WHERE tenant_id = :tenant_id
                    """
                ),
                {"tenant_id": tenant_id},
            ).mappings().first()

        if not row or not row.get("settings_json"):
            value = self._default(tenant_id)
            self._cache[tenant_id] = value
            return value

        try:
            payload: dict[str, Any] = json.loads(str(row["settings_json"]))
        except Exception:
            payload = {}

        value = TenantRuntimeSettings(tenant_id=tenant_id, **payload)
        self._cache[tenant_id] = value
        return value

    def update_settings(self, patch: TenantRuntimeSettingsPatch) -> TenantRuntimeSettings:
        current = self.get_settings(patch.tenant_id)
        merged = current.model_dump()
        for key in patch.model_fields_set:
            if key == "tenant_id":
                continue
            merged[key] = getattr(patch, key)

        updated = TenantRuntimeSettings(**merged)

        if self._engine and self._table_ready:
            payload = json.dumps(
                {
                    "response_style": updated.response_style,
                    "max_recommendations": updated.max_recommendations,
                    "show_verdict": updated.show_verdict,
                    "v2_enabled": updated.v2_enabled,
                    "v2_provider": updated.v2_provider,
                }
            )
            with self._engine.begin() as conn:
                conn.execute(
                    text(
                        """
                        MERGE chatbot_tenant_runtime_settings AS target
                        USING (SELECT :tenant_id AS tenant_id, :settings_json AS settings_json) AS source
                        ON target.tenant_id = source.tenant_id
                        WHEN MATCHED THEN
                          UPDATE SET settings_json = source.settings_json, updated_at = SYSUTCDATETIME()
                        WHEN NOT MATCHED THEN
                          INSERT (tenant_id, settings_json) VALUES (source.tenant_id, source.settings_json);
                        """
                    ),
                    {"tenant_id": updated.tenant_id, "settings_json": payload},
                )

        self._cache[updated.tenant_id] = updated
        return updated

    def resolve_v2_enabled(self, tenant_id: str) -> bool:
        tenant_value = self.get_settings(tenant_id).v2_enabled
        if tenant_value is None:
            return settings.enable_v2
        return bool(tenant_value)

    def resolve_v2_provider(self, tenant_id: str) -> str:
        tenant_value = self.get_settings(tenant_id).v2_provider
        return (tenant_value or settings.v2_research_provider).strip().lower()


tenant_settings_service = TenantSettingsService()
