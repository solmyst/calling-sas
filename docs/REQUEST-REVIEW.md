# Structured requests and local follow-up

Scope agreed 29 October 2026: fix the workflow editor, add a reviewable business
request to Call Detail, and persist a local lead/follow-up after operator review.
External calendar, CRM, messaging and phone actions remain disabled by request.

Contract:
- `GET /api/calls/{id}/request`: request, revision, integration status and local lead.
- `POST /api/calls/{id}/request/extract`: optional paid post-call extraction using
  the configured conversation model; body `{revision}`. No voice-path work is added.
- `PUT /api/calls/{id}/request`: operator-reviewed fields, owner, notes and revision.
- `POST /api/calls/{id}/request/follow-up`: create/update a local lead and reuse the
  call's local task; body `{revision}`. This never invokes an external integration.

Fields: service, preferred_day, preferred_time, timezone, business_need,
callback_window. Unknown values remain blank. Spoken preferences are not silently
resolved to calendar dates or AM/PM. Model suggestions require exact customer-turn
evidence and operator review. A statement from the agent is not customer evidence.

Writes require an ended call and optimistic revision checks. Extracted suggestions
cannot overwrite intervening edits. Follow-up requires a reviewed, current request,
an assigned owner and a contact that remains eligible. Repeating follow-up does
not create another lead/task. Lead records are workspace-local and explicitly
unsynced; no appointment is presented as booked.

Acceptance: latest Saturday-at-two correction can be extracted with customer
quotes, edited and reviewed; a single local lead/task persists through restart;
missing details stay unknown; model failures preserve the request; stale edits,
unsafe extracted evidence, unreviewed follow-up and opted-out contacts are rejected.
External actions remain disabled regardless of environment flags or submitted data.

## Using the demo

1. Run a browser voice conversation or a labelled typed simulation.
2. End the voice session to open Call Detail, or open it from Call history.
3. Select **Extract from transcript** for model suggestions, or enter the details.
   Evidence quotes show the original customer statement and transcript turn.
4. Clarify or leave unknown fields blank. Assign a team/owner and select
   **Save reviewed request**. Unchanged extracted fields retain their evidence.
5. Select **Create local follow-up**. The lead and task are stored in this
   workspace only. Repeat saves update the same records. Later edits visibly
   mark the existing local lead as an earlier revision until it is updated.

Unknown service, AM/PM, calendar date and timezone are never filled from business
assumptions. Use an IANA timezone when supplied by the operator. A reviewed
request is still not a confirmed appointment. Opted-out/ineligible contacts are
blocked at the follow-up endpoint even if they were eligible during the call.

## Checks

```sh
.venv/bin/python -m unittest discover -s tests -q
node --test tests/*.test.mjs
# Optional browser test; uses Playwright from the existing video toolchain.
# Install that toolchain with: cd video && npm ci
node scripts/check_request_browser.mjs
# One paid model extraction using fictional test statements:
node scripts/check_request_browser.mjs --live-model
```

The browser helper starts/stops its own loopback server on an available port and
uses a temporary database, never the ordinary workspace or VM. It requires
Google Chrome, or set `BROWSER_PATH` to a compatible installed Chromium binary.
Screenshots/report are written under ignored `runtime/request-browser-check/`.
The checked path covers workflow create/edit, correction extraction, manual
review, deduplicated follow-up, reload persistence, mobile horizontal fit and
page errors. It does not exercise physical microphone acoustics or phone calls.

Implementation references: [FastAPI routers](https://fastapi.tiangolo.com/tutorial/bigger-applications/)
and [Pydantic configuration](https://docs.pydantic.dev/latest/api/config/).
No new runtime dependencies or provider credentials are introduced.
