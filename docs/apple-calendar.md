# Apple Calendar connector notes

## Two ways to connect

### CalDAV sync

Use this when you want:

- two-way sync
- edits on iPhone/macOS to write back to Radicale
- full calendar account behavior

The suite exposes the relevant metadata with:

```bash
proton-agent calendar connector
```

That output includes:

- CalDAV base URL
- username
- default calendar name
- discovered calendar path if available

### ICS subscription

Use this only when you want:

- read-only calendar view
- a simpler subscription URL
- no edits flowing back to the server

If `PROTON_AGENT_ICS_PUBLIC_BASE_URL` is configured and the deployment exposes public ICS files, the connector output includes an `ics_url`.

## Practical differences

- CalDAV: **two-way**
- ICS: **read-only**

If Apple Calendar asks for a server/account, use the CalDAV information. If it asks for a subscription URL, use the ICS URL.

## Security

- treat CalDAV credentials as account secrets
- treat ICS URLs as sensitive if they expose private event data
- prefer HTTPS for both
