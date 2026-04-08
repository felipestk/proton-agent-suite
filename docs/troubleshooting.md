# Troubleshooting

## Bridge not running

Symptoms:

- `BRIDGE_NOT_RUNNING`
- `BRIDGE_UNREACHABLE`
- mail health check fails immediately

Checks:

- verify Proton Mail Bridge is running on the VPS
- verify the configured IMAP/SMTP ports match Bridge
- verify Bridge is bound to `127.0.0.1` or the expected local address

## Bridge auth failures

Symptoms:

- `BRIDGE_AUTH_FAILED`

Checks:

- re-copy the Bridge username and password from Proton Mail Bridge
- make sure the account is still signed in within Bridge
- confirm the `.env` or systemd credential file contains the right value

## Bridge port changes

Bridge ports can differ from common defaults.

Checks:

- inspect the Bridge account settings
- update `PROTON_AGENT_BRIDGE_IMAP_PORT` and `PROTON_AGENT_BRIDGE_SMTP_PORT`

## IMAP / SMTP connectivity problems

- run `proton-agent diagnostics dump`
- ensure local firewall rules are not blocking localhost access
- confirm the suite is running on the same host as Bridge

## Radicale discovery failures

Symptoms:

- `CALENDAR_UNREACHABLE`
- `CALENDAR_DISCOVERY_FAILED`

Checks:

- verify `PROTON_AGENT_RADICALE_BASE_URL`
- ensure the URL points at the user collection root expected by Radicale
- verify reverse proxy path rewriting is correct

## CalDAV auth issues

Symptoms:

- `CALENDAR_AUTH_FAILED`

Checks:

- confirm Radicale username/password
- confirm the proxy forwards `Authorization` headers correctly

## Apple Calendar connection issues

Use the output of `proton-agent calendar connector`.

Remember:

- **CalDAV** is two-way sync
- **ICS** is read-only subscription

Common mistakes:

- pasting the ICS URL into a CalDAV account form
- using the collection root when Apple needs a deeper calendar path
- failing TLS trust because of a self-signed certificate

## TLS / self-signed certificates

If Radicale is fronted by a self-signed TLS certificate, clients may reject it.

Fixes:

- prefer a valid public certificate on the reverse proxy
- if you must use a self-signed cert, install trust on the client devices
- do not broadly disable TLS validation unless you understand the risk

## Malformed ICS

Symptoms:

- `INVITE_PARSE_FAILED`
- missing organizer or attendee data

Behavior:

- recoverable invite detection still stores the source message locally
- unsafe or incomplete RSVP pathways fail instead of faking success

## Duplicate invite cases

The suite tracks invite versions by UID, organizer, recurrence ID, and sequence.

If duplicates still look confusing:

- inspect `invites latest`
- inspect `invites source INVITE_REF`
- compare organizer and recurrence identifiers

## Invite update or cancel behaves oddly in Apple Calendar or Gmail

Checks:

- confirm the workflow used `proton-agent invites update` or `proton-agent invites cancel`, not a manual calendar edit plus plain email
- confirm the same UID is being reused
- confirm each organizer-side change increments `SEQUENCE`
- confirm cancellations are being sent as `METHOD:CANCEL`

Important default:

- `invites cancel` sends the cancel mail first and then deletes the organizer-side CalDAV object
- this is deliberate to reduce ghost events and duplicate cancellation artifacts in Apple Calendar and Gmail

If you intentionally used `--keep-local-event`, expect more client-specific variation.

## Folder lifecycle failures

Symptoms:

- `VALIDATION_ERROR` from `mail create-folder`
- `VALIDATION_ERROR` from `mail rename-folder`
- `VALIDATION_ERROR` from `mail delete-folder`

Checks:

- pass custom folders as logical names like `Clients/Felipe`; the suite maps them to `Folders/Clients/Felipe`
- `Folders/...` is accepted directly and is not double-prefixed
- system folders such as `Inbox`, `Sent`, `Archive`, `Drafts`, `Trash`, and `Spam` are intentionally not prefixed
- avoid renaming or deleting special system folders
- if you need the exact Bridge mailbox path, inspect `mail folders` and use the returned `remote_name`

## Existing DB upgrade failures

Symptoms:

- `SQLITE_UNAVAILABLE` during startup
- `sqlite3.OperationalError: no such column: events.description`
- `sqlite3.OperationalError: no such column: invite_instances.calendar_ref`
- invite create/update/cancel failing immediately after upgrading the code

Checks:

- confirm the service is opening the expected DB path, for example `/var/lib/proton-agent/proton-agent.sqlite3`
- restart the CLI or service so startup migrations run against that DB
- inspect free disk space and filesystem permissions for the DB directory
- if migration fails, read the surfaced error details and fix that DB-level problem first instead of continuing with partial state

Current behavior:

- startup now runs explicit, idempotent SQLite migrations
- existing installs are upgraded in place with missing columns, tables, and indexes
- organizer invite workflows require the full migration set, including `invite_instances.calendar_ref`, `invite_instances.calendar_href`, and `invite_instances.calendar_etag`
- migration failures are fatal by design and are not silently skipped

## Sent message correlation looks incomplete

Checks:

- use `mail sent` or `mail sent-record SENT_REF`
- confirm Bridge SMTP returned a `message_id`
- remember that the suite stores outbound correlation locally even before the sent copy is re-synced from IMAP

Current behavior:

- direct `mail send`, `mail reply`, `mail send-draft`, and organizer invite workflows persist a local outbound record
- attachment support is strongest on direct send and reply flows

## Browser automation is intentionally not used

This version does **not** use selector automation or browser automation for Proton Calendar. That is deliberate, not a missing troubleshooting step.
