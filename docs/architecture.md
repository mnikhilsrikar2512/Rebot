# Universal Chatbot API - Architecture

## Overview

The Universal Chatbot API is a domain-agnostic conversational platform that integrates with any application (finance, education, business, event management, CRM, ERP, and more).

It delivers user-specific responses using tenant configuration, user context, and optional tool calls.

It is tolerant of noisy user input (spelling mistakes, shorthand, imperfect grammar) through an input normalization stage before intent routing.

It is designed for production from day one: secure multi-tenancy, observability, reliability controls, and backward-compatible versioning.

The platform is open-source-first and self-hosted; it does not depend on paid external LLM APIs.

### Primary Goals

- Easy to integrate into any app within hours.
- Personalized responses without hardcoding domain logic in the core API.
- Open-source model gateway with multi-model failover.
- Enterprise-ready security, governance, and auditability.

## Core Concepts

- **Tenant**: A customer/workspace using the platform.
- **User**: End user within a tenant.
- **Session**: Conversation container for context continuity.
- **Message**: Unit of user/assistant/tool communication.
- **Tool**: External function/API callable by the assistant.
- **Adapter**: Domain/application connector implementing the standard contract.
- **Policy**: Rules controlling behavior, safety, and tool access.
- **Prompt Pack**: Versioned instructions for assistant behavior.
- **Trace**: End-to-end execution record for debugging/audit.

## High-Level Architecture

- **API Gateway**: Authentication, rate limits, request validation.
- **Chat Orchestrator**: Builds prompt, calls model, handles tool execution loop.
- **Input Normalizer**: Cleans noisy text and improves intent extraction before retrieval/tool selection.
- **Context Service**: Pulls user/app context via adapters.
- **Tool Registry**: Tenant-scoped tool definitions and permissions.
- **Policy Engine**: Input/output safety checks and rule enforcement.
- **Memory Service**: Session history and summarization.
- **Model Gateway**: Routes to self-hosted model runtimes with fallback.
- **Model Serving Layer**: Self-hosted open-source models (for example via vLLM/Ollama) with fallback routing.
- **Storage**: Postgres (source of truth), Redis (cache/session hot path), object storage (attachments).
- **Queue Workers**: Async tasks (webhooks, long tool calls, background indexing).
- **Observability Stack**: Logs, metrics, traces, alerts.

## API Design Principles

- Versioned endpoints (`/v1/...`) and no breaking changes inside a major version.
- JSON-first contracts with explicit schemas.
- Idempotent write operations using `Idempotency-Key`.
- Streaming and non-streaming support.
- Deterministic error envelope.
- Correlation via `request_id` and `trace_id` in all responses.

## Authentication and Authorization

- **Server-to-server**: signed service token or internal JWT (`Authorization: Bearer <token>`).
- **User-context calls**: JWT support (`sub`, `tenant_id`, roles).
- **RBAC** roles: `tenant_admin`, `developer`, `analyst`, `runtime_service`.
- **Least privilege**: Tool execution allowed only when explicitly granted by policy.
- **Identity-bound requests**: Every chat request is resolved against authenticated `tenant_id` and `user_id`.

## Open-Source Runtime Rules

- No paid model API key is required for core inference.
- Model lifecycle (download, quantization, upgrade, rollback) is managed internally.
- Capacity planning (GPU/CPU memory, concurrency, queue depth) is required for stable p95 latency.

## Multi-Tenant Data Isolation

- Every record includes `tenant_id`.
- DB row-level protections and query guards.
- Cache keys namespaced by tenant.
- Strict prohibition on cross-tenant retrieval.
- Isolation tests required in CI.

## Universal Adapter Contract

Every domain/app integration implements this standard contract:

- `get_user_context(user_id, tenant_id)` returns normalized user profile/preferences.
- `get_domain_entities(query, user_id, tenant_id)` returns relevant business objects (courses, invoices, events, tickets, and so on).
- `run_action(action_name, params, user_id, tenant_id)` executes allowed domain action.
- `policy_checks(input, candidate_output, tenant_id)` optionally applies custom policy gating.

This keeps the core chatbot generic while allowing deep personalization.

## Grounding Rules

- The assistant must prioritize client application data as source of truth for account-specific questions.
- Generic model priors can assist with phrasing and explanation, but not replace missing account facts.
- If user data is unavailable or insufficient, the assistant asks clarifying questions and reports missing fields.

## Prompt Orchestration

Final prompt is assembled from:

- Base system instructions.
- Tenant prompt pack (brand voice, behavior).
- Domain pack (optional constraints/tool hints).
- User context summary.
- Recent session memory (window + summarized older context).
- Current user message.

### Prompt Versioning

- `prompt_pack_id`, `version`, `checksum`.
- Supports canary rollout and rollback.

## Memory Strategy

- Short-term memory: recent turns (configurable N/token window).
- Summarized memory: condensed history for long sessions.
- Long-term preferences: optional key-value profile store.
- Retention: policy-driven per tenant with delete/export support.

## Policy and Safety

- Input checks: injection patterns, unsafe content, malformed payloads.
- Output checks: policy violations, hallucination risk, restricted advice classes.
- Tool policy: allowlist plus parameter validation.
- Optional domain guardrails (finance/health/legal and others).
- If uncertain, ask for clarification rather than fabricating facts.

## Project Folder Structure (Reference)

```text
/chatbot-platform
  /apps
    /api-gateway
    /orchestrator
    /worker
  /packages
    /sdk-js
    /openapi
    /policy-engine
    /prompt-manager
    /tool-runtime
  /infra
    /terraform
    /k8s
  /docs
    /architecture
    /api
    /runbooks
```
