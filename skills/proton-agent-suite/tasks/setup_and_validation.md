# Setup And Validation

## Runtime Requirements

- Package name: `proton-agent-suite`
- Entry point: `proton-agent`
- Python requirement: `>=3.12`

## Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

For development tools:

```bash
pip install -e .[dev]
```

## Create `.env`

```bash
cp .env.example .env
```

Or generate from the built-in sample:

```bash
proton-agent config init
```

If `.env` already exists, `config init` refuses to overwrite it unless `--force` is used.

## Important Environment Variables

From `.env.example`:

- `PROTON_AGENT_PROFILE`
- `PROTON_AGENT_DB_PATH`
- `PROTON_AGENT_BRIDGE_HOST`
- `PROTON_AGENT_BRIDGE_IMAP_PORT`
- `PROTON_AGENT_BRIDGE_SMTP_PORT`
- `PROTON_AGENT_BRIDGE_USERNAME`
- `PROTON_AGENT_BRIDGE_PASSWORD`
- `PROTON_AGENT_BRIDGE_LABEL_PREFIX`
- `PROTON_AGENT_BRIDGE_ALLOW_INSECURE_LOCALHOST`
- `PROTON_AGENT_RADICALE_BASE_URL`
- `PROTON_AGENT_RADICALE_USERNAME`
- `PROTON_AGENT_RADICALE_PASSWORD`
- `PROTON_AGENT_RADICALE_DEFAULT_CALENDAR`
- `PROTON_AGENT_RADICALE_ALLOW_INSECURE`
- `PROTON_AGENT_ICS_PUBLIC_BASE_URL`
- `CREDENTIALS_DIRECTORY`

## First-Run Validation

Run these in order:

```bash
proton-agent config init
proton-agent config validate
proton-agent diagnostics dump
proton-agent mail health
proton-agent calendar health
```

Helpful extra inspection:

```bash
proton-agent config show
proton-agent config doctor
```

Validation notes:

- `config validate` checks missing required values, insecure secret file permissions, and insecure `http://` Radicale URLs unless `PROTON_AGENT_RADICALE_ALLOW_INSECURE=true`.
- `diagnostics dump` checks config problems, SQLite accessibility, Bridge health, calendar health, and connector info.
- `mail health` tests local IMAP/SMTP reachability through Bridge.
- `calendar health` performs a CalDAV/WebDAV health request to the configured base URL.

## First Sync

```bash
proton-agent sync mail --since 30d
proton-agent sync invites
proton-agent sync calendar --days 30
```

Equivalent mail sync with explicit folder:

```bash
proton-agent sync mail --folder Inbox --since 30d
```

## Same-Host Bridge Requirement

- Proton Mail access is supported only through Proton Mail Bridge.
- Bridge must run on the same machine as the CLI.
- Typical local settings from `.env.example` are `127.0.0.1`, IMAP `1143`, SMTP `1025`.
- Do not document or build workflows that connect to Bridge on a different host.

## Local Storage Expectations

- SQLite path comes from `PROTON_AGENT_DB_PATH`.
- Default path is `./data/proton-agent.sqlite3`.
- The CLI creates parent directories for the DB path automatically.
- SQLite stores synced mail metadata, bodies, attachments, invite state, and calendar metadata.
- Secrets are loaded from environment variables or `CREDENTIALS_DIRECTORY` at runtime and are not stored in SQLite.

## Safe Fresh-Install Flow

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
proton-agent sync calendar --days 30
```
