# Verification report — 2026-10-25

## Automated checks passed
`python -m unittest discover -s tests -v`: **22 tests passed**. Tests use temporary databases and mocked provider boundaries.

Covered: complete simulated qualification flow; persistent metrics/history; configuration snapshots; invalid input; missing agent; consent rejection; opt-out suppression; unconditional real-call rejection; duplicate start/turn/workflow requests; terminal-state protection; transcript redaction/export; cancellation; host and cross-origin write rejection; hosted configuration fail-closed; password sign-in, HttpOnly session cookie and logout; persistence across application recreation; negative confirmation; original voicemail detection vs a real person asking for a callback.

Additional checks: JavaScript syntax checks on all four modules; shell script syntax; `pip check` (no broken requirements); copied original redactor self-checks. A SQLite backup was created using the supplied utility, opened independently, passed `PRAGMA integrity_check`, and contained the persisted call records. This is a local backup/read validation, not a VM disaster-recovery exercise.

The test runner emits a Starlette deprecation warning about its httpx compatibility layer. Tests pass; the pinned dependencies preserve the tested configuration. Migrate the test-client dependency during a deliberate dependency update.

## Browser verification
Used the Codex in-app browser and Chrome against the loopback server:
- Dashboard rendered with actual database metrics, chart and seeded history.
- Aria simulation: greeting → customer consent → need → confirmation → qualified outcome, seven transcript turns and follow-up task.
- Edited Aria’s description and verified the saved value.
- Added a fictional Robin Demo contact with consent and verified it appeared in Contacts and subsequent workflow selection.
- Ran the lead workflow: four eligible contacts completed, one contact without consent skipped; tasks appeared.
- History filtered to the three seeded handoff calls; transcript modal showed the appropriate transcript and configuration details.
- Local voice playback reported completion in Chrome; no independent acoustic quality assessment was made. Browser voice support varies.
- After restarting the server, existing calls and edits remained available.
- Selected Casey instead of the default contact; the selection remained correct during the call. Voicemail response completed as `no_answer`, not a qualified lead or handoff.
- Browser console returned no warnings/errors during the initial complete conversation test.
- Browser voice mode rendered as available from live server configuration. Starting it created a separate `browser` session, generated and played the ElevenLabs opening, displayed push-to-talk controls, and left telephone mode disabled. Browser console returned no warnings or errors. Microphone capture was not exercised by automation because granting microphone permission and supplying a human utterance require the operator.
- Overview had no document-level horizontal overflow at 320, 768, 1024 and 1440 CSS pixels after the mobile fix. Call studio also fit at 320px. Tables intentionally scroll inside their containers. This is not a full accessibility certification or every-page/device matrix.

## Issues found and fixed
1. Plain “No” at final confirmation originally marked a successful result. Added a failing regression test, then refusal handling and an affirmative-confirmation requirement.
2. Mobile navigation overflowed by seven pixels at 320px. Reduced narrow-screen navigation padding and verified matching viewport/document width.
3. Contact selection reset visually to Jamie during a call to a different contact. Render now preserves the call’s contact snapshot selection.
4. Machine greetings could hit a generic “person” handoff rule. Extracted the original detector, added regression tests, and prioritized its result.
5. Added a label for the native dialog and prevented the skip link from inadvertently changing the application route.

## Original-project integrity
`docs/original-integrity.json` records a before/after SHA-256 comparison of **38,646 files** (including existing nested artifacts; Git metadata, named venv/cache directories excluded). **0 changed, 0 missing.** Application/test source inventory contains 84 Python files after excluding hidden/vendor directories. No original project commands, live calls, messaging, deployment scripts or provider probes were executed.

## Provider verification

A synthetic provider round trip used the user-authorized private configuration without printing credential values: ElevenLabs returned a 52,287-byte MP3; AssemblyAI transcribed the synthetic sentence; Bifrost returned a contextual 97-character reply. This proves account authentication and the request formats used by this implementation. It does not establish physical microphone quality, conversational latency under representative use, provider capacity, billing economics or telephone audio quality.

## Boundaries not validated
Physical microphone permission/audio, streaming barge-in, original Pipecat runtime execution, Exotel/CallerDesk/Asterisk connectivity, telephone call quality, billing, multitenancy, load/concurrency beyond SQLite transactions, production security, VM systemd/Caddy startup and Docker build/runtime. These are explicit next-stage work, not implied by passing the browser demo checks.
