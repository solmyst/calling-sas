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
