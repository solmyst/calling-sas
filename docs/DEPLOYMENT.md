# VM operations and deployment templates

The templates prepare a private, password-protected demo on a Linux VM after explicit owner approval. They do not make this a production multi-tenant calling service. The authenticated demo was subsequently deployed on Azure; see [28 October validation](GNANI-VALIDATION.md). These templates are not a fresh audit of that VM. The structured-request update is locally validated and is not deployed by this change.

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
Shared demo password is not user authentication/RBAC or tenant isolation. Sessions last eight hours; rotate SESSION_SECRET to revoke all sessions. Login throttling is in-memory and resets with the process. The current app must run one worker. Host checks and same-origin mutation checks complement SameSite cookies; they are not a substitute for a security assessment. SQLite files and backups are not encrypted by the application. Regex redaction misses unstructured addresses, names, international identifiers and spoken-out numbers. Contacts intentionally contain supplied contact data. Do not collect real sensitive information in the pitch environment.

Before production: independent security review, real identity/tenant controls, durable rate limiting, retention and deletion tooling, observability, disaster recovery, load tests, model/provider evaluation, consent/recording requirements reviewed for the actual operating jurisdictions, provider contract review, and explicit live-call authorization. No claim of regulatory compliance is made.

Reference: [FastAPI deployment concepts](https://fastapi.tiangolo.com/deployment/). Templates remain reviewable preparations, not executed deployment steps.
