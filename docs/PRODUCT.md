# Relay Voice — product brief

A voice operations workspace for businesses that need consistent lead qualification, reminders, support triage, follow-ups and sales conversations. The immediate release is a pitch-ready, single-workspace local demonstration; commercial multi-tenant service is a subsequent release.

## Customer problem
Small operations teams cannot personally follow up every inbound lead or appointment. They need a configurable conversation, visibility into outcomes, and a clear path to human follow-up. A raw voice pipeline does not supply these operational controls.

## Release acceptance
- Create and edit an agent's prompt, business context, opening and qualification question; show exactly which configuration a call used.
- Create/edit contacts, capture consent and do-not-call status, reject ineligible calls server-side.
- Start a clearly labeled simulation, choose guided or typed customer responses, and persist each turn. No network telephony calls.
- Complete, cancel, hand off, schedule follow-up, or opt out; preserve outcomes across reloads.
- Configure a workflow by agent, contact segment, and outcome action; simulate a batch without duplicates from repeated request IDs.
- Show truthful metrics computed from persisted demo calls, with synthetic seed history explicitly marked.
- Export redacted transcripts; protect API mutations from cross-origin requests; require authentication outside local mode.
- Run without company services, keys, datasets, assets, or the original checkout.

## User stories
An operator configures an agent for a business, adds a consenting contact, rehearses the conversation, and reviews the transcript and outcome. A manager runs a segment workflow and inspects completion and handoff counts. A founder demonstrates this sequence in under five minutes without a telephony account.

## Scope
P0: dashboard, agent editor, contact management, simulation studio, history, transcript export, workflows, analytics, settings, SQLite persistence, local authentication option, disabled live provider, setup and VM templates.
P1: browser voice playback, deterministic objections and opt-outs, seed data, reusable privacy filter.
P2: licensed Pipecat runtime extraction, Exotel, validated webhooks, queue workers, tenant isolation, RBAC/SSO, billing, CRM/calendar integrations, consent policy by jurisdiction, retention automation, load testing.

## Demo success measures
All automated acceptance tests pass. A new call appears in history and analytics after completion. Configuration and contact edits survive restart. Real call requests fail even if flags are enabled. No source-file content changes in the company project.

## Open decisions
Founder: final brand, target vertical, pricing, contractual code ownership evidence. Engineering: live provider and model accounts, voice/media requirements, tenant architecture. Production blockers: authentication and authorization beyond a shared demo password, per-tenant storage, provider validation, security and operational review. No revenue, latency, conversion or cost claims are inferred from simulations.
