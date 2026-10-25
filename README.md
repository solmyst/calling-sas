# Relay Voice

**A separate, local AI calling product demo built from an audited voice-system foundation.**

Configure agents, manage contacts, rehearse conversations, run workflows, review transcripts, and see the next step. The dashboard is backed by a real API and SQLite persistence. Calls are clearly labeled simulations; this release has no live dialing implementation or connected AI model.

![Relay Voice dashboard](docs/dashboard.png)

## Start locally

Python 3.14 was used and tested on this Mac. No Node build, Docker, AI key or telephony account is needed.

```sh
cd "/Users/anushgupta/Documents/Codex/2026-10-25/i-m-providing-you-with-the/outputs/relay-voice"
./scripts/start.sh
```

Open **http://127.0.0.1:8787**. Stop with Ctrl+C. The script creates an isolated `.venv` and installs the pinned lockfile if the venv is absent. On a different machine, change the `cd` path to your checkout.

Manual clean setup:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock
cp .env.example .env
.venv/bin/python run.py
```

Configuration is optional locally. A local `.env` is ignored by Git. Shell environment variables take precedence. Set `PORT` and `PUBLIC_ORIGIN` together when changing the port. If the port is in use, use another port; do not stop an unrelated process. Local mode refuses a non-loopback bind address.

## Your five-minute pitch

1. **Overview:** introduce the workspace and the three agents. Say clearly that records are simulated.
2. **AI agents → Aria → Configure:** change the opening, question or business context. Saved system prompts are for a future model connection; the offline simulator uses the explicit script fields.
3. **Call studio:** select Aria and Jamie Morgan. Start a simulation. Choose “Happy to talk,” “Share a need,” then “Confirm next step.”
4. Inspect the saved outcome and transcript. Repeat with “Ask for a human” or “Call back later” to show a different path. “Opt out” marks that contact do-not-call and blocks subsequent calls.
5. **Workflows:** simulate New lead discovery. The server skips ineligible contacts and creates local follow-up tasks. Mark a task done.
6. **Call history / Analytics:** show persisted transcripts, configuration snapshots and derived metrics. Export a transcript. Optional “Listen locally” uses an available on-device English browser voice; it is not a recording or a live voice pipeline.

An in-progress conversation survives page/server restarts; open it from Call history and select Resume. The runtime database lives in `runtime/relay.sqlite` by default. Keep the entire `runtime` directory private. To start an independent fresh demo, set DATABASE_PATH to a new file; do not delete a database containing wanted work.

## Included features

| Area | Working locally |
|---|---|
| Dashboard | Persisted call totals, outcomes, demo duration, weekly activity, agents, recent calls |
| Agents | Create/edit, pause, industry/use case, opening, question, context, prompt storage |
| Contacts | Create/edit, search, segments, E.164 validation, consent and do-not-call enforcement |
| Studio | Typed and suggested replies, context questions, success/refusal/callback/handoff/opt-out, cancellation |
| Workflows | Create/edit/pause, segment selection, batch simulation, request deduplication, local tasks |
| History | Search/filter, transcript viewer/export, configuration snapshots, resume active simulations |
| Analytics | Derived all-time and weekly metrics; no invented production claims |
| Privacy | Original redactor reused, extra email masking, escaped rendering, no frontend credentials |
| Operations | Environment settings, optional local password, hosted-mode gates, backup tool, VM templates |

Seed history, script responses and outcomes are synthetic. Batch runs execute immediately and can show 0s durations. No speech recognition, model reasoning, real calendar booking, actual transfer, SMS, email, Exotel calls or external CRM updates occur.

## Tests

```sh
.venv/bin/python -m unittest discover -s tests -v
node --check static/app.js
node --check static/views.js
node --check static/forms.js
```

Node is needed only for optional JS syntax checks, not for running the product. Tests use temporary databases and no external services. See [verification report](docs/VERIFICATION.md) for browser checks, fixes and limitations.

## Independence and reuse

The original `/Users/anushgupta/Documents/Ai calling work/` project was inspected read-only. Nothing in the new app imports it or requires its files at runtime. The user confirmed permission to reuse code. The active privacy redactor and optional audio gate were copied; the voicemail detector was extracted with its behavior preserved. No company `.env`, customer data, recordings, models, business prompts, deployment credentials or internal service configuration was copied.

The original voice engine contains useful failover and lifecycle behavior, but also direct company integrations. The audit and architecture document explain how to preserve that investment in a separate media worker, rather than importing the company monolith into the product.

## Documentation

- [Existing-system audit](docs/SOURCE-AUDIT.md) and [symbol inventory](docs/source-inventory.json)
- [Product context and acceptance criteria](docs/PRODUCT.md)
- [Architecture, storage and provider boundary](docs/ARCHITECTURE.md)
- [Feature overview and pitch guide](docs/DEMO-GUIDE.md)
- [VM deployment preparation](docs/DEPLOYMENT.md)
- [Roadmap and commercial release gates](docs/ROADMAP.md)
- [Reuse provenance](docs/PROVENANCE.md)

## Release status

**Local demo / product foundation, v0.1.0.** Prepared for a sales conversation about the experience and intended capability. Not a production multi-tenant SaaS or a validated live calling service. Production voice integration, Exotel, real customer data and hosting are subsequent, explicitly approved stages. Nothing has been deployed.
