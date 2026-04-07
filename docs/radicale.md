# Radicale notes

## Why Radicale

Radicale is used as the initial calendar provider because it is self-hosted, simple to deploy, and speaks CalDAV/WebDAV clearly.

## Expected configuration

The suite expects:

- a base user collection URL in `PROTON_AGENT_RADICALE_BASE_URL`
- basic authentication credentials
- at least one calendar collection discoverable via PROPFIND

## Provider behavior

The Radicale provider:

- performs PROPFIND discovery
- uses calendar-query REPORT for upcoming events
- stores normalized calendar and event metadata in SQLite
- exposes connector info for Apple Calendar

## HTTPS guidance

For Apple clients and remote VPS access, put Radicale behind HTTPS. A reverse proxy such as nginx or Caddy is usually the cleanest path.

## Optional public ICS exposure

The suite can advertise a read-only ICS URL if your deployment exposes one. This is optional and external to the core CLI itself.
