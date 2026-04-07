# Threat model

## Trust boundaries

### Proton Mail Bridge

Bridge is a **local integration component**. The suite trusts Bridge as the supported way to expose decrypted mail to local IMAP/SMTP clients.

Operational consequences:

- the VPS running Bridge becomes a sensitive host
- Bridge ports must stay private
- host compromise can expose synced mail and credentials in memory/runtime context

### Local SQLite

SQLite stores synced email metadata, bodies, attachments, invite state, and calendar metadata.

Risk:

- anyone with filesystem access to the DB can read synced content

Mitigations:

- store the DB on trusted local storage
- use filesystem permissions and OS hardening
- keep VPS access narrow and audited

## Secret handling model

Secrets are loaded from:

- environment variables / `.env`
- optional Linux systemd credentials

Secrets are **not stored in SQLite**.

This reduces long-lived plaintext replication across app storage. The suite also warns when secret files or credential directories are too permissive.

## Mail label semantics

Proton labels are represented as agent-friendly labels but implemented with Bridge mailbox semantics. This means behavior follows what Bridge exposes over IMAP rather than a custom metadata API.

Implication:

- label behavior is constrained by Bridge mailbox mapping
- removal semantics are conservative and mailbox-based

## Invite trust limits

Invite ingestion is useful but not perfectly trustworthy.

Risks:

- forwarded invites can misrepresent organizer intent
- sender may differ from organizer
- malformed ICS may omit attendee/organizer data
- duplicate or replayed invite messages can exist

Mitigation:

- forwarded or suspicious invites are flagged with machine-readable reason codes
- risky RSVP actions require explicit `--force`
- unsupported safe pathways fail clearly instead of pretending success

## VPS operational risks

- shell access to the VPS is highly privileged
- backups may contain the SQLite DB and attachments
- misconfigured reverse proxies can expose Radicale or optional ICS feeds

Mitigations:

- use minimal SSH access
- encrypt backups separately
- restrict Radicale behind TLS and authentication
- keep optional public ICS exposure deliberately separate and review access patterns

## CalDAV endpoint security

Prefer HTTPS. If self-signed certificates are used, document and pin trust at deployment time. Avoid `http://` unless you explicitly allow insecure mode for a trusted internal path.

## ICS subscription exposure risk

A public ICS feed is read-only, not harmless:

- anyone with the URL may read event titles/times/details depending on what is exposed
- URLs may leak via logs, screenshots, or device sync settings

Treat ICS URLs as shared secrets unless intentionally public.
