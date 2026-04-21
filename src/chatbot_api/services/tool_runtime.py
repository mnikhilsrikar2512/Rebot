from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from threading import Lock
from typing import Any

from fastapi import HTTPException

from chatbot_api.adapters.factory import get_adapter
from chatbot_api.schemas import ToolDefinition, ToolInvokeResponse


class ToolRuntime:
    def __init__(self) -> None:
        self._registry: dict[str, dict[str, ToolDefinition]] = {}
        self._lock = Lock()
        self._adapter = get_adapter()

    def register(self, tenant_id: str, tools: list[ToolDefinition]) -> int:
        with self._lock:
            tenant_tools = self._registry.setdefault(tenant_id, {})
            for tool in tools:
                tenant_tools[tool.name] = tool
        return len(tools)

    def list_tools(self, tenant_id: str) -> list[ToolDefinition]:
        with self._lock:
            return list(self._registry.get(tenant_id, {}).values())

    def invoke(
        self,
        *,
        tenant_id: str,
        user_id: str,
        role: str,
        tool_name: str,
        params: dict[str, Any],
    ) -> ToolInvokeResponse:
        with self._lock:
            definition = self._registry.get(tenant_id, {}).get(tool_name)

        if not definition:
            raise HTTPException(status_code=404, detail="Tool not found")

        if role not in definition.allowed_roles:
            raise HTTPException(status_code=403, detail="Role is not allowed to invoke this tool")

        start = time.perf_counter()
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(
                self._adapter.run_action,
                tool_name,
                params,
                user_id,
                tenant_id,
            )
            try:
                output = future.result(timeout=max(0.001, definition.timeout_ms / 1000.0))
            except TimeoutError as exc:
                raise HTTPException(status_code=503, detail="Tool execution timed out") from exc
            except Exception as exc:
                raise HTTPException(status_code=503, detail="Tool execution failed") from exc

        duration_ms = int((time.perf_counter() - start) * 1000)
        return ToolInvokeResponse(
            tool_name=tool_name,
            status="success",
            output=output if isinstance(output, dict) else {"result": str(output)},
            duration_ms=duration_ms,
        )


tool_runtime = ToolRuntime()
