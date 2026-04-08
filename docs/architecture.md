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
- custom folder normalization lives here so services and CLI commands share the same `Folders/...` namespace behavior

Calendar adapter:

- `providers/radicale_calendar/provider.py`
- explicit WebDAV/CalDAV requests over HTTP
- no browser automation
- no assumption of a Proton Calendar API

Invite workflow:

- organizer-side workflow is still local-first and CLI-driven
- CalDAV remains the source of truth for local event state
- Bridge SMTP delivers iTIP mail with `METHOD:REQUEST`, `METHOD:CANCEL`, or `METHOD:REPLY`
- one shared UID is reused across CalDAV objects and outbound invite mail

### Persistence

`storage/` contains:

- SQLAlchemy schema
- explicit SQLite migration runner
- repository classes per aggregate/table area

SQLite stores normalized data and source linkage, but not secrets.

Important persisted state now includes:

- normalized event rows with organizer, description, location, sequence, timezone, and attendee metadata
- invite lifecycle records keyed by `UID + organizer + recurrence-id + sequence`
- latest invite instance linkage
- outbound mail records with `sent_ref`, `message_id`, recipients, related invite UID, and method

Migration behavior:

- startup runs repo-local SQLite migrations before ORM sessions are created
- migrations inspect live tables with `PRAGMA table_info(...)`
- missing columns are added with targeted `ALTER TABLE ... ADD COLUMN ...`
- missing tables come from the SQLAlchemy metadata
- invite latest-state rows are backfilled into `invite_instances`
- indexes are created idempotently with `IF NOT EXISTS`

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

### Organizer invite lifecycle

1. create or update the CalDAV event with organizer and attendee metadata
2. generate an iCalendar payload from the same normalized event model
3. send the payload through Bridge SMTP with the correct iTIP method
4. persist the invite record plus outbound mail correlation in SQLite
5. on cancel, default to deleting the organizer-side CalDAV object after sending `METHOD:CANCEL`

## Determinism

The suite is designed for polling and automation:

- stable refs for messages, attachments, invites, calendars, and events
- stable refs for outbound mail sends
- strict JSON envelopes
- typed domain errors
- no background worker required
- destructive actions gated by `--yes`

## Intentional non-goals

- Proton Calendar CRUD integration
- browser automation of Proton web apps
- hidden daemons or async background behavior
- a web UI

## Cancellation design note

For attendee-facing cancellation, the suite does not default to leaving a `STATUS:CANCELLED` VEVENT in Radicale after mail delivery. Real-world Apple Calendar and Gmail behavior is more predictable when the tool sends a standards-compliant `METHOD:CANCEL` update and then removes the local organizer copy from CalDAV. The invite history remains inspectable in SQLite even after the CalDAV object is deleted.
