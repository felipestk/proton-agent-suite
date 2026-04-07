# CLI reference

## Global flags

- `--json`
- `--quiet`
- `--verbose`
- `--profile NAME`
- `--db PATH`
- `--interactive`
- `--env-file PATH`

## Config

- `proton-agent config init`
- `proton-agent config doctor`
- `proton-agent config show`
- `proton-agent config validate`

## Mail

- `proton-agent mail health`
- `proton-agent mail folders`
- `proton-agent mail sync --folder Inbox --since 30d`
- `proton-agent mail list --folder Inbox --limit 50`
- `proton-agent mail read MESSAGE_REF`
- `proton-agent mail raw MESSAGE_REF`
- `proton-agent mail search "meeting"`
- `proton-agent mail send --to bob@example.com --subject "Hello" --body-file body.txt`
- `proton-agent mail draft --to bob@example.com --subject "Hello" --body-file body.txt`
- `proton-agent mail drafts`
- `proton-agent mail send-draft DRAFT_REF`
- `proton-agent mail reply MESSAGE_REF --body-file reply.txt`
- `proton-agent mail attachments MESSAGE_REF`
- `proton-agent mail save-attachment MESSAGE_REF ATTACHMENT_REF --out ./downloads`
- `proton-agent mail mark-read MESSAGE_REF`
- `proton-agent mail mark-unread MESSAGE_REF`
- `proton-agent mail move MESSAGE_REF --folder Archive`
- `proton-agent mail archive MESSAGE_REF`
- `proton-agent mail labels`
- `proton-agent mail add-label MESSAGE_REF LABEL_NAME`
- `proton-agent mail remove-label MESSAGE_REF LABEL_NAME`

## Invites

- `proton-agent invites scan`
- `proton-agent invites list --status pending`
- `proton-agent invites show INVITE_REF`
- `proton-agent invites latest`
- `proton-agent invites source INVITE_REF`
- `proton-agent invites accept INVITE_REF`
- `proton-agent invites tentative INVITE_REF`
- `proton-agent invites decline INVITE_REF`

## Calendar

- `proton-agent calendar health`
- `proton-agent calendar discover`
- `proton-agent calendar list`
- `proton-agent calendar calendars`
- `proton-agent calendar connector`
- `proton-agent calendar upcoming --days 14`
- `proton-agent calendar changed-since 2026-04-01T00:00:00Z`
- `proton-agent calendar show EVENT_REF`
- `proton-agent calendar create --calendar default --title "Demo" --start ... --end ...`
- `proton-agent calendar update EVENT_REF --title "New title"`
- `proton-agent calendar reschedule EVENT_REF --start ... --end ...`
- `proton-agent calendar cancel EVENT_REF --yes`
- `proton-agent calendar delete EVENT_REF --yes`
- `proton-agent calendar create-calendar --name "Personal"`

## Sync

- `proton-agent sync all`
- `proton-agent sync mail --folder Inbox --since 30d`
- `proton-agent sync invites`
- `proton-agent sync calendar --days 30`

## Agent polling

- `proton-agent agent snapshot`
- `proton-agent agent changed-since 2026-04-01T00:00:00Z`

## Diagnostics

- `proton-agent diagnostics dump`
