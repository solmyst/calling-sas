# Voice latency

Measured on 4 November 2026 from the local browser-voice backend in India, using the configured Gemini and Gnani accounts. Provider variance is expected; compare medians rather than individual calls.

## Kept optimizations

- Reuse the backend HTTP client so Gemini requests can reuse pooled connections instead of repeating DNS, TCP and TLS setup.
- Open the Gnani TTS WebSocket while Gemini generates the reply. The complete Gemini response is still used, so response quality and guardrails are unchanged.
- Avoid sending recent customer turns twice as both memory and conversation history. Older conversation memory remains available outside the recent 20-turn window.

The representative support turn improved from a 2,429 ms median to first audio to 1,682 ms after the changes, approximately 31% faster. A two-turn API integration run recorded 2,577 ms cold and 1,815 ms warm to first audio.

## Tested but not kept

- NVIDIA Nemotron Bolt reached first text faster but did not match Gemini on Hindi/Hinglish, support intent and handoff behavior.
- Streaming partial Gemini sentences into TTS did not improve first audio consistently because Gemini completes these short voice replies shortly after its first token.
- Lowering speech-end silence was not applied because it can split natural pauses and reduce transcription quality.

The stored `voice_timing` fields (`llm_ms`, `first_audio_ms`, and `total_ms`) are the production measurement source for later tuning.
