# Deployment And Security

## Linux VPS Assumptions

From the repo deployment model:

- Proton Mail Bridge runs on the same VPS as `proton-agent`
- SQLite is local to the VPS filesystem
- Radicale runs locally or on a reachable internal endpoint
- Apple Calendar reaches Radicale over HTTPS

## Recommended Layout

- dedicated non-root app user
- checkout at `/opt/proton-agent-suite`
- DB at `/var/lib/proton-agent/proton-agent.sqlite3`
- logs in the systemd journal or a restricted log path
- credentials in systemd credentials or a locked-down `.env`

## systemd, Cron, Timers

No daemon is required. Run ad-hoc CLI commands from cron or systemd timers.

Typical scheduled workflow:

```bash
proton-agent sync mail --since 7d
proton-agent sync invites
proton-agent sync calendar --days 30
proton-agent --json agent snapshot
```

## `CREDENTIALS_DIRECTORY`

Credential handling supports:

- environment variables
- optional Linux systemd credentials via `CREDENTIALS_DIRECTORY`

Expected credential filenames when using systemd credentials:

- `proton_agent_bridge_password`
- `proton_agent_radicale_password`

Notes:

- Secrets are loaded at runtime.
- Secrets are not stored in SQLite.
- Validation warns when the env file or credentials directory is too permissive.

## DB And File Permissions

- Restrict filesystem permissions on the DB and `.env`.
- Keep the DB on trusted local storage.
- Back up the SQLite DB securely because it contains synced content and attachments.
- Treat backups as sensitive material.

## Bridge Privacy

- Keep Bridge bound to localhost.
- Do not expose Bridge ports via firewall rules, reverse proxy, or public interfaces.
- The VPS hosting Bridge is a sensitive host because Bridge exposes decrypted mail to local IMAP/SMTP clients.

## Radicale TLS Guidance

- Prefer HTTPS for Radicale.
- Terminate TLS with a proper certificate on the reverse proxy when possible.
- If self-signed TLS is unavoidable, install trust deliberately on clients rather than disabling validation broadly.

## ICS URL Sensitivity

- Public ICS is optional and external to the core CLI.
- ICS is read-only, not harmless.
- Anyone with the URL may be able to read event details exposed by that feed.
- Treat ICS URLs as shared secrets unless intentionally public.

## Trust Boundaries

Important boundaries from the threat model:

- Bridge is the trusted local integration point for decrypted Proton mail.
- SQLite is readable by anyone with filesystem access to the DB.
- Invite ingestion is useful but not perfectly trustworthy.
- Forwarded, replayed, malformed, or organizer-mismatched invites can exist.
- Browser automation is intentionally out of scope.
- Proton labels follow Bridge mailbox semantics, not a custom metadata API.
