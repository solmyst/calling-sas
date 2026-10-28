# Gnani validation — 28 October 2026

## Passed

- 34 automated tests, locally and on Ubuntu/Python 3.12 on the Azure VM.
- English and Hindi synthesis → raw PCM → realtime recognition, using synthetic
  audio. Both sentences returned intelligible matching text. This is a smoke test,
  not a statistical recognition-accuracy benchmark.
- Browser STT proxy readiness and normalized transcript using synthetic microphone
  frames and a temporary database.
- All four flows: actual Bifrost reply, actual Gnani streaming synthesis, persisted
  transcript, ended session and follow-up review outcome. Test records used a
  temporary database, not the customer workspace.
- Worklet framing at 16 kHz and 48 kHz input: 31 full 1,024-byte frames per second
  plus the retained partial frame, matching 512-sample/32 ms output cadence.
- Deployed HTTPS login, four scenarios, selected Gnani services, static UI, and
  no captured browser console errors/warnings on the demo hub.
- VM Gnani TTS and Hinglish STT readiness after fixing the live language-header
  incompatibility. InterviewAce, Nginx and Relay Voice remain active.

## Timing samples

| Synthetic sample | Model response | First server audio chunk | Complete server stream |
| --- | ---: | ---: | ---: |
| Sales | 1,317 ms | 1,895 ms | 5,581 ms |
| Business helper | 1,159 ms | 2,271 ms | 5,739 ms |
| Customer care | 1,046 ms | 1,467 ms | 4,087 ms |
| Appointment intake | 1,176 ms | 1,927 ms | 5,941 ms |

Gnani-only English/Hindi first-audio samples on the Mac were 507/369 ms. The
VM Hindi TTS sample received first audio at 431 ms. These are single synthetic
samples, not p50/p95, SLAs, or a before/after speed claim. Server first-audio timing
excludes end-of-speech detection, browser/network buffering and speaker playback.
The stream's completion time is not how long the customer waits before playback:
playback can begin with the first chunk.

## Problems caught and addressed

- Shared sales instructions incorrectly drove support/booking: separated by use
  case and added four specific prompts and approved contexts.
- Sales model overpromised automatic calling/booking: strengthened global rules;
  a repeat live reply proposed a pilot rather than claiming an existing connection.
- Full-file reply playback: added incremental raw PCM playback for Gnani.
- Gnani locale-list documentation differed from live API: the service rejected
  `hi-IN,en-IN`, so Hinglish uses `hi-IN` with `codemix`.
- Interrupted/failed sessions could lose context or remain muted: save generated
  text before synthesis, cancel playback on end/logout, and release session state.
- Demo/source/provider labels and public-site links were stale: updated them for
  the four scenario experiences and the current VM URL.

## Still requires a human listening session

Microphone permission and selected audio device, echo from speakers, real accents,
background noise, extended Hinglish switching, and perceived prosody must be checked
with a person in a real browser. Synthetic audio passing STT is not proof those
conditions work. This baseline predates automatic interruption; see the updated
[Silero barge-in and memory validation](BARGE-IN-MEMORY.md).
Generated transcript text is not proof that every word was heard during interruption.

Test several Gnani voices and delivery settings before claiming a best voice.
Audio tags are optional and off by default pending a listening comparison. The
public marketing source points to the current VM and four demo experiences.
The authenticated demo itself is deployed on the VM.

## Operations

The production key is stored server-side in `/etc/relay-voice.env` (root:relay, 0640).
The database remains relay-owned with mode 0600. The pre-update configuration,
code and SQLite backup are in `/var/backups/relay-voice/gnani-20261028` (root-only).
The original company source was not edited. No outbound telephone call was made.
