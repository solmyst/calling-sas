# Voice latency

Measured on 4 November 2026 from the local browser-voice backend in India, using the configured Gemini and Gnani accounts. Provider variance is expected; compare medians rather than individual calls.

## Kept optimizations

- Reuse the backend HTTP client so Gemini requests can reuse pooled connections instead of repeating DNS, TCP and TLS setup.
- Open the Gnani TTS WebSocket while Gemini generates the reply. The complete Gemini response is still used, so response quality and guardrails are unchanged.
- Avoid sending recent customer turns twice as both memory and conversation history. Older conversation memory remains available outside the recent 20-turn window.
- Explicitly request Gemini's `minimal` reasoning level. Gemini 3 cannot fully disable thinking; `minimal` is its documented lowest-latency setting.

The representative support turn improved from a 2,429 ms median to first audio to 1,682 ms after the connection changes, approximately 31% faster. Explicit `minimal` reasoning reduced the model-only benchmark from 1,505 ms to 1,161 ms median in a four-run comparison.

## Tested but not kept

- NVIDIA Nemotron Bolt reached first text faster but did not match Gemini on Hindi/Hinglish, support intent and handoff behavior.
- Streaming partial Gemini sentences into TTS did not improve first audio consistently because Gemini completes these short voice replies shortly after its first token.
- Lowering speech-end silence was not applied because it can split natural pauses and reduce transcription quality.

The stored `voice_timing` fields (`llm_ms`, `first_audio_ms`, and `total_ms`) are the production measurement source for later tuning.
