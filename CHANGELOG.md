# Changelog

## Unreleased

- Each agent now has its own Gnani voice (13 Timbre v3.0 voices in the agent editor). The six demo agents get distinct voices on upgrade, in every workspace; a voice the user already chose is kept.
- Added an optional VoiceLink phone bridge: the main account can dial +91 mobile contacts with recorded consent between 9 am and 9 pm India time. Call audio is converted between A-law 8 kHz and Gnani's formats, callers can interrupt the AI, and transcripts are saved and classified like browser sessions. Verified against a simulated VoiceLink call only.
- Added accounts: an unlimited main account (`ADMIN_EMAIL` + `DEMO_PASSWORD`) and self-service trial sign-up. Each trial gets a private seeded workspace with 15 minutes of live voice for 7 days, one live stream at a time, and a cap of 20 new trials per day. Existing data migrates to the main account's workspace.
- Browser-session opt-out detection now uses the same phrases as the simulator, including "remove me" and "opt out", with Hindi phrases shared both ways.
- `startup.sh` refuses local mode and no longer trusts client-supplied `X-Forwarded-For`, which bypassed the login rate limit.
- Removed the AssemblyAI/ElevenLabs speech path, `SPEECH_PROVIDER`, `/voice/turn` and non-streaming `/voice/respond`. Gnani is always used.
- Live microphone streams send no audio while paused and close after 10 minutes without detected speech (close code 4408); resuming reconnects.
- Removed the never-imported `optional/voice/voice_gate.py` and unused engine symbols.
- Simulated-turn retries cache only the call ID instead of a full call copy per turn.
- Added automatic Groq-to-Gemini failover for rate limits and transient capacity failures, with a cooldown circuit and per-stage ASR, LLM, and TTS timing.
- Reduced the measured Gnani speech-end setting from 600 ms to 500 ms after a live synthetic comparison lowered final-transcript wait by about 215 ms across English and Hindi samples.
- Added a selectable Groq Qwen conversation backend with non-reasoning dialogue mode, backend-only authentication, and explicit Gemini configuration fallback.
- Added a prefetched, language-matched Gnani backchannel to cover slow-response gaps without delaying model generation or polluting transcripts.
- Constrained Gemini voice replies to the documented `minimal` reasoning level and reinforced final opt-out and no-tool checks.
- Reduced browser-call response latency by reusing model connections and preparing Gnani speech generation in parallel with Gemini.
- Removed duplicate recent transcript content from model requests while retaining older session memory.
- Added lifecycle cleanup and regression coverage for prepared voice connections, including model failure paths.

## 0.2.0 — 2026-10-25

- Added a local push-to-talk browser voice mode with AssemblyAI transcription, Bifrost conversation generation and ElevenLabs speech.
- Connected editable agent instructions and approved business context to model sessions.
- Persisted finalized browser transcripts while retaining explicit browser/simulation mode labels.
- Added microphone, recording, provider, playback and configuration error states; telephone requests remain rejected.
- Added provider-boundary tests and verified a synthetic STT/LLM/TTS round trip against the configured accounts.

## 0.1.0 — 2026-10-25

- Independent local product workspace, dashboard, agent configuration and fictional contact management.
- Interactive call simulations with callbacks, handoffs, refusal, consent, opt-out and voicemail handling.
- Persistent history, transcripts, exports, configuration snapshots, analytics and workflow follow-up tasks.
- Authorized reuse of the original privacy filter, voicemail detection and optional audio gate.
- Environment configuration, local/hosted-demo authentication boundaries, backups and VM preparation.
- Source audit, architecture, pitch guide, roadmap and verification report.

No live telephony, connected AI model or production deployment in this release.
