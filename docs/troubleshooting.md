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

## Browser automation is intentionally not used

This version does **not** use selector automation or browser automation for Proton Calendar. That is deliberate, not a missing troubleshooting step.
