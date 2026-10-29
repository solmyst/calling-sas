# Relay Voice — 60-second Gnani Hackathon film

The film is composed in **Remotion**, using high-quality CDP/Playwright recordings of the existing Relay Voice application. No dashboard component, transcript, provider response, or successful action is mocked. The only injected elements are the visible cursor and a recording-only virtual microphone fed with generated customer speech. Narration and customer samples use the configured Gnani Timbre adapter. The conversation uses the real Gnani Prisma → Bifrost → Gnani Timbre pipeline.

**Output:** `out/giani-hackathon-demo.mp4`, 1920 × 1080, 30 fps, exactly 60 seconds, H.264 / AAC / yuv420p. Nothing is posted to social media automatically.

## Render on this Mac

From the repository root:

```sh
.venv/bin/python -m pip install -r requirements.lock -r video/requirements.txt
cd video
npm ci
npx playwright install chromium
npm run build
```

`ffmpeg`, `ffprobe`, and the macOS Swift compiler must be available on PATH. This machine already has them. On a clean Mac, install FFmpeg through Homebrew and the Apple command-line tools through the usual Xcode setup. Node 22+ is recommended; this render was verified with Node 26. The review uses Apple's local Vision OCR; it does not upload frames to a vision service.

The root `.env` must contain the already approved `SPEECH_PROVIDER=gnani`, `GNANI_API_KEY`, and Bifrost settings described in the product README. Keys stay in Python/backend processes; the capture has no access to them. No keys are injected into Remotion, copied into `public`, logged, or stored in video metadata. Generate and capture steps invoke paid speech/model APIs. Cached narration WAV files are reused when present.

For a **free re-render of the existing take**, with no API requests:

```sh
cd video
npm run build -- --reuse-capture
```

For only the final composition, after capture/edit assets exist:

```sh
cd video
npm run render
npm run review
```

`npm run build` starts a loopback-only recording server on port 8792 and stops its own process afterward. It refuses an occupied port. It uses only `runtime/hackathon-video.sqlite`, never the regular local database or the VM. It creates fictional contacts with reserved example contact details. Background history is generated through the real offline engine and retains its typed-simulation labels. It never dials a phone, sends messages, confirms calendar availability, or changes the original company project.

## Edit structure

| Time | Actual product view | Point |
|---|---|---|
| 0–7 s | Demo experience gallery | Four concrete workflows |
| 7–16 s | Agent editor → Call studio | Language, instructions, business context |
| 16–22 s | Browser voice configuration | Gnani STT/TTS with Bifrost |
| 22–44 s | Recorded live voice conversation | Natural interruption and the latest correction |
| 44–51 s | Conversation details and memory | Persisted transcript and customer context |
| 51–55 s | Analytics | Outcomes traceable to stored demo conversations |
| 55–60 s | Demo gallery | Product name and public demo link |

Silent waits in the voice take are shortened and labelled in the film. Speech remains genuine provider output; `out/edit-report.json` records every cut, audio/video alignment, and the very small tempo adjustment used to fit the exact duration. The film demonstrates an appointment **request**, with no claimed external calendar booking. Narration is synthetic. The quiet synth bed is generated locally from tones, with no stock-music licence dependency.

## Pipeline

- `scripts/prepare.py`: recording-only configuration, fictional contacts, real offline rehearsal history, Gnani narration.
- `scripts/server.py`: the unchanged product app factory with an isolated database and an audio-fixture mount.
- `scripts/instrument.js`: visible eased cursor, virtual customer microphone, actual browser audio recording.
- `scripts/capture.mjs`: real buttons/forms/navigation; lossless-timing high-quality capture; checks interruption metadata and corrected Saturday response; fails on browser errors.
- `scripts/edit.py`: records silent-wait cuts, aligns audio/video, prepares the exact chapter durations and original synth bed.
- `src/index.jsx`: Remotion typography, camera framing, chapter transitions, original product icon, progress line and audio mix.
- `scripts/render.mjs`: pinned Remotion Headless Shell, PNG frames, software rendering, then H.264/AAC with BT.709 limited range and fast-start metadata.
- `scripts/review.py` and `scripts/ocr.swift`: decode every frame, OCR each distinct overlay locally and compare its title/caption pixels on every stable frame, reject duplicated-image artifacts, check black frames/title contrast, track the cursor template, check audio peaks, and create full-size keyframes and contact sheets covering every frame.

Generated media, capture state, the synthetic recording database, and `node_modules` are ignored by Git. Sources and dependency lockfiles are versionable. The output folder contains the film, poster, edit report, frame review report, all-frame contact sheets, and keyframes for inspection.

## Scope of verification

Automated checks inspect all 1,800 frames; a visual review of full-size keyframes and all-frame contact sheets checks framing and typography. This is an edited product demonstration using fictional participants and synthetic speech, not a latency benchmark, a real customer call, a confirmed booking, or a production accuracy claim. Native microphone noise suppression and loudspeaker echo still depend on the viewer's own device; this recording uses a virtual microphone.

The optional `../.venv/bin/python scripts/verify_audio.py` sends the finished audio mix to the configured Gnani STT account and checks intelligibility of the product name, workflow explanation, speech stack, and corrected Saturday-at-two preference. This is a paid API check and is deliberately separate from the free cached re-render. Its raw returned transcript is retained locally in `out/audio-intelligibility.json`.
