# Deployment on a Linux VPS

## Assumptions

- Proton Mail Bridge runs on the same VPS as `proton-agent`
- SQLite is local to the VPS filesystem
- Radicale runs locally or on a reachable internal endpoint
- Apple Calendar reaches Radicale over HTTPS

## Recommended layout

- app user: dedicated non-root Unix account
- project checkout: `/opt/proton-agent-suite`
- DB path: `/var/lib/proton-agent/proton-agent.sqlite3`
- logs: systemd journal or a restricted log path
- credentials: systemd credentials or a locked-down `.env`

## systemd considerations

You can run ad-hoc CLI commands from cron/systemd timers without a daemon.

Use systemd credentials for:

- `proton_agent_bridge_password`
- `proton_agent_radicale_password`

Expose them via `CREDENTIALS_DIRECTORY`.

## Hardening notes

- keep Bridge bound to localhost
- restrict filesystem permissions on the DB and `.env`
- back up the SQLite DB securely
- do not expose Bridge ports through firewall or reverse proxy
- terminate TLS for Radicale with a proper certificate

## Example workflow

- timer 1: `proton-agent sync mail --since 7d`
- timer 2: `proton-agent sync invites`
- timer 3: `proton-agent sync calendar --days 30`
- agent poller: `proton-agent --json agent snapshot`
