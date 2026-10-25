# Real voice integration — inspection and next steps

Inspected 2026-10-25. Status: provider integration pending dedicated credentials. No live voice test or outbound call has been performed. Original company files were read only. The user elected to supply dedicated credentials in the standalone product's `.env`.

## What exists

- `app/main.py`, `app/store.py`: FastAPI dashboard API, SQLite records, agent/contact/workflow configuration, sessions, transcripts and outcomes.
- `app/engine.py`: deterministic DemoProvider. It does not run an LLM. The configured system prompt is stored but not interpreted.
- `static/app.js`: typed simulated conversations and optional local speech synthesis of existing transcripts. No microphone capture or real speech recognition.
- Original `voicebot/server/bot.py`: Pipecat cascade, STT selection, LLM failover, TTS selection, context aggregation, VAD, interruption controls, timeouts and WebRTC/telephony transports.
- Original `bifrost_stt.py`, `bifrost_tts.py`, `fallback_sarvam_tts.py`, `elevenlabs_fallback.py`, `voice_gate.py`: reusable provider/audio components. Bifrost adapters use a company gateway by default; authorization to reuse source does not establish authorization to use its hosted services.
- Original domain prompts, guards, customer cards, reporting, WhatsApp and Slack are tied to company operations. Extract the voice components without importing those actions into product startup.

The original declares Python >=3.12,<3.13 and Pipecat 1.10.0. Its existing environment is Python 3.12. Preserve that runtime boundary initially; do not install dependencies into the original environment. Some audio code imports audioop, which is absent from newer Python standard libraries.

## Modes

| Mode | Audio/AI | Telephone network | Current status |
|---|---|---|---|
| Simulation | Scripted text; optional local playback | None | Implemented; no fresh runtime verification in this inspection |
| Browser voice | Browser mic/speaker → WebRTC → server STT → LLM → TTS | None | Supported in original architecture; not integrated into product |
| Phone call | Provider audio transport to same server pipeline | Exotel/Plivo or other provider | Not integrated or authorized to dial |

Browser voice removes the need for a telephone provider, not the server or paid AI services. Local microphone access uses localhost; hosted browsers need HTTPS and permission. Production WebRTC may require TURN for restricted networks.

## Dedicated configuration needed

Save the file at `outputs/relay-voice/.env` (relative to the workspace). None was present at inspection. `.gitignore` already excludes `.env`. Do not copy the original environment wholesale.

Recommended first route, using providers already present in the original:

| Service | Original environment names | Required details |
|---|---|---|
| Streaming STT | ASSEMBLYAI_API_KEY, ASSEMBLYAI_MODEL, ASSEMBLYAI_LANGUAGE_CODES | Dedicated key, enabled streaming model, target languages |
| LLM | GROQ_API_KEY, GROQ_MODEL | Dedicated key and exact enabled model ID |
| Direct TTS | SARVAM_API_KEY, SARVAM_MODEL, SARVAM_VOICE, SARVAM_TTS_ROUTE | Dedicated key, enabled model and compatible voice; route direct |
| Optional alternate LLM | GOOGLE_API_KEY, GOOGLE_MODEL | Only if chosen instead of Groq or as explicit fallback |
| Optional alternate TTS | ELEVENLABS_API_KEY, ELEVENLABS_MODEL, ELEVENLABS_VOICE_ID | Only if chosen as fallback |
| Optional approved gateway | BIFROST_URL, BIFROST_VK, BIFROST_MODELS; SARVAM_BIFROST_VK for speech route | Exact base URL, auth scheme, allowed models, network requirements and independent-product permission |

All model names in source are historical defaults, not account verification. Provide API documentation/sample requests for any custom gateway. Do not supply Exotel, Plivo, Metabase, Slack or WhatsApp credentials for the browser milestone.

Copy these fields into your dedicated `.env` alongside existing application settings. Empty values are intentional. The current dashboard does not consume these voice settings yet; this is a configuration contract for the pending integration.

```dotenv
ASSEMBLYAI_API_KEY=
ASSEMBLYAI_MODEL=
ASSEMBLYAI_LANGUAGE_CODES=hi,en
GROQ_API_KEY=
GROQ_MODEL=
SARVAM_API_KEY=
SARVAM_MODEL=
SARVAM_VOICE=
SARVAM_TTS_ROUTE=direct
```

Use English only if desired by setting language codes accordingly; language support must match the selected model. The current dashboard agent schema only accepts English and needs extension for Hindi/Hinglish.

## Integration sequence

1. Validate dedicated provider configuration and billing limits without logging secrets or response bodies containing sensitive data. Probe the selected services using synthetic inputs.
2. Extract a Python 3.12 voice worker with explicit STT/LLM/TTS selection. Reuse the original streaming setup, context aggregation and voice gate. Avoid implicit company endpoints and silent provider changes.
3. Create authenticated, origin-checked browser sessions bound to an immutable agent/context snapshot and call ID. Use session-owned histories and cleanup; do not rely on process-global last-call state.
4. Add microphone start/stop, permission and playback errors, connection state, interruption handling, and end-session cleanup to the existing Studio.
5. Persist finalized user speech and assistant speech actually delivered; distinguish generated-but-interrupted text. Save errors, timing, provider/model identifiers and explicit mode without storing credentials or raw audio by default.
6. Save structured discovery/outcomes from the sales script. Label requested callbacks separately from scheduled callbacks. Derive no successful appointment from an unexecuted tool.
7. Keep simulated, browser and telephone sessions filterable in history/analytics. Real dialing stays unavailable until the telephony milestone is expressly authorized.

## Acceptance evidence required before calling the demo ready

- Valid STT, LLM and TTS requests with the configured accounts; missing keys, invalid auth, quota, timeout and disconnect errors surfaced without secret leakage.
- Actual browser microphone permission granted/denied, no input device, audible playback and browser autoplay restriction recovery.
- At least one multi-turn human microphone conversation; verify answer retention, business context, interruption, corrections and no repeated discovery questions.
- Measure speech-end → first audible response p50/p95; report observations rather than promise a latency number.
- Two independent sessions cannot mix context. Closing/reloading a tab and idle/max duration expiry release provider sessions and prevent orphan billing.
- History agrees with the heard conversation, including partial responses, cancellations, errors and requested next steps. Restart preserves completed history.
- Test busy, unknown booking, pricing, unsupported integrations, human request, opt-out and pilot-interest branches.
- Record which tests use synthetic media and which use a real microphone. A synthetic test cannot establish physical microphone/speaker quality.

See `SALES-DEMO-PROMPT.md` for the user-provided sales flow adaptation and `GO-TO-MARKET.md` for the proposed pilot offer.
