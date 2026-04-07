# Smoke Test

Use this sequence on a fresh install to prove the CLI, local storage, Bridge integration, invite ingestion, and CalDAV path are working.

## Safe End-To-End Validation

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
cp .env.example .env
proton-agent config validate
proton-agent diagnostics dump
proton-agent mail health
proton-agent calendar health
proton-agent sync mail --since 30d
proton-agent sync invites
proton-agent invites scan
proton-agent sync calendar --days 30
proton-agent --json agent snapshot
```

## What Good Looks Like

- `config validate` reports no blocking config problems
- `diagnostics dump` shows DB access and both providers reachable
- `mail health` succeeds against local Bridge IMAP and SMTP
- `calendar health` succeeds against the configured CalDAV base URL
- `sync mail` returns synced message refs
- `sync invites` or `invites scan` returns scanned invite refs when invite mail exists
- `sync calendar` returns an event count
- `--json agent snapshot` returns the strict `{"ok":true,"data":...}` envelope with local state

## Optional JSON-Only Variant

```bash
proton-agent --json config validate
proton-agent --json diagnostics dump
proton-agent --json mail health
proton-agent --json calendar health
proton-agent --json sync mail --since 30d
proton-agent --json sync invites
proton-agent --json sync calendar --days 30
proton-agent --json agent snapshot
```
