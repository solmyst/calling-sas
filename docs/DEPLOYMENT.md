# VM operations and deployment templates

The templates prepare a private, password-protected demo on a Linux VM after explicit owner approval. They do not make this a production multi-tenant calling service. The authenticated demo was subsequently deployed on Azure; see [28 October validation](GNANI-VALIDATION.md). On 5 November 2026 the VM was updated through runtime commit `0d7266b` with Groq-primary/Gemini-fallback routing and per-stage voice timing. The release passed VM-local tests, public HTTPS login and dashboard checks, SQLite integrity, and live synthetic Groq/Gnani provider checks. No phone call was placed.

The pre-update code, environment and consistent SQLite backup are stored root-only at `/var/backups/relay-voice/pre-0d7266b-20261105-015232`.

On 8 November 2026 the VM was updated to commit `50065fd` (trial accounts and a main account). The app is served at `https://anvaya.indiasouthcentral.cloudapp.azure.com/relay/` behind Nginx, which proxies `/relay/` to `127.0.0.1:8787`; the Azure DNS label changed from the earlier `interviewace-anush` name. The release passed all 67 tests on the VM, a dry-run migration of a copy of the live database (all 22 records moved to the main workspace), local and public health checks, and public session and sign-up validation checks. No production trial account was created. The pre-update code, environment and SQLite backup are stored root-only at `/var/backups/relay-voice/pre-50065fd-20261108-173126`. The first release attempt rolled back automatically when release-directory permissions prevented the service user from entering `/opt/relay-voice`; deployment was repeated with the application root restored to mode `0755` and then passed health checks.

## Requirements
A supported Linux host, Python 3.14 for the web demo, a dedicated unprivileged `relay` user, Caddy for HTTPS, an approved hostname, persistent local disk, and outbound package-registry access during installation. One process is appropriate for this SQLite/shared-password demo. A future Pipecat media worker needs a separately validated Python 3.12 environment, codec/media dependencies, CPU/audio-model compatibility and service accounts.

## Installation outline (only after approval)
1. Copy this independent repository to `/opt/relay-voice`. Exclude `.venv`, runtime databases, local `.env` and Git history if unnecessary.
2. Create a clean venv with the chosen Python and install `requirements.lock`. Run the test suite on the VM.
3. Create `/var/lib/relay-voice`, owned by `relay:relay` with mode 0700. App code should be owned by the deployment administrator, read-only to the service user.
4. Copy `deploy/production.env.example` to `/etc/relay-voice.env`, owned by root and readable only by the service group (0640). Set an independent password of at least 16 characters, a random session secret of at least 32 characters, and the exact HTTPS public origin. Generate values locally with a password manager; never reuse company keys. Leave the bind address on loopback.
5. Review/install the systemd unit. Caddy runs separately and proxies to 127.0.0.1:8787. Configure `RELAY_DOMAIN` in Caddy's environment. Validate Caddy configuration before restart. Expose only approved SSH and HTTPS/HTTP ports; do not open the app port publicly.
6. Start the service only after approval, verify HTTPS, sign-in, health, persistence, backups and the live-call rejection test from the deployed hostname. The application refuses hosted startup with missing secrets or a non-HTTPS origin.

## Process management and logs
`relay-voice.service` restarts on failure, uses restrictive file permissions, protects the filesystem and writes application lifecycle logs to journald. Configure journald retention and disk limits. API access logging is disabled to reduce exposure. Call logs include only the internal call ID and `mode=demo`; they do not log passwords, telephone numbers or transcript bodies. Do not enable verbose proxy/body logging on real-data systems.

`GET /health` verifies a database operation and exposes only status/mode/version. The Dockerfile uses the configured PUBLIC_ORIGIN host in its health check. For a manual hosted-mode check, supply the expected Host header:

```sh
curl --fail -H 'Host: voice.example.com' http://127.0.0.1:8787/health
```

## Backups and restore
Run `python scripts/backup.py /var/lib/relay-voice/relay.sqlite /secure-backups/relay-YYYY-MM-DD.sqlite` as a user permitted to read the source and write the backup. This uses SQLite's backup API, not a raw copy of an active WAL database. Encrypt off-host backups and restrict access. Test restore regularly: stop the app, preserve the current DB and WAL/SHM files, restore the backup to a clean directory with correct permissions, restart and verify. A backup is not verified until it has been restored successfully.

## Container alternative
`docker build -f deploy/Dockerfile -t relay-voice:demo .` prepares an image. Supply production environment values at runtime, mount a private persistent volume at `/data`, bind the container only to loopback behind TLS, and set memory/CPU limits. Do not run both the container and systemd app against the same database. Docker build/runtime were not exercised on this workstation; the template needs validation on the target host.

## Security limitations and launch gates
Accounts give each trial user a private workspace inside one SQLite file, scoped by a workspace column; this is application-level isolation, not separate databases. There is no email verification, password reset or admin user management yet; disable a trial by setting `disabled` on its `users` record. Sessions last eight hours; rotate SESSION_SECRET to revoke all sessions. Login throttling is in-memory and resets with the process. The current app must run one worker. Host checks and same-origin mutation checks complement SameSite cookies; they are not a substitute for a security assessment. SQLite files and backups are not encrypted by the application. Regex redaction misses unstructured addresses, names, international identifiers and spoken-out numbers. Contacts intentionally contain supplied contact data. Do not collect real sensitive information in the pitch environment.

Before production: independent security review, real identity/tenant controls, durable rate limiting, retention and deletion tooling, observability, disaster recovery, load tests, model/provider evaluation, consent/recording requirements reviewed for the actual operating jurisdictions, provider contract review, and explicit live-call authorization. No claim of regulatory compliance is made.

Reference: [FastAPI deployment concepts](https://fastapi.tiangolo.com/deployment/). Templates remain reviewable preparations, not executed deployment steps.
