# proton-agent-suite

`proton-agent-suite` is a local-first, VPS-deployable Python CLI for deterministic access to:

- Proton Mail through **Proton Mail Bridge** on the same host
- A self-hosted **CalDAV** calendar, with **Radicale** as the first provider
- Invite ingestion from synced email into a local SQLite model
- Machine-friendly polling for AI agents with strict JSON output
- Apple Calendar connector metadata for CalDAV sync and optional read-only ICS subscription

This project is intentionally boring: CLI only, no web UI, no background daemon, no invented Proton APIs.

## Status

This repository ships a production-oriented MVP with:

- typed domain errors and stable JSON envelopes
- local SQLite persistence
- Bridge IMAP/SMTP integration paths only
- explicit Radicale/CalDAV HTTP/WebDAV interactions
- invite normalization and RSVP safety checks
- pytest coverage for unit, integration, and CLI JSON behavior

Known limitations are documented below instead of being hidden.

## Prerequisites

- Python 3.12+
- Linux VPS or local Linux host
- Proton Mail Bridge installed and configured on the same machine
- A reachable Radicale/CalDAV endpoint
- SQLite filesystem access

## Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

For development:

```bash
pip install -e .[dev]
```

## Proton Mail Bridge setup on Linux/VPS

This suite only supports Proton mail through **Proton Mail Bridge**.

1. Install Proton Mail Bridge on the VPS.
2. Add the target Proton account in Bridge.
3. Collect the local Bridge IMAP and SMTP settings shown by Bridge:
   - host
   - IMAP port
   - SMTP port
   - Bridge username
   - Bridge password
4. Put those values into `.env` or systemd credentials.
5. Run the CLI on the same machine as Bridge.

The suite does **not** use any unsupported Proton Mail or Proton Calendar API.

## Radicale setup assumptions

- Radicale is your system of record for calendar data.
- The suite talks to it using CalDAV/WebDAV semantics.
- Apple Calendar should connect directly to Radicale over HTTPS.
- Optional public read-only ICS exposure may be reverse-proxied separately.

See `docs/radicale.md` and `docs/apple-calendar.md`.

## Configuration

Copy the sample config:

```bash
cp .env.example .env
```

Important variables:

- `PROTON_AGENT_DB_PATH`
- `PROTON_AGENT_BRIDGE_HOST`
- `PROTON_AGENT_BRIDGE_IMAP_PORT`
- `PROTON_AGENT_BRIDGE_SMTP_PORT`
- `PROTON_AGENT_BRIDGE_USERNAME`
- `PROTON_AGENT_BRIDGE_PASSWORD`
- `PROTON_AGENT_RADICALE_BASE_URL`
- `PROTON_AGENT_RADICALE_USERNAME`
- `PROTON_AGENT_RADICALE_PASSWORD`
- `PROTON_AGENT_RADICALE_DEFAULT_CALENDAR`
- `PROTON_AGENT_ICS_PUBLIC_BASE_URL` (optional)
- `CREDENTIALS_DIRECTORY` (optional systemd credentials)

### Secret handling

- secrets are loaded from environment variables or systemd credentials at runtime
- secrets are **not** stored in SQLite
- the CLI warns about insecure secret file permissions
- logs redact password-like values

## First run

```bash
proton-agent config init
proton-agent config validate
proton-agent diagnostics dump
proton-agent mail health
proton-agent calendar health
```

Then do the first sync:

```bash
proton-agent sync mail --since 30d
proton-agent sync invites
proton-agent sync calendar --days 30
```

## Example commands

Sync mail:

```bash
proton-agent mail sync --folder Inbox --since 30d
```

Scan invites:

```bash
proton-agent invites scan
```

Accept an invite:

```bash
proton-agent invites accept INVITE_REF
```

Create an event:

```bash
proton-agent calendar create   --calendar default   --title "Demo"   --start "2026-04-10T09:00:00+01:00"   --end "2026-04-10T10:00:00+01:00"
```

Show Apple Calendar connector info:

```bash
proton-agent calendar connector
```

Agent snapshot:

```bash
proton-agent --json agent snapshot
```

## JSON mode

Every important command supports `--json`.

Success shape:

```json
{"ok":true,"data":{}}
```

Failure shape:

```json
{"ok":false,"error":{"code":"SOME_STABLE_ERROR_CODE","message":"Human-readable explanation","details":{}}}
```

No extra prose is emitted in JSON mode.

## Apple Calendar

Use **CalDAV** for two-way sync. Use **ICS** only when you intentionally want read-only subscription behavior.

The connector command exposes:

- CalDAV base URL
- username
- default calendar name
- discovered calendar path when available
- optional public ICS URL when configured

## Security notes

- synced mail and calendar metadata live locally in SQLite
- do not place the DB on untrusted storage
- do not expose Bridge ports publicly
- prefer HTTPS for Radicale
- read-only ICS URLs should be treated as public if guessable or shared

## Tests

```bash
pytest
```

Live end-to-end coverage against a real Bridge or Radicale server is intentionally isolated from the default suite.

## Known limitations

- Proton labels are modeled via Bridge mailbox semantics, not arbitrary remote metadata.
- RSVP mail generation is conservative and refuses unsafe forwarded/untrusted invites unless `--force` is used.
- The suite does not automate Proton Calendar.
- `mail search` is local over synced messages, not remote IMAP server-side search.
- `calendar show` currently resolves from locally synced events.

## Repository guide

- `docs/architecture.md` — architecture and boundaries
- `docs/threat-model.md` — security model and risks
- `docs/troubleshooting.md` — common operational fixes
- `docs/cli-reference.md` — command reference
- `docs/deployment-vps.md` — deployment notes
- `docs/apple-calendar.md` — Apple connector details
- `docs/radicale.md` — Radicale assumptions and endpoints
