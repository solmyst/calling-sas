# Roadmap

## 0.1 — Local demo (this delivery)
Independent dashboard and API; configurable agents; fictional contacts and consent flags; interactive simulations; workflow runs; transcripts; analytics; task tracking; server-side privacy filter; tests; VM templates. No company-service dependencies.

## 0.2 — Current browser voice and reviewed requests
Gnani streaming STT/TTS, the configured model, exact PCM framing, Silero automatic interruption, noise-suppression requests, persistent conversation memory, four templates and an authenticated Azure demo are implemented. Physical-room acoustics still require listening checks; synthetic validation is not a quality SLA.

Structured requests now support post-call AI suggestions with customer evidence, manual corrections, assigned owners, optimistic revisions, an audit trail and workspace-local leads/tasks. Calendar/CRM actions remain disabled by owner preference. This latest slice has local API and real-browser validation and requires a separate deployment step.

Next: per-turn end-to-end latency and usage measurement, a representative language/acoustic evaluation set, and one approved sandbox calendar/CRM when the owner selects and configures them. Keep public anonymous voice access closed until restricted sessions, duration/rate/concurrency limits and spending caps are implemented.

## 0.3 — Exotel / telephony pilot
Implement origination and media adapters, signed webhooks, replay protection, idempotent reconciliation, calling windows, opt-out/consent evidence, destination allowlist, rate limits and spend limits. Require explicit live-call approval. Validate recording/disclosure policy and provider terms for the actual use case. Measure outcomes against a small consenting pilot baseline.

Exit gate: owner-approved pilot, controlled test calls, verified hangup/cancellation, failover, escalation routing and incident controls.

## 0.4 — Commercial foundation
Postgres schema and migrations, tenant isolation, real user accounts, roles, audit trail, retention/deletion, customer onboarding, quotas and billing. CRM/calendar actions need idempotency, failure reporting and least-privilege credentials. Add a durable scheduler, job queue and worker autoscaling. Protect prompts, customer context and recordings by tenant.

Exit gate: security review, tenant-boundary tests, backup restore exercise, load tests, SLOs, support and incident process, legal/commercial documentation.

## 1.0 — Vertical product
Choose one segment (lead qualification, reminders, support or follow-up). Ship evaluated templates, reliable multilingual voices, operational dashboards, human transfer, customer-specific integrations, measured unit economics and a repeatable sales/onboarding process. Expand into adjacent verticals after a successful pilot.

Pricing remains a hypothesis: platform access + metered usage + optional implementation support. Do not set margins until actual telephony, speech and model costs are measured.
