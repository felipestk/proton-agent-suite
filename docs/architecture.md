# Architecture

## Goal

Provide deterministic CLI access for an AI agent to:

- Proton email through Proton Mail Bridge
- self-hosted calendar data through CalDAV
- normalized invite state in local SQLite

## Architecture style

The code uses a ports-and-adapters layout.

### Domain

`src/proton_agent_suite/domain/` contains:

- enums and typed error codes
- provider protocols
- Pydantic models and value objects
- services implementing business workflows

Domain services do not depend directly on Typer, sqlite3 details, or HTTP/XML parsing.

### Adapters

Mail adapter:

- `providers/bridge_mail/client.py`
- Bridge IMAP only for retrieval and mailbox operations
- Bridge SMTP only for sending

Calendar adapter:

- `providers/radicale_calendar/provider.py`
- explicit WebDAV/CalDAV requests over HTTP
- no browser automation
- no assumption of a Proton Calendar API

### Persistence

`storage/` contains:

- SQLAlchemy schema
- migration bootstrap
- repository classes per aggregate/table area

SQLite stores normalized data and source linkage, but not secrets.

### CLI

Typer commands are thin wrappers around services. They:

- load settings
- map output to human or JSON mode
- map domain errors to stable CLI failures

## Core flow

### Mail sync

1. connect to Bridge IMAP
2. list or fetch messages from a selected folder
3. parse MIME content and attachment metadata
4. persist normalized messages and attachments in SQLite
5. expose stable local refs for later operations

### Invite scan

1. query synced messages with invite hints
2. extract `text/calendar` parts and `.ics` attachments
3. normalize VEVENT state
4. deduplicate by `UID + organizer + recurrence-id + sequence`
5. mark latest version and warnings
6. link invite records back to source email refs

### Calendar sync

1. discover calendars through CalDAV/WebDAV
2. fetch upcoming event payloads via calendar-query REPORT
3. parse VEVENT objects from ICS payloads
4. persist normalized calendar and event metadata locally

## Determinism

The suite is designed for polling and automation:

- stable refs for messages, attachments, invites, calendars, and events
- strict JSON envelopes
- typed domain errors
- no background worker required
- destructive actions gated by `--yes`

## Intentional non-goals

- Proton Calendar CRUD integration
- browser automation of Proton web apps
- hidden daemons or async background behavior
- a web UI
