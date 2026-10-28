# Gnani voice demos

## Configuration

Put dedicated credentials in the root `.env` (ignored by Git). Never put these in
the static site, browser JavaScript, screenshot or a commit.

```dotenv
SPEECH_PROVIDER=gnani
GNANI_API_KEY=
GNANI_STT_MODEL=prisma-v3.0
GNANI_TTS_MODEL=timbre-v3.0
GNANI_VOICE=Shivani
GNANI_SILENCE_MS=600
GNANI_SPEED=1.0
GNANI_AUDIO_TAGS=false
BIFROST_URL=https://bifrost.parkplus.io/v1
BIFROST_VK=
BIFROST_MODELS=
```

The model/voice above is a documented starting configuration, not a conclusion
that the screenshot's voice is the best voice. Select a voice supported by your
chosen model, then compare English, Hindi, Hinglish, names, numbers and dates.
Gnani supplies speech recognition and synthesis; Bifrost still supplies the LLM.
Both require valid accounts/credits and network access from the backend. Charges
depend on your account agreement; no price or concurrency guarantee is assumed.

`SPEECH_PROVIDER=legacy` retains the existing AssemblyAI/ElevenLabs integration.
Selecting `gnani` with missing credentials disables browser voice; it never silently
falls back to another paid provider.

Start with `python run.py`, open `/#demos`, choose an experience, then select Live
browser voice. Production uses the existing `/relay/` prefix and HTTPS. After
editing production configuration in `/etc/relay-voice.env`, restart the service.

## What each demo demonstrates

| Experience | Conversation | Next step |
| --- | --- | --- |
| Sales | Permission, business need, enquiry volume, relevant workflow, objection, pilot | Review pilot interest |
| Business helper | Question, clarification, approved answer, comprehension check | Answer or team follow-up |
| Customer care | Acknowledge issue, one troubleshooting step, verify, escalate | Human review when needed |
| Appointments | Service, preferred date/time, timezone, read-back | Request awaiting availability confirmation |

These four versioned templates are added to the existing workspace without
overwriting edited agents or generating fictional conversation history. Configure
your business facts and language before a customer pitch. No live calendar, CRM,
WhatsApp, refund or telephone action is claimed or executed.

## Script and delivery

Keep the script conversational: one thought, one short question, then wait. An
opening should identify the AI and establish the purpose. Give answers before
advancing the flow. Refer to what the person already said instead of repeating
questions. Hindi is written in Devanagari; familiar English terms can stay in Latin
script. Have the model speak dates and numbers as words rather than reading IDs as
large numbers. Relative appointment dates use current India time from the server.

Each agent has a neutral/warm/calm/upbeat delivery setting in Configure. Delivery
affects the conversation instructions. Optionally enable `GNANI_AUDIO_TAGS=true`
with Timbre v3 to insert one `<pauses>` cue after the first sentence. Upbeat delivery
also enables `<excited>`. Neutral, warm and calm avoid that cue. Tags are compiled
only for synthesis; saved transcripts remain plain text. Arbitrary tags from LLM
output are removed. Yawning, coughing, laughing and shouting are inappropriate for
these business templates and are not inserted. Compare tagged versus untagged audio
before enabling it for a customer demonstration.

## Audio pipeline and limits

1. Browser echo cancellation, noise suppression and automatic gain control capture
   the microphone. An AudioWorklet resamples to 16 kHz PCM, emitting 512 samples /
   1,024 bytes every 32 ms. Paused/muted input sends silence to preserve cadence.
2. The authenticated backend attaches the Gnani key to its upstream WebSocket.
   Prisma returns completed utterances and language information. The proxy exposes
   normalized events and a readiness acknowledgment, never credentials. The live
   service rejected the documentation's comma-separated locale list; Hinglish
   therefore uses the accepted single `hi-IN` locale with `codemix` formatting.
3. Bifrost receives approved context, flow-specific instructions and recent history.
4. Timbre's realtime socket produces raw 24 kHz PCM. The backend forwards chunks as
   NDJSON; the browser schedules audio immediately without waiting for the full file.
5. Session history stores generated text and measured model/first-audio/total server
   timings. Generated text does not prove the whole sentence was heard. The browser
   interrupts automatically when Silero confirms user speech. See [barge-in and memory](BARGE-IN-MEMORY.md).

Microphone permission is required. Hosted demos need HTTPS. Avoid loud speakers
next to the mic; headphones make the demonstration more reliable. The microphone
remains active during playback so you can interrupt naturally.
Replay is available for the opening/full-file legacy audio; streamed reply replay
is a future improvement. Gnani's STT sessions have a documented fifteen-minute limit.

Completed browser sessions are saved for review rather than automatically counted
as qualified, booked or resolved. Handoff and explicit opt-out wording are detected
with conservative rules; all other sessions require a human review. Those rules
are not a substitute for production intent detection or consent evidence.

## Validation

```sh
.venv/bin/python -m unittest discover -s tests -v
node --check static/app.js
node --check static/pcm-capture.js
# Calls paid speech APIs using short synthetic samples, no customer records:
.venv/bin/python scripts/check_gnani.py
```

The live smoke test writes English/Hindi audio and metadata under ignored
`runtime/`. It verifies synthesis and streaming recognition connectivity, not
subjective voice quality or recognition accuracy on real customers. A human
listening pass must test accents, interruptions, noise, microphone denial, reconnect,
Hindi/English switching, appointment corrections and the transcript after ending.

Latency targets for a pilot should be agreed from measured p50/p95 first-audible
response times. Server first-audio timing excludes endpointing, browser/network
buffering and speaker playback. No latency reduction is claimed until compared on
the same machine/network and representative utterances.

## Research informing this implementation

- [Gnani STT streaming protocol](https://docs.gnani.ai/api/STT/stt-websocket): raw PCM framing, VAD settings, ready/transcript/error events and language hints.
- [Gnani realtime synthesis](https://docs.gnani.ai/api/TTS/tts-websocket): streaming audio before completion, voice/model matching, formats.
- [Gnani audio tags](https://docs.gnani.ai/api/TTS/tts-audio-tags): expression belongs in synthesis input and is model-specific.
- [LiveKit turn-taking guidance](https://docs.livekit.io/agents/logic/turns/tuning/): endpointing, interruptions, false-interruption recovery and background noise are separate concerns.

Next priorities: benchmark voice candidates and physical-room barge-in with your
own audience; stream the LLM sentence by sentence;
add actual calendar/CRM tools with confirmation; add per-workspace rate limits,
usage billing and tenant isolation before opening a public voice playground.

For selling, start with one appointment-led service business and one workflow.
Run a five-minute demo: discovery, live scenario with an unexpected question,
correction, transcript review, then agree a small paid pilot. Compare contact rate,
requests captured, staff review time and cost per useful outcome against a baseline.
Keep setup/support as a fee and metered speech/LLM/telephony usage explicit in the
proposal until measured usage supports a fixed bundle.
