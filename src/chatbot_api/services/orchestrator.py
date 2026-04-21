from chatbot_api.adapters.factory import get_adapter, adapter_mode
from chatbot_api.adapters.mock_adapter import MockAdapter
from chatbot_api.config import settings
from chatbot_api.normalizer import normalize_user_text
from chatbot_api.schemas import ChatRequest, ChatResponse, Citation, ResponseMessage, Usage
from chatbot_api.services.domain_policy import domain_policy
from chatbot_api.services.memory import memory_store
from chatbot_api.services.model_runtime import runtime
from chatbot_api.services.tenant_settings import tenant_settings_service


class AdapterRuntimeError(Exception):
    pass


class AdminScopeError(Exception):
    pass


class TenantScopeError(Exception):
    pass


class ChatOrchestrator:
    def __init__(self) -> None:
        self.adapter = get_adapter()
        self.mode = adapter_mode()
        self.mock_adapter = MockAdapter()

    def run(self, request: ChatRequest) -> ChatResponse:
        normalized = normalize_user_text(request.message.content)
        admin_scope_terms = ["all users", "platform", "across users", "everyone", "team overview"]
        asks_admin_scope = any(term in normalized for term in admin_scope_terms)

        in_scope, domain = domain_policy.is_query_in_scope(request.tenant_id, normalized)
        if not in_scope:
            message = (
                f"I can only help with {domain}-related questions for this website. "
                "Ask something related to your account and this domain."
            )
            return ChatResponse(
                session_id=request.session_id,
                message=ResponseMessage(content=message, citations=[]),
                confidence_score=0.99,
                needs_clarification=False,
                missing_data_fields=[],
                usage=Usage(
                    input_tokens=max(1, len(request.message.content.split())),
                    output_tokens=max(1, len(message.split())),
                    model=runtime.model_name,
                ),
                warnings=[f"domain_scope_blocked:{domain}"],
            )

        memory_store.append(
            request.session_id,
            request.message,
            tenant_id=request.tenant_id,
            user_id=request.user_id,
        )

        warnings: list[str] = []

        try:
            user_context = self.adapter.get_user_context(
                user_id=request.user_id,
                tenant_id=request.tenant_id,
            )
            domain_entities = self.adapter.get_domain_entities(
                query=normalized,
                user_id=request.user_id,
                tenant_id=request.tenant_id,
            )
        except PermissionError as exc:
            raise TenantScopeError("User is not authorized for this tenant") from exc
        except Exception:
            if not settings.db_fallback_to_mock:
                raise AdapterRuntimeError("SQL adapter unavailable")
            user_context = self.mock_adapter.get_user_context(
                user_id=request.user_id,
                tenant_id=request.tenant_id,
            )
            domain_entities = self.mock_adapter.get_domain_entities(
                query=normalized,
                user_id=request.user_id,
                tenant_id=request.tenant_id,
            )
            warnings.append("sql_adapter_unavailable_fallback_mock")

        role = str(user_context.get("role") or "user").lower()
        if asks_admin_scope and role != "admin":
            raise AdminScopeError("Admin access required for platform-level queries")

        content, confidence, missing_fields = runtime.generate_account_response(
            normalized_query=normalized,
            user_context=user_context,
            insights=domain_entities,
            verbose=request.verbose,
            runtime_settings=tenant_settings_service.get_settings(request.tenant_id).model_dump(),
        )

        policy = self.adapter.policy_checks(
            input_text=request.message.content,
            candidate_output=content,
            tenant_id=request.tenant_id,
        )
        if not policy["allowed"]:
            content = "I cannot help with requests that attempt to access data outside your account scope."
            confidence = 0.99
            warnings.append(policy["reason"])

        warnings.append(f"adapter_mode:{self.mode}")

        response = ChatResponse(
            session_id=request.session_id,
            message=ResponseMessage(
                content=content,
                citations=[Citation(source_type="tool", source_id="tool.user_context")],
            ),
            confidence_score=round(confidence, 2),
            needs_clarification=bool(missing_fields),
            missing_data_fields=missing_fields,
            usage=Usage(
                input_tokens=max(1, len(request.message.content.split())),
                output_tokens=max(1, len(content.split())),
                model=runtime.model_name,
            ),
            warnings=warnings,
        )

        memory_store.append(
            request.session_id,
            response.message,
            tenant_id=request.tenant_id,
            user_id=request.user_id,
        )
        return response


orchestrator = ChatOrchestrator()
