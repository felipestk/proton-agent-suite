# Mail Workflows

All mail access goes through Proton Mail Bridge IMAP/SMTP on the same host. There is no direct Proton API path.

## Health And Folder Discovery

Bridge health:

```bash
proton-agent mail health
```

List folders and Bridge-exposed label mailboxes:

```bash
proton-agent mail folders
proton-agent --json mail folders
```

## Sync Mail

Sync one folder into local SQLite:

```bash
proton-agent mail sync --folder Inbox --since 30d
proton-agent sync mail --folder Inbox --since 30d
```

Notes:

- Sync is folder-scoped.
- `--since` accepts relative windows such as `30d`.
- Synced messages are persisted locally and assigned stable local refs.

## List, Read, Raw, Search

List synced messages:

```bash
proton-agent mail list --folder Inbox --limit 50
proton-agent --json mail list --folder Inbox --limit 50
```

Read one synced message:

```bash
proton-agent mail read MESSAGE_REF
```

Show stored raw RFC822 content:

```bash
proton-agent mail raw MESSAGE_REF
```

Search synced local messages:

```bash
proton-agent mail search "meeting" --limit 50
proton-agent --json mail search "meeting" --limit 50
```

Boundary:

- `mail search` is local over synced SQLite-backed messages.
- It is not remote IMAP server-side search.

## Attachments

List attachment refs from a synced message:

```bash
proton-agent mail attachments MESSAGE_REF
```

Save one attachment from SQLite to disk:

```bash
proton-agent mail save-attachment MESSAGE_REF ATTACHMENT_REF --out ./downloads
```

Operational note:

- `save-attachment` writes the stored attachment bytes to the requested output directory.

## Draft, Send, Reply

Send immediately:

```bash
proton-agent mail send --to bob@example.com --subject "Hello" --body-file body.txt
proton-agent mail send --to bob@example.com --subject "Hello" --stdin < body.txt
```

Create a local draft record:

```bash
proton-agent mail draft --to bob@example.com --subject "Hello" --body-file body.txt
proton-agent mail drafts
proton-agent mail send-draft DRAFT_REF
```

Reply to a synced message:

```bash
proton-agent mail reply MESSAGE_REF --body-file reply.txt
proton-agent mail reply MESSAGE_REF --stdin < reply.txt
```

Notes:

- Sending uses Bridge SMTP.
- Reply uses the synced message metadata to set reply headers.
- Drafts are stored locally until sent.

## Read State, Move, Archive

```bash
proton-agent mail mark-read MESSAGE_REF
proton-agent mail mark-unread MESSAGE_REF
proton-agent mail move MESSAGE_REF --folder Archive
proton-agent mail archive MESSAGE_REF
```

Behavior:

- Read/unread and folder changes are applied through Bridge and then reflected locally.
- `archive` moves the message to `Archive`.

## Labels

List label names:

```bash
proton-agent mail labels
```

Add or remove a Bridge label mailbox mapping:

```bash
proton-agent mail add-label MESSAGE_REF Work
proton-agent mail remove-label MESSAGE_REF Work
```

Boundary:

- Label behavior follows Proton Mail Bridge mailbox semantics.
- Labels are not arbitrary remote metadata beyond what Bridge exposes over IMAP-style mailboxes.

## JSON Usage

Prefer JSON for agent workflows:

```bash
proton-agent --json mail health
proton-agent --json mail sync --folder Inbox --since 30d
proton-agent --json mail list --folder Inbox --limit 20
proton-agent --json mail read MESSAGE_REF
proton-agent --json mail attachments MESSAGE_REF
```

Agent guidance:

- Use the returned `ref` values for later commands.
- Do not parse human-readable text when `--json` is available.
