# Architecture

## Implemented local product

Browser (buildless ES modules) → same-origin FastAPI API → transaction service → SQLite WAL.

`app/engine.py` contains the `CallingProvider` protocol, deterministic `DemoProvider`, and fail-closed `LiveCallingDisabled`. The web process does not import Pipecat or the original company checkout. Browser voice uses server-side Gnani STT/TTS and the configured conversation-model gateway. No telephony SDK, carrier adapter, durable scheduler or outbound dialing operation is installed. Backend credentials are never returned to the browser.

- `app/main.py`: validated request models, authentication, origin/host boundary, agent/contact/workflow APIs, call state transitions, tasks and exports.
- `app/store.py`: SQLite transactions and request deduplication. `BEGIN IMMEDIATE` serializes writes, including opt-out state and workflow creation.
- `app/engine.py`: simulation decisions, redaction before persistence, per-call configuration and transcript.
- `app/reused/voicemail.py`: extracted original machine-greeting detector, used by the simulation engine.
- `app/reused/redaction.py`: exact original privacy redactor; engine adds email masking.
- `app/seed.py`: minimal demo participant and versioned agent templates, without fabricated activity history.
- `app/gnani.py`, `app/voice.py`, `app/vad.py`: speech/model adapters and Silero VAD; streaming microphone and synthesis connections remain server-authenticated.
- `app/memory.py`: bounded, redacted per-conversation customer notes and interrupted-answer context.
- `app/requests.py`: post-call extraction validation, optimistic review revisions, local leads and follow-up tasks.
- `static/voice-session.js`, `pcm-capture.js`, `request-review.js`: microphone lifecycle, PCM framing, automatic interruption and request-review UI.
- `static/ui.js`, `views.js`, `forms.js`, `app.js`: escaped rendering, navigation, forms, API client and interaction state.
- `optional/voice/voice_gate.py`: original audio gate preserved for future Pipecat worker; not imported or installed by the demo.

## Storage and lifecycle
Records use `(kind,id)` primary keys and JSON bodies. Kinds: agents, contacts, calls, workflows, tasks, leads, meta. Structured business requests and revision/audit metadata live inside their call record. A separate request table holds idempotency results. The schema is intentionally small for a single operator; it is not a normalized multi-tenant schema.

Start → in_progress → completed or cancelled. Completed calls cannot accept turns. Agent/contact snapshots preserve the context in which a conversation happened. Opt-out atomically marks the contact do-not-call. Positive final outcomes require an affirmative response; unclear responses request confirmation. Completion creates a local next-step task. No external calendar booking, human transfer or message is claimed.

Interactive calls persist every turn. A page reload can resume a call through History → details → Resume. Workflow runs execute scripted happy-path responses for eligible contacts; each run uses a request ID. Retrying that ID returns the original result. A deliberate new run has a new ID and creates another batch. There is no automatic scheduling or cooldown in this local demo.

Metrics are derived from persisted calls. Success = qualified, confirmed or resolved. Cards are all-time; chart dates are UTC. Duration measures demo elapsed wall time, including operator typing; seed durations are synthetic. Batch simulations may have a duration of 0 seconds. These are not production voice latency or conversion measurements.

## Earlier plan for preserving the original voice engine
The current browser pipeline uses direct provider adapters and does not require Pipecat extraction. The following is an optional future telephony-worker plan, not a description of unfinished browser voice:

1. Introduce immutable call context with agent prompt, approved business context, language, tools and contact consent reference.
2. Replace imports of company KYC, WhatsApp, remarks, Slack and Metabase functions with injected action/data adapters. No internal endpoint defaults.
3. Keep provider failover, VAD/interruption policies, TTS fallback, guards and timeout logic. Pin Python 3.12 and the validated Pipecat version in that worker independently of the control plane.
4. Replace trace `_LAST` and shared mutable domain state with call-scoped state. Emit events keyed by workspace ID and call ID.
5. Translate worker events into started, transcript_delta, turn_completed, outcome, failed and ended events in the durable call store.
6. Validate with synthetic audio and provider sandboxes; only then enable approved live origination.

## Future telephony adapter contract
Separate call origination from media streaming. An Exotel adapter will receive a validated `CallRequest` with workspace, call ID, agent version, destination, consent evidence and an idempotency key. It must require all of: installed adapter, environment enablement, per-workspace approval, per-request live authorization, verified caller ID, destination allowlist in pilot, calling-hours/opt-out enforcement and rate/budget limits. Provider credentials stay server-side.

Return the provider call ID; never treat HTTP acceptance as an answered or successful call. Validate webhook signatures, timestamps and replay keys; reconcile duplicate/out-of-order events. A timeout after origination is “unknown”, not permission to retry. Stream audio into the extracted Pipecat worker and record an explicit provider failure when necessary. Real-call and demo records remain separately queryable.

## Scale and commercial boundaries
The current release is one workspace and one process. Before multi-customer hosting: Postgres with tenant keys and enforced access controls, migrations, authenticated users/roles, job queue and durable workers, webhook verification, secrets manager, encrypted backups, retention/deletion rules, audit events, billing metering and incident response. Do not point this demo at real customer datasets or present it as a production telephony service.

## Post-call request boundary

The request router is covered by the existing `/api/` password/origin middleware. AI suggestions must cite a customer turn and an exact quote/value; the model sees customer statements as data. It cannot set a booking status or execute a tool. Operator-reviewed fields use optimistic revisions. Model calls run outside the database transaction and cannot overwrite intervening edits. Local lead/task writes share one SQLite transaction and deterministic call-derived IDs. Eligibility is checked again at follow-up time. Calendar and CRM are explicitly disabled. See [request contract and verification](REQUEST-REVIEW.md).
