# Universal Chatbot API - API Reference (v1 + v2)

## Base and Versioning

- Base path: `/v1`
- Backward compatibility is preserved within major version `v1`.
- Use idempotency for write requests with `Idempotency-Key`.

## Headers

- `Authorization: Bearer <jwt_or_service_token>`
- `Content-Type: application/json`
- `Idempotency-Key: <uuid>` (recommended for POST requests)

Note: This platform is self-hosted and open-source-only. No external model provider API key is required.

## Endpoints

### `POST /v1/chat`

Main entrypoint for conversational responses.

Behavior requirements:

- Handles noisy input (typos, shorthand, informal grammar) via server-side normalization.
- Produces user-specific, account-grounded responses when `tenant_id` and `user_id` are authenticated.
- Returns clarifying prompts when required account data is missing.

Request example:

```json
{
  "tenant_id": "tnt_123",
  "user_id": "usr_456",
  "session_id": "ses_789",
  "message": {
    "role": "user",
    "content": "Can I reduce my monthly expenses?"
  },
  "channel": "web",
  "stream": true,
  "strict_grounding": true,
  "context": {
    "locale": "en-US",
    "timezone": "Asia/Kolkata"
  },
  "metadata": {
    "app_version": "1.2.0"
  }
}
```

Response example (non-stream):

```json
{
  "request_id": "req_abc",
  "trace_id": "trc_xyz",
  "session_id": "ses_789",
  "message": {
    "role": "assistant",
    "content": "Yes. Based on your recent spending, you can start by reducing dining and subscriptions by 10-15%.",
    "citations": [
      { "source_type": "tool", "source_id": "tool.spending_summary", "timestamp": "2026-04-17T10:20:00Z" }
    ]
  },
  "confidence_score": 0.87,
  "needs_clarification": false,
  "missing_data_fields": [],
  "grounding": {
    "mode": "client_data_first",
    "account_scoped": true
  },
  "usage": {
    "input_tokens": 912,
    "output_tokens": 134,
    "model": "qwen2.5-7b-instruct"
  },
  "warnings": []
}
```

### `POST /v2/research`

V2 research endpoint with provider switching behind feature flags.

Feature flags:

- `CHATBOT_ENABLE_V2=true` to enable V2 routes.
- `CHATBOT_V2_RESEARCH_PROVIDER=skeleton|external` to select backend provider on the same endpoint.

Request example:

```json
{
  "tenant_id": "tnt_demo",
  "user_id": "usr_alex",
  "query": "How can I improve monthly cash flow?",
  "sources": [
    { "url": "https://www.investopedia.com/terms/b/budget.asp" }
  ],
  "max_sources": 3,
  "verbose": false
}
```

Response example:

```json
{
  "request_id": "req_abc123",
  "trace_id": "trc_xyz123",
  "tenant_id": "tnt_demo",
  "user_id": "usr_alex",
  "summary": "Alex, priority improvement: focus on the top two actions below for how can i improve monthly cash flow?.",
  "recommendations": [
    "Prioritize top 3 tasks",
    "Reduce context switching"
  ],
  "explanation": null,
  "confidence_score": 0.82,
  "warnings": []
}
```

### `POST /v1/sessions`

Creates/resumes a session and returns `session_id`, TTL, and memory config.

### `GET /v1/sessions/{session_id}`

Fetch session metadata and status.

### `POST /v1/tools/register`

Registers tenant-scoped tools.

Request example:

```json
{
  "tenant_id": "tnt_123",
  "tools": [
    {
      "name": "get_user_profile",
      "description": "Fetch profile by user id",
      "input_schema": {
        "type": "object",
        "properties": {
          "user_id": { "type": "string" }
        },
        "required": ["user_id"]
      },
      "timeout_ms": 3000
    }
  ]
}
```

### `POST /v1/webhooks`

Registers event callback endpoint and webhook secret.

### `GET /v1/capabilities`

Returns tenant feature flags (streaming, tools, citations, memory, multimodal flags).

### `GET /v1/usage`

Returns usage and billing metrics by date/tenant/model.

## Streaming Protocol (SSE)

- Content type: `text/event-stream`
- Event types:
  - `response.started`
  - `response.delta`
  - `tool.called`
  - `tool.completed`
  - `response.completed`
  - `response.failed`
- Each event includes `request_id`, `trace_id`, and `timestamp`.

## Error Handling

Standard error envelope:

```json
{
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Too many requests for tenant tnt_123",
    "request_id": "req_abc",
    "retry_after_ms": 1200
  }
}
```

Common error codes:

- `INVALID_REQUEST`
- `UNAUTHORIZED`
- `FORBIDDEN`
- `NOT_FOUND`
- `CONFLICT`
- `RATE_LIMIT_EXCEEDED`
- `UPSTREAM_MODEL_TIMEOUT`
- `TOOL_EXECUTION_FAILED`
- `POLICY_BLOCKED`
- `INTERNAL_ERROR`

## Integration Quickstart

1. Create tenant and configure auth token issuance (JWT/service token).
2. Register tools/adapters (optional but recommended).
3. Configure prompt pack and policies.
4. Create session.
5. Send first chat request (streaming or non-streaming).
6. Subscribe to webhooks for async events.
7. Use `request_id` and `trace_id` for support/debug.
8. Ensure your adapter returns account-scoped data for the authenticated `user_id`.

Minimal curl example:

```bash
curl -X POST https://api.example.com/v1/chat \
  -H "Authorization: Bearer $APP_TOKEN" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: 4f3b8f29-6c5b-4a6a-9f7d-a061e5d11f0c" \
  -d '{
    "tenant_id":"tnt_123",
    "user_id":"usr_456",
    "session_id":"ses_789",
    "message":{"role":"user","content":"Help me plan this week"},
    "stream":false
  }'
```

## SDK Requirements (v1)

- JS/TS SDK first.
- Features:
  - typed request/response models
  - automatic retries (safe status codes only)
  - SSE helper
  - idempotency helper
  - middleware hooks for logging
- Include 3 sample apps:
  - web app integration
  - backend service integration
  - tool registration plus invocation flow

## Open-Source Deployment Notes

- API contracts remain unchanged across open-source model swaps.
- `usage.model` should report the active self-hosted model identifier.
- Add model fallback ordering in tenant config (for example: small -> medium -> large OSS models).
