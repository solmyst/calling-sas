# Voice latency

Measured on 4–5 November 2026 from the local browser-voice backend in India, using the configured Gemini and Gnani accounts. Provider variance is expected; compare medians rather than individual calls.

## Kept optimizations

- Reuse the backend HTTP client so Gemini requests can reuse pooled connections instead of repeating DNS, TCP and TLS setup.
- Open the Gnani TTS WebSocket while Gemini generates the reply. The complete Gemini response is still used, so response quality and guardrails are unchanged.
- Avoid sending recent customer turns twice as both memory and conversation history. Older conversation memory remains available outside the recent 20-turn window.
- Explicitly request Gemini's `minimal` reasoning level. Gemini 3 cannot fully disable thinking; `minimal` is its documented lowest-latency setting.
- Prefetch a short same-voice acknowledgement while the opening plays. If a response still has not arrived after 650 ms, the browser uses it as a conversational backchannel while the conversation model and Gnani continue in parallel. It is limited to alternating turns and suppressed for opt-outs.
- Support Groq Qwen 3.8 27B in instruct mode (`reasoning_effort=none`) as a selectable conversation backend. The measured median model reply was 258 ms and median first Gnani audio was approximately 714 ms across the successful end-to-end runs. The free tier is for a single demo flow, not production concurrency.
- Route Groq rate limits, capacity errors, server errors and transport timeouts to the same Gemini prompt contract. A cooldown circuit sends later turns directly to Gemini during the provider retry window.
- Use a 500 ms Gnani speech-end window. A live synthetic comparison against 600 ms reduced clip-end-to-final-transcript time from 534 to 321 ms in English and from 765 to 546 ms in Hindi. Natural-pause behavior still needs production monitoring.

The representative support turn improved from a 2,429 ms median to first audio to 1,682 ms after the connection changes, approximately 31% faster. Explicit `minimal` reasoning reduced the model-only benchmark from 1,505 ms to 1,161 ms median in a four-run comparison.

The configured Gemini fallback was also rechecked with three live English support turns on 5 November. Median complete-model time was 1,396 ms, median first Gnani audio was 1,644 ms, and the measured TTS portion was 288 ms. English, Hindi, Hinglish, and exact opt-out scenarios returned usable guarded responses in the fallback validation.

## Tested but not kept

- NVIDIA Nemotron Bolt reached first text faster but did not match Gemini on Hindi/Hinglish, support intent and handoff behavior.
- Streaming partial Gemini sentences into TTS did not improve first audio consistently because Gemini completes these short voice replies shortly after its first token.
- Sending a local Silero `commit` after 384 ms of silence was not applied because it can split natural pauses before Gnani's 500 ms endpointing decision.

The stored `voice_timing` fields separate `asr_ms`, `stt_provider_ms`, `llm_ms`, `tts_first_audio_ms`, `first_audio_ms`, and `total_ms`. Use production p50 and p95 values to decide which stage to tune next.

## Three-stage production plan

1. **STT:** Keep the Gnani WebSocket open, send 16 kHz mono PCM in 1,024-byte frames at 32 ms cadence, and measure the 500 ms endpoint against real pauses and corrections. Gnani emits only final transcripts, so speculative partial-text LLM requests are not used.
2. **LLM:** Keep Groq primary and Gemini as the circuit-breaker fallback. Gemini uses minimal reasoning through the OpenAI-compatible gateway. Stable guardrails and business context precede the changing timestamp and conversation turns to maximize implicit prefix-cache eligibility. Short prompts below Gemini's cache minimum will not receive cache hits.
3. **TTS:** Open the Gnani TTS WebSocket while the LLM is generating, send one synthesis request at a time, and play raw PCM chunks immediately. The saved `tts_first_audio_ms` measures the remaining synthesis delay independently from model generation.
