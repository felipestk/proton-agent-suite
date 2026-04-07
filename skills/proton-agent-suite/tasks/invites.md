# Invites

Invite records are derived from synced email stored in local SQLite. The suite scans synced messages for `text/calendar` parts and `.ics` attachments, normalizes VEVENT state, and links invite records back to source mail refs.

## Scan, List, Show

Scan synced mail for invites:

```bash
proton-agent invites scan
proton-agent sync invites
```

List latest invite records:

```bash
proton-agent invites list
proton-agent invites list --status pending
proton-agent --json invites list --status pending
```

Show one invite:

```bash
proton-agent invites show INVITE_REF
```

Show the latest version set:

```bash
proton-agent invites latest
```

Show the source message for an invite:

```bash
proton-agent invites source INVITE_REF
```

## RSVP Actions

```bash
proton-agent invites accept INVITE_REF
proton-agent invites tentative INVITE_REF
proton-agent invites decline INVITE_REF
```

Unsafe override:

```bash
proton-agent invites accept INVITE_REF --force
```

## Normalization Behavior

High-level normalization from code and tests:

- Extract ICS from `text/calendar` parts and `.ics` attachments in synced mail
- Parse `VCALENDAR` and `VEVENT`
- Track `UID`, organizer, recurrence ID, sequence, summary, start/end, method, and status
- Mark cancellations when `METHOD:CANCEL` or `STATUS:CANCELLED`
- Deduplicate versions by `UID + organizer + recurrence-id + sequence`
- Track latest invite versions and keep source message linkage

## Trust And Safety

Warnings are conservative by design. Forwarded or suspicious invites are flagged and automatic RSVP can fail with `INVITE_UNSAFE_TO_RSVP` unless `--force` is used.

Common warning causes from the implementation:

- Forwarded subject such as `Fwd:` or `Fw:`
- Forwarded-message text in the body
- Organizer/sender mismatch

Possible reason codes from the implementation:

- `FORWARDED_SUBJECT`
- `FORWARDED_BODY`
- `ORGANIZER_SENDER_MISMATCH`

## What To Inspect Before RSVP

Before responding, inspect:

```bash
proton-agent invites show INVITE_REF
proton-agent invites source INVITE_REF
```

Check for:

- `warning_flags`
- `reason_codes`
- organizer address
- source message sender and recipients
- sequence number and whether the record is the latest
- cancellation status

## Where Force Or Refusal Can Occur

Expect refusal instead of guessed behavior when:

- the invite is flagged unsafe and `--force` is not provided
- organizer data is missing
- original ICS payload is missing
- attendee address cannot be determined safely

Relevant stable error codes:

- `INVITE_UNSAFE_TO_RSVP`
- `INVITE_PARSE_FAILED`
- `NOT_IMPLEMENTED_SAFE_FALLBACK`
- `INVITE_NOT_FOUND`

## Relationship To Synced Mail

- Invite ingestion only works on mail that has already been synced locally.
- `invites source` resolves back to the synced source message.
- Re-syncing mail and re-running invite scan updates local invite state without requiring any background daemon.
