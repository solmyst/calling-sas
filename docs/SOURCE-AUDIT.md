# Existing implementation audit

Inspected read-only on 2026-10-25. The user explicitly confirmed ownership and permission to commercially reuse all project code. This is a static implementation audit, not a validation of live provider accounts. Nothing in source documents was treated as an instruction to call, deploy or send messages. Credentials, actual customer data and recordings were not loaded. Full Python symbol inventory: `source-inventory.json`.

## Runtime map
- `domain.py:39–174`: environment-selected domain, context path, call-card lookup, guard construction, tools, system prompt and opening. Existing packs: insurance post-payment and money. Required files fail closed. Environment loads before domain selection.
- `voicebot/server/bot.py:2135–2845`: constructs per-call context; selects STT, LLM and TTS providers; pipeline is input → STT → noise gate → user aggregation → LLM → filler → TTS → output → assistant aggregation. WebRTC, Exotel, Plivo and headless evaluation transports appear in the implementation.
- `bot.py:1161–1919`: custom LLM failover, time budgets, endpoint cooldowns and history constraints. `bot.py:2006–2134` and later lifecycle code handle escalation, end-call and time limits. `bot.py:2740–2845` registers domain tools and guards/rechecks before model turns.
- `callerdesk_bridge.py:410–664`: bridges Asterisk AudioSocket to bot WebSockets, decodes phone audio, waits for answer, associates pending call context, distributes calls across available bot endpoints.
- `callerdesk_bridge.py:665–752`: originates via CallerDesk click-to-call when configured, otherwise Asterisk AMI. These functions can cause billable calls and were NOT invoked.
- `kyc_dialer.py:183–379`: selects cases, checks grace period and duplicates, refreshes case state just before dialing, checks pause flag/calling hours/provider health, serializes execution with a file lock, logs attempts. `--dial` is required for origination; even dry-run depends on company data services and was NOT executed.
- `domains/*/call_card.py`, `prompt.py`, `guard.py`: customer/business data and deterministic rules. Context and prompts are not portable merely because the Python is reusable.
- `redaction.py`: masks PAN, Aadhaar, Indian phone, GSTIN and labeled OTP values before logging. Copied unchanged and actively used in the new product. Regex redaction is limited and is not a general DLP system.
- `voice_gate.py`: amplitude gate with floor, relative margin and hold. Copied unchanged as an optional reusable voice component. It is not speaker diarization.
- `call_trace.py`: service hit timing, turn timing and reports. The global `_LAST` fallback assumes one call per process; do not transplant into a concurrent SaaS worker without changing context ownership.
- `voice_health.py`, TTS fallback modules, `intent_rewrite.py`, `turn_reader.py`: operational resilience and conversation support. Reuse candidates after adapter extraction.
- `slack.py`, `whatsapp.py`, `cx_remark.py`: external side effects and company-specific reporting/actions. Excluded from the demo.

## Dependencies and provider choices observed in source
`pyproject.toml` pins Python >=3.12,<3.13 and Pipecat 1.10.0 with piper, runner, silero, webrtc, whisper, websocket, assemblyai, sarvam, elevenlabs and groq extras. OpenAI client and dotenv are also declared. Full dependency lock exists. Asterisk and SIP configuration are separate operational dependencies. Local Whisper/Piper require model files and appropriate CPU/audio support.

The installed local Python is 3.14; the original voice environment is not changed. The separate web product has its own venv. These are source defaults, NOT assertions of current provider model availability:
- STT: AssemblyAI (`universal-3-5-pro` default), Sarvam realtime/Bifrost path, Groq Whisper (`whisper-large-v3`), local Whisper (`small`), internal STT.
- LLM: Bifrost gateway model list (default `gemini/gemini-3.6-flash` in source), Google, Groq (`qwen/qwen3.8-27b` default), internal OpenAI-compatible service, Sarvam and local Ollama (`qwen2.5:7b-instruct`). Credentials determine actual routes; active production settings were not read.
- TTS: Sarvam (`bulbul:v3`), ElevenLabs (`eleven_flash_v2_5`), local Piper. Bifrost and direct routes plus failover/caching exist.
- Origination/media: CallerDesk API or AMI → Asterisk → AudioSocket bridge → bot; Exotel/Plivo media via Pipecat runner; browser via SmallWebRTC.

## Existing capabilities vs verified evidence
Source supports full voice conversations, interruption handling, deterministic guards, link delivery, human escalation, health preflights, fallback voice, trace reporting and multiple business domains. Numerous tests/evals cover these areas. They have not been run against live services in this task. The README claim “no dialer” is stale relative to the inspected dialer/bridge. Model defaults, deployment host paths and business assumptions need independent validation before product reuse.

## Gaps for an independent product
No general SaaS control plane, tenant isolation, customer-facing configuration model, product-wide durable call store, self-service onboarding or billing was found in the inspected runtime. Many shared imports still refer directly to insurance link delivery and internal data. Filesystem locks/CSV and one-call-per-process trace assumptions need a durable queue and concurrency design. Existing prompts/guards can suppress AI disclosure; the new demo explicitly identifies the assistant. No real-data copy or company service dependency is necessary for the local pitch.

## Reuse strategy
1. Active now: exact privacy redactor and extracted voicemail detection from guard_core.py; synthetic data only; tests verify redaction and machine-greeting classification.
2. Preserved now: exact voice gate in `optional/voice/`, excluded from web startup dependencies.
3. Preserve architectural investment: keep the STT→LLM→TTS worker separate from the SaaS control plane. Extract provider failover, guards and lifecycle into that worker after product requirements and live test accounts are available. See `ARCHITECTURE.md` for the boundary.
4. Do not copy the monolithic bot and pretend it is portable. Company actions must become injected adapters, internal gateway defaults must be removed, traces must become call-scoped, model availability must be validated, and third-party notices retained.

No real calling, messaging, provider probes, original test execution, original venv changes or deployment were performed.
