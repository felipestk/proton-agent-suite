# Calendar And Connector

Calendar access is through CalDAV/WebDAV, with Radicale as the first documented provider. There is no Proton Calendar API path.

## Health, Discovery, Calendars

Calendar endpoint health:

```bash
proton-agent calendar health
```

Discover calendars through WebDAV/CalDAV:

```bash
proton-agent calendar discover
```

List calendars:

```bash
proton-agent calendar list
proton-agent calendar calendars
```

Create a new calendar collection:

```bash
proton-agent calendar create-calendar --name "Personal"
```

## Connector Output

Show Apple Calendar connector metadata:

```bash
proton-agent calendar connector
proton-agent --json calendar connector
```

Connector output contains:

- `provider`
- `caldav_base_url`
- `username`
- `default_calendar`
- `calendar_path` when the default calendar is discovered
- `ics_url` when `PROTON_AGENT_ICS_PUBLIC_BASE_URL` is configured
- `notes` describing CalDAV and ICS behavior

## Upcoming, Changed, Show

Upcoming events:

```bash
proton-agent calendar upcoming --days 14
proton-agent calendar upcoming --days 14 --calendar default
```

Changed since a timestamp:

```bash
proton-agent calendar changed-since 2026-04-01T00:00:00Z
proton-agent calendar changed-since 2026-04-01T00:00:00Z --calendar default
```

Show one locally synced event:

```bash
proton-agent calendar show EVENT_REF
```

Important boundary:

- `calendar show` resolves from locally persisted events.
- If an event has not been synced or persisted locally yet, do not assume it can be shown by remote lookup.

## Create, Update, Reschedule, Cancel, Delete

Create an event:

```bash
proton-agent calendar create \
  --calendar default \
  --title "Demo" \
  --start "2026-04-10T09:00:00+01:00" \
  --end "2026-04-10T10:00:00+01:00"
```

Update fields:

```bash
proton-agent calendar update EVENT_REF --title "New title"
proton-agent calendar update EVENT_REF --description "Updated details" --location "Lisbon"
```

Reschedule:

```bash
proton-agent calendar reschedule EVENT_REF --start "2026-04-10T11:00:00Z" --end "2026-04-10T12:00:00Z"
```

Cancel or delete, both gated:

```bash
proton-agent calendar cancel EVENT_REF --yes
proton-agent calendar delete EVENT_REF --yes
```

Safety:

- Without `--yes`, cancel/delete fail with `VALIDATION_ERROR`.
- Destructive actions are intentionally conservative.

## CalDAV vs ICS

Exact distinction:

- CalDAV: two-way sync and write-back to the server
- ICS: read-only subscription

Apple Calendar notes:

- Use CalDAV account settings for normal two-way Apple Calendar sync.
- Use the ICS URL only for read-only subscription behavior.
- Do not paste the ICS URL into a CalDAV account form.

## Radicale Assumptions

The provider expects:

- a base user collection URL in `PROTON_AGENT_RADICALE_BASE_URL`
- basic authentication
- discoverable calendar collections via `PROPFIND`
- event retrieval through `calendar-query REPORT`

## HTTPS And Self-Signed Certificates

- Prefer HTTPS, especially for remote VPS access and Apple clients.
- If self-signed TLS is used, trust must be installed on clients intentionally.
- Do not normalize insecure HTTP unless `PROTON_AGENT_RADICALE_ALLOW_INSECURE=true` is explicitly set for a trusted path.
