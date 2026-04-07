# Common Troubleshooting

## Bridge Not Running Or Unreachable

Symptoms:

- `BRIDGE_NOT_RUNNING`
- `BRIDGE_UNREACHABLE`
- `mail health` fails immediately

Checks:

- Verify Proton Mail Bridge is running on the same host.
- Verify `PROTON_AGENT_BRIDGE_HOST`, `PROTON_AGENT_BRIDGE_IMAP_PORT`, and `PROTON_AGENT_BRIDGE_SMTP_PORT`.
- Confirm Bridge is bound to `127.0.0.1` or the intended local address.
- Run:

```bash
proton-agent diagnostics dump
proton-agent mail health
```

## Bridge Auth Failure

Symptom:

- `BRIDGE_AUTH_FAILED`

Checks:

- Re-copy Bridge username and password from Proton Mail Bridge.
- Confirm the Proton account is still signed in within Bridge.
- Confirm `.env` or `CREDENTIALS_DIRECTORY` contains the right secret.

## Bridge Port Mismatch

Symptoms:

- local TCP checks fail
- health works for one port but not the other

Fix:

- Inspect Bridge’s configured IMAP and SMTP ports.
- Update `PROTON_AGENT_BRIDGE_IMAP_PORT` and `PROTON_AGENT_BRIDGE_SMTP_PORT`.

## IMAP Or SMTP Connectivity Problems

Relevant codes:

- `BRIDGE_NOT_RUNNING`
- `BRIDGE_UNREACHABLE`
- `BRIDGE_SMTP_UNAVAILABLE`

Checks:

- Run `proton-agent diagnostics dump`.
- Ensure local firewall rules are not blocking localhost traffic.
- Confirm the CLI is running on the same host as Bridge.

## Radicale Discovery Failure

Symptoms:

- `CALENDAR_UNREACHABLE`
- `CALENDAR_DISCOVERY_FAILED`

Checks:

- Verify `PROTON_AGENT_RADICALE_BASE_URL`.
- Ensure it points at the user collection root expected by Radicale.
- Check reverse-proxy path rewriting.
- Run:

```bash
proton-agent calendar health
proton-agent calendar discover
```

## CalDAV Authentication Failure

Symptom:

- `CALENDAR_AUTH_FAILED`

Checks:

- Confirm Radicale username and password.
- Confirm the proxy forwards `Authorization` headers correctly.

## Apple Calendar Connection Mistakes

Use:

```bash
proton-agent calendar connector
```

Common mistakes:

- Using the ICS URL in a CalDAV account form
- Using the collection root when Apple needs the discovered `calendar_path`
- Failing TLS trust on a self-signed certificate

Reminder:

- CalDAV is two-way
- ICS is read-only

## TLS And Self-Signed Certificates

Symptoms:

- discovery or client connection failures despite correct host and credentials

Fixes:

- Prefer a valid public certificate on the Radicale reverse proxy.
- If self-signed TLS is required, install trust on client devices intentionally.
- Do not disable TLS validation broadly unless you explicitly accept the risk.

## Malformed ICS

Symptoms:

- `INVITE_PARSE_FAILED`
- missing organizer or attendee details

Behavior:

- The source message can still exist locally even if RSVP cannot proceed safely.
- Unsafe or incomplete RSVP pathways fail instead of pretending success.

## Duplicate Invite Confusion

The suite tracks versions by:

- UID
- organizer
- recurrence ID
- sequence

Inspect:

```bash
proton-agent invites latest
proton-agent invites show INVITE_REF
proton-agent invites source INVITE_REF
```

## Unsafe RSVP Or Forced RSVP

Relevant codes:

- `INVITE_UNSAFE_TO_RSVP`
- `NOT_IMPLEMENTED_SAFE_FALLBACK`

Checks:

- Inspect `warning_flags` and `reason_codes`.
- Confirm the source message sender matches the organizer.
- Confirm attendee, organizer, and ICS payload data are present.
- Use `--force` only when you have manually reviewed the invite and accept the risk.

## Browser Automation Is Intentionally Not Used

This project does not use browser automation for Proton Calendar or other web workflows. That is an intentional boundary, not a missing fix.
