# Sync And Agent Polling

This project is designed for deterministic polling. There is no hidden daemon and no background worker requirement.

## Sync Commands

Sync everything:

```bash
proton-agent sync all
```

Sync mail:

```bash
proton-agent sync mail --folder Inbox --since 30d
```

Sync invites from already-synced mail:

```bash
proton-agent sync invites
```

Sync calendar events:

```bash
proton-agent sync calendar --days 30
```

Operational loop:

1. `sync mail`
2. `sync invites`
3. `sync calendar`
4. `agent snapshot` or `agent changed-since`

## Agent Snapshot

```bash
proton-agent agent snapshot
proton-agent --json agent snapshot
```

Snapshot includes:

- unread synced messages
- pending invites
- upcoming events
- sync status rows
- recent failures
- connector info when available

## Changed Since

```bash
proton-agent agent changed-since 2026-04-01T00:00:00Z
proton-agent --json agent changed-since 2026-04-01T00:00:00Z
```

Changed-since output includes:

- generation timestamp
- echoed `since`
- changed local refs for messages, invites, and events
- connector info when available

## JSON Mode For Agents

Always prefer global `--json` in polling loops:

```bash
proton-agent --json sync all
proton-agent --json sync mail --folder Inbox --since 7d
proton-agent --json sync invites
proton-agent --json sync calendar --days 30
proton-agent --json agent snapshot
proton-agent --json agent changed-since 2026-04-01T00:00:00Z
```

Stable envelope shapes:

```json
{"ok":true,"data":{}}
```

```json
{"ok":false,"error":{"code":"...","message":"...","details":{}}}
```

Contract notes:

- JSON mode emits no extra prose.
- Keys are deterministic and serialized compactly.
- Error handling should branch on `ok` and `error.code`, not free-form text.

## Deterministic And Polling-Oriented Behavior

- Local refs are stable hashes, not random per command output.
- Sync status is stored in SQLite and surfaced back to polling commands.
- Mail, invite, and calendar state are local-first after sync.
- `changed-since` is based on locally tracked changes, not remote server-side diff feeds.

## Stable Refs And Local State

Practical guidance:

- Store returned message, invite, event, and sync refs for follow-up commands.
- Treat SQLite as the source of local synchronized state.
- Re-sync before acting when remote state may have changed.
- Do not assume remote search or remote event lookup beyond what the explicit commands perform.
