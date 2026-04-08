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
- attendee-aware calendar event writes with organizer and ATTENDEE metadata
- first-class invite create, update, and cancel workflows with shared UID/SEQUENCE across CalDAV + SMTP
- IMAP-safe folder create, rename, and delete commands
- outbound send correlation with local `sent_ref` + SMTP `message_id`
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
- `PROTON_AGENT_BRIDGE_FOLDER_PREFIX` (defaults to `Folders`)
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

Existing installs are upgraded in place on startup. The CLI now runs explicit SQLite schema migrations before opening a session, so an existing DB such as `/var/lib/proton-agent/proton-agent.sqlite3` is updated with newly required columns, tables, and indexes instead of relying on `create_all()` alone.

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

Create an attendee-aware event without sending invitations:

```bash
proton-agent calendar create \
  --calendar default \
  --title "Demo" \
  --start "2026-04-10T09:00:00+01:00" \
  --end "2026-04-10T10:00:00+01:00" \
  --timezone Europe/Lisbon \
  --organizer felipe@nurami.ai \
  --attendee 'felipestark@gmail.com|cn=Felipe Stark|role=REQ-PARTICIPANT|rsvp=true|partstat=NEEDS-ACTION'
```

Create and send a meeting invite:

```bash
proton-agent invites create \
  --calendar default \
  --title "Demo" \
  --start "2026-04-10T09:00:00+01:00" \
  --end "2026-04-10T10:00:00+01:00" \
  --organizer felipe@nurami.ai \
  --attendee felipestark@gmail.com
```

Update or cancel an existing invite by `INVITE_REF` or `UID`:

```bash
proton-agent invites update UID_OR_REF --start "2026-04-10T11:00:00+01:00" --end "2026-04-10T12:00:00+01:00"
proton-agent invites cancel UID_OR_REF
```

Manage folders:

```bash
proton-agent mail create-folder --name "Clients/Felipe"
proton-agent mail rename-folder --from "Clients/Felipe" --to "Clients/Felipe-2026"
proton-agent mail delete-folder --name "Clients/Felipe-2026"
```

With Proton Mail Bridge, custom folders are user-facing logical names but remote IMAP mailboxes live under `Folders/...`. The suite now normalizes:

- `Clients/Felipe` -> `Folders/Clients/Felipe`
- `Folders/Clients/Felipe` -> unchanged
- system folders like `Inbox`, `Sent`, `Archive`, `Drafts`, `Trash`, and `Spam` -> unchanged

`mail folders` returns the logical `name` plus the underlying `remote_name` so JSON callers can see both.

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

- SQLite migrations are additive and repo-local. They safely handle current schema evolution for existing installs, but they are not a general-purpose migration framework for arbitrary historical forks.
- Proton labels are modeled via Bridge mailbox semantics, not arbitrary remote metadata.
- Proton Bridge custom folders depend on the configured namespace prefix and default to `Folders`. Renaming or deleting Bridge system folders is still not supported.
- RSVP mail generation is conservative and refuses unsafe forwarded/untrusted invites unless `--force` is used.
- Invite cancel defaults are optimized for Apple Calendar and Gmail compatibility: send `METHOD:CANCEL`, then delete the organizer-side CalDAV object. Use `--keep-local-event` only if you explicitly want a canceled local placeholder.
- The suite does not automate Proton Calendar.
- `mail search` is local over synced messages, not remote IMAP server-side search.
- `calendar show` currently resolves from locally synced events.
- Outgoing attachments are supported for direct `mail send` and `mail reply`, but draft attachment persistence is still limited.

## Repository guide

- `docs/architecture.md` — architecture and boundaries
- `docs/threat-model.md` — security model and risks
- `docs/troubleshooting.md` — common operational fixes
- `docs/cli-reference.md` — command reference
- `docs/deployment-vps.md` — deployment notes
- `docs/apple-calendar.md` — Apple connector details
- `docs/radicale.md` — Radicale assumptions and endpoints
