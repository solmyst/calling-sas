# Relay Voice

**A separate, local AI calling product demo built from an audited voice-system foundation.**

Configure agents, manage contacts, hold browser voice conversations, rehearse scripted flows, review transcripts, and see the next step. The dashboard is backed by a real API and SQLite persistence. Browser voice uses AssemblyAI, Bifrost and ElevenLabs. Telephone dialing remains unavailable.

The browser runtime supports English, Hindi and Hinglish agents. The included `Nisha` agent demonstrates customer help and booking intake without falsely claiming calendar availability or confirmation.

## Public site

The static product site is deployed from `site/` to [GitHub Pages](https://solmyst.github.io/calling-sas/). GitHub Pages cannot run FastAPI, SQLite, private API keys or realtime server WebSockets; use the deployment configuration in `deploy/` for the working voice application.

![Relay Voice dashboard](docs/dashboard.png)

## Start locally

Python 3.14 was used and tested on this Mac. No Node build, Docker or telephony account is needed. Typed simulation works without provider credentials; browser voice requires the settings below.

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

For browser voice, configure these server-only values in `.env` and restart:

```dotenv
ASSEMBLYAI_API_KEY=
BIFROST_URL=https://bifrost.parkplus.io/v1
BIFROST_VK=
BIFROST_MODELS=your-approved-model-id
ELEVENLABS_API_KEY=
ELEVENLABS_VOICE_ID=
ELEVENLABS_MODEL=eleven_flash_v2_5
```

The current local `.env` has been configured from the provider credentials the user explicitly authorized for this demo. It is mode `0600` and Git-ignored. Keys never enter frontend JavaScript or API responses.

## Your five-minute pitch

1. **Overview:** introduce the workspace and the three agents. Say clearly that records are simulated.
2. **AI agents → Aria → Configure:** change the opening, question or business context. Saved system prompts are for a future model connection; the offline simulator uses the explicit script fields.
3. **Call studio:** choose Live browser voice and start the conversation. Grant microphone access once, listen to the ElevenLabs opening, then answer naturally. The microphone detects speech and sends the turn after a short silence; no Stop button is required.
4. Inspect the saved outcome and transcript. Repeat with “Ask for a human” or “Call back later” to show a different path. “Opt out” marks that contact do-not-call and blocks subsequent calls.
5. **Workflows:** simulate New lead discovery. The server skips ineligible contacts and creates local follow-up tasks. Mark a task done.
6. **Call history / Analytics:** show persisted transcripts, configuration snapshots and derived metrics. Export a transcript. “Listen locally” in history still uses an on-device browser voice; live Studio replies use ElevenLabs.

An in-progress conversation survives page/server restarts; open it from Call history and select Resume. The runtime database lives in `runtime/relay.sqlite` by default. Keep the entire `runtime` directory private. To start an independent fresh demo, set DATABASE_PATH to a new file; do not delete a database containing wanted work.

## Included features

| Area | Working locally |
|---|---|
| Dashboard | Persisted call totals, outcomes, demo duration, weekly activity, agents, recent calls |
| Agents | Create/edit, pause, industry/use case, opening, question, context, prompt storage |
| Contacts | Create/edit, search, segments, E.164 validation, consent and do-not-call enforcement |
| Studio | Typed simulation plus hands-free browser voice: realtime AssemblyAI STT, Bifrost LLM and ElevenLabs TTS |
| Workflows | Create/edit/pause, segment selection, batch simulation, request deduplication, local tasks |
| History | Search/filter, transcript viewer/export, configuration snapshots, resume active simulations |
| Analytics | Derived all-time and weekly metrics; no invented production claims |
| Privacy | Original redactor reused, extra email masking, escaped rendering, no frontend credentials |
| Operations | Environment settings, optional local password, hosted-mode gates, backup tool, VM templates |

Seed history, script responses and outcomes are synthetic. Batch runs execute immediately and can show 0s durations. Browser voice invokes the three configured cloud providers and saves finalized transcript text. It does not record raw audio locally. No real calendar booking, actual transfer, SMS, WhatsApp, email, Exotel call or external CRM update occurs.

## Tests

```sh
.venv/bin/python -m unittest discover -s tests -v
node --check static/app.js
node --check static/views.js
node --check static/forms.js
```

Node is needed only for optional JS syntax checks, not for running the product. Tests use temporary databases and no external services. See [verification report](docs/VERIFICATION.md) for browser checks, fixes and limitations.

## Independence and reuse

The original `/Users/anushgupta/Documents/Ai calling work/` project was inspected read-only. Nothing in the new app imports it or requires its files at runtime. The user confirmed permission to reuse code and later explicitly authorized the provided provider accounts for this demo. The selected AssemblyAI, Bifrost and ElevenLabs settings were copied into the standalone product's private, ignored `.env`; no customer data, recordings, company business prompts or telephony/messaging credentials were copied.

The original voice engine contains useful failover and lifecycle behavior, but also direct company integrations. The audit and architecture document explain how to preserve that investment in a separate media worker, rather than importing the company monolith into the product.

## Documentation

- [Existing-system audit](docs/SOURCE-AUDIT.md) and [symbol inventory](docs/source-inventory.json)
- [Product context and acceptance criteria](docs/PRODUCT.md)
- [Architecture, storage and provider boundary](docs/ARCHITECTURE.md)
- [Feature overview and pitch guide](docs/DEMO-GUIDE.md)
- [VM deployment preparation](docs/DEPLOYMENT.md)
- [Roadmap and commercial release gates](docs/ROADMAP.md)
- [Reuse provenance](docs/PROVENANCE.md)
- [Voice integration and test plan](docs/VOICE-INTEGRATION.md)
- [Sales demo prompt](docs/SALES-DEMO-PROMPT.md)
- [Initial commercial plan](docs/GO-TO-MARKET.md)

## Release status

**Local browser voice demo, v0.2.0.** Provider connectivity and synthetic round-trip audio have been verified. The physical microphone flow still needs the operator to grant permission and speak. This is not a production multi-tenant SaaS or a validated telephone calling service. Exotel, real customer data and hosting remain later stages. Nothing has been deployed.
