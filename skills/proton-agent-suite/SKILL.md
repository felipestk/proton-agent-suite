---
name: proton-agent-suite
description: Use this skill when operating, validating, or troubleshooting the proton-agent-suite CLI for local-first Proton Mail Bridge mail access, Radicale/CalDAV calendar sync, invite ingestion and RSVP, strict JSON polling, Apple Calendar connector metadata, and Linux/VPS deployment. Do not use for Proton web automation, Proton Calendar APIs, hosted services, background daemons, or non-CLI workflows.
---

# Proton Agent Suite

`proton-agent-suite` is a local-first Python CLI for deterministic mail, invite, and calendar workflows. It talks to Proton Mail through Proton Mail Bridge on the same host, talks to self-hosted calendars through CalDAV/WebDAV with Radicale as the first provider, stores synced state in local SQLite, and emits strict JSON envelopes for agent polling.

## Use This Skill For

- Installing and validating `proton-agent-suite`
- Operating mail workflows through Proton Mail Bridge IMAP/SMTP
- Syncing and inspecting invite records derived from synced email
- Operating Radicale/CalDAV calendars and Apple Calendar connector metadata
- Running deterministic `--json` polling workflows on Linux or VPS hosts

## Do Not Use This Skill For

- Proton Calendar API work
- Browser automation or web UI tasks
- Hosted/server-side search or background workers
- Remote Bridge usage from a different host
- OAuth, browser login flows, or invented connectors

## Key Constraints

- CLI-only
- Local-first
- Proton Mail access is Bridge-only
- Bridge must run on the same machine as the CLI
- Calendar access is CalDAV/WebDAV only
- Radicale is the first documented calendar provider
- No hidden daemon or background worker
- SQLite stores synced data, not secrets
- JSON mode is strict and machine-friendly
- Destructive actions are gated conservatively, including `--yes` where applicable
- Invite RSVP is conservative and may require `--force` or fail safely
- Apple Calendar: CalDAV is two-way, ICS is read-only

## Prerequisites

- Python `>=3.12`
- Linux host or VPS
- Proton Mail Bridge installed and configured on the same host
- Reachable Radicale/CalDAV endpoint
- Writable local SQLite path

## Quick Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
cp .env.example .env
proton-agent config init
proton-agent config validate
proton-agent diagnostics dump
```

Read [tasks/setup_and_validation.md](tasks/setup_and_validation.md) for the full setup and first-sync flow.

## Core Workflow

1. Validate config and local storage.
2. Check Bridge and calendar health.
3. Sync mail, then sync invites, then sync calendar.
4. Use local refs for read/search/show/respond/update operations.
5. For agent loops, prefer `--json` with `agent snapshot` and `agent changed-since`.

## High-Value Commands

```bash
proton-agent config validate
proton-agent diagnostics dump
proton-agent mail health
proton-agent sync mail --since 30d
proton-agent invites list --status pending
proton-agent invites accept INVITE_REF
proton-agent calendar connector
proton-agent sync calendar --days 30
proton-agent --json agent snapshot
proton-agent --json agent changed-since 2026-04-01T00:00:00Z
```

## JSON Contract

- Add global `--json` to get strict machine output.
- Success envelope:

```json
{"ok":true,"data":{}}
```

- Failure envelope:

```json
{"ok":false,"error":{"code":"SOME_STABLE_ERROR_CODE","message":"Human-readable explanation","details":{}}}
```

- No extra prose is emitted in JSON mode.
- Use stable local refs from prior sync output instead of scraping human text.

## Safety

- Keep Bridge bound to localhost and private.
- Do not store secrets in SQLite.
- Prefer HTTPS for Radicale.
- Treat ICS URLs as sensitive.
- Use `invites show` and `invites source` before RSVP when trust is unclear.
- Expect `calendar cancel` and `calendar delete` to require `--yes`.
- Expect unsafe or incomplete RSVP flows to fail rather than guess.

## Package Layout

- [tasks/setup_and_validation.md](tasks/setup_and_validation.md): install, env, first validation, first sync
- [tasks/mail_workflows.md](tasks/mail_workflows.md): mail recipes and Bridge boundaries
- [tasks/invites.md](tasks/invites.md): invite ingestion and RSVP safety
- [tasks/calendar_and_connector.md](tasks/calendar_and_connector.md): CalDAV, Radicale, Apple connector, event CRUD
- [tasks/sync_and_agent_polling.md](tasks/sync_and_agent_polling.md): sync loops and polling JSON
- [tasks/deployment_and_security.md](tasks/deployment_and_security.md): VPS layout, timers, credentials, trust boundaries
- [troubleshooting/common.md](troubleshooting/common.md): operational failures and fixes
- [examples/smoke_test.md](examples/smoke_test.md): safe end-to-end validation
