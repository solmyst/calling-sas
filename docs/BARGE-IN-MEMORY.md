# Natural interruption and conversation memory

## Behavior

While the AI speaks, the microphone continues streaming. The browser requests
echo cancellation, noise suppression and automatic gain control, and applies an
85 Hz high-pass filter for rumble. Silero v5 classifies 16 kHz PCM on the backend.
Sustained speech stops local playback, aborts the response request and cancels
server-side generation. Gnani transcribes the full utterance, including its start,
and the next AI reply uses those words. No interrupt button is needed.

Silero runs locally on the VM through ONNX Runtime. Its model and original MIT
license are bundled under `app/models`; no runtime download, API key or separate
VAD service is required. Recurrent state is isolated for each microphone connection.
The inference session is shared, uses one CPU thread, and has no external telemetry.

## Speech confirmation and noise

- Frames contain 512 mono int16 samples at 16 kHz: 1,024 bytes every 32 ms.
- Speech confidence must be at least 0.72 during playback (0.58 otherwise), with
  RMS at least 0.008 and 128 ms of confirmed speech. Up to 64 ms of small gaps is
  tolerated so a natural word boundary does not reset the confirmation window.
- After 384 ms without speech, the local utterance detector resets.
- Browser echo cancellation prevents the AI's loudspeaker output from feeding
  back into the microphone. Silero detects speech; it is not an echo canceller or
  a noise-removal model. Actual browser/OS support and microphone placement matter.
- Native browser noise suppression and the high-pass filter clean the input;
  short transient sounds do not automatically cause an interruption.

Noise, competing speakers and poor acoustic echo cancellation can still cause a
false interruption. If words cannot be recognized, the user may need to repeat.
The Gaussian-noise test is a regression check, not a real-room noise benchmark.

## Memory and interrupted answers

Customer statements are redacted and saved in the same conversation record as
the transcript. Up to 32 statements are retained, within the existing session turn
limit. Bounded excerpts supplement the latest 20 turns in the LLM context, without
an extra model call. Instructions prefer the latest correction and avoid asking
for information already provided. These notes are quoted customer data, not
trusted system instructions.

An interrupted answer retains its generated text for audit and receives
`delivery_status=interrupted`. It is replaced with an interruption marker in the
model's conversational context. No character-by-character audible alignment is
claimed. The model does not assume that an unfinished answer was heard in full.

The interruption endpoint uses response IDs. An old response cannot overwrite a
newer turn or restart playback after cancellation. Even an interrupted request
that has not reached generation yet can preserve its customer input. Repeated
response IDs are rejected to prevent duplicate transcript entries.

Memory persists through a server/page restart and voice sessions can resume from
History without replaying the introduction. Memory is scoped to one conversation:
starting a new call does not silently import another call's or customer's history.
There is no external memory database or additional retention policy.

## Small reliability improvements

- A transient STT disconnect gets two reconnect attempts with backoff; the UI asks
  the user to repeat anything said while disconnected.
- New microphone sessions release the previous audio graph and tracks. End,
  logout and page exit stop playback and capture.
- Pause microphone remains an explicit privacy control. It sends silence and
  ignores incoming transcripts until resumed.
- Listening, understanding, thinking and interruptible playback have visible
  status text; interrupted transcript entries are labelled.

## Reproducing the checks

```sh
python -m pip install -r requirements.lock
python -m unittest discover -s tests -v
node --test tests/voice-session.test.mjs
```

The tests use the real bundled Silero model to reject silence/seeded noise and
detect a synthetic speech fixture. They also check immediate playback cancellation,
stale-chunk rejection, preservation of interruption words, concurrent generation
cancellation, memory isolation and restart persistence.

For a paid live-provider check through an actual browser:

```sh
.venv/bin/python scripts/serve_voice_validation.py
```

Open `http://127.0.0.1:8791/voice-validation` and run the check. It injects two
synthetic corrections through a virtual microphone: first over the opening, then
over a streamed reply. Gnani STT/TTS, Silero, Bifrost, the browser audio graph,
cancel requests and memory all run through the real product pipeline. It never
opens the physical microphone. The validation server is loopback-only, uses a
separate runtime database and is not mounted by the production application.

Browser checks passed for both opening and streamed-response interruptions, with
the latest Saturday-at-two correction used by the model. With the final 128 ms
confirmation window, sample cutoffs were 366 ms and 966 ms from the start of the
synthetic audio. Earlier samples were 435/1,040 ms at 224 ms confirmation and
422/1,011 ms at 192 ms. The final configuration also passed silence, seeded-noise
and click tests. These single-sample observations are not a p95, an SLA or a
measurement of speech onset in a noisy physical room.

The Azure VM browser check also passed both interruptions and retained the latest
correction. That run measured 414 ms and 1,749 ms from synthetic audio start through
the SSH test tunnel. Network path and speech content affect these observations.

The live long-context memory check recalled a dealership, fifty weekly enquiries
and the corrected Saturday-at-two preference after the initial facts left the
recent 20-turn context. Physical microphone permissions, loudspeaker echo and noisy
rooms still need a human listening check on the actual demo device.

## References

- [Silero VAD v5.1.2](https://github.com/snakers4/silero-vad/tree/v5.1.2), including the original ONNX state/context wrapper and MIT license.
- [LiveKit turn and interruption guidance](https://docs.livekit.io/agents/logic/turns/), particularly canceling speech and avoiding unheard text in model history.
