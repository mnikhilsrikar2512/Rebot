# Documentation Index

This folder contains the production documentation split for easier maintenance and ownership.

Current product direction: user-specific and product-specific answers grounded in each client's application data, with robust handling of typo/noisy input.

Deployment mode: open-source and self-hosted only (no paid external model APIs).

## Reading Order

1. `product-rules.md` - hard rules and launch criteria for the end product.
2. `architecture.md` - system design, core concepts, and platform contracts.
3. `api-reference.md` - endpoint contracts, request/response examples, and integration flow.
4. `operations-runbook.md` - reliability, security, observability, release, and SLO guidance.
5. `personalization-test-cases.md` - QA/UAT cases for account-scoped and typo-tolerant behavior.
6. `release-notes-template.md` - reusable release notes format.
7. `CHANGELOG.md` - documentation change history by version/date.

## Document Ownership (Suggested)

- `architecture.md`: Platform/Backend lead + AI/Orchestration lead.
- `product-rules.md`: Product + Platform lead.
- `api-reference.md`: API/SDK owner.
- `operations-runbook.md`: DevOps/SRE + Security owner.

## Update Guidelines

- Keep endpoint and schema changes in sync with the OpenAPI source.
- Keep all AI/runtime dependencies compatible with open-source-only deployment.
- Update `api-reference.md` first for any contract change.
- Update `architecture.md` when components, flows, or policies change.
- Update `operations-runbook.md` when SLOs, alerts, deployment, or incident procedures change.
- Update `product-rules.md` when personalization, grounding, or noisy-input behavior requirements change.
- Include doc updates in the same PR as code changes whenever possible.

## Source of Truth

- Master legacy file: `../chatbot-api-documentation.md`
- Active maintained docs: files in this folder (`docs/`).
