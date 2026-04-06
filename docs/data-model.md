# Data Model

All state is stored in a single SQLite database file. The schema is defined in
`src/quiver/db/schema.sql` and applied idempotently (all `CREATE TABLE IF NOT
EXISTS`) by the `init_db` function.

## Tables

### teams

The roster of participating intelligence agencies.

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER PK | Auto-increment team ID |
| `name` | TEXT UNIQUE | Team name (e.g., "CIA", "MI6") |
| `discord_channel_id` | TEXT UNIQUE | Discord channel snowflake ID |
| `created_at` | TEXT | ISO 8601 timestamp |

Seed data is loaded from `src/quiver/db/seed.sql` using `INSERT OR IGNORE`,
making it safe to re-run initialization without duplicating teams.

### injects

Intel injects composed by C2 operators on the web dashboard.

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER PK | Auto-increment inject ID |
| `content` | TEXT | The inject body text |
| `sent_by_operator` | TEXT | Operator name (default "C2") |
| `created_at` | TEXT | ISO 8601 timestamp |

### inject_recipients

Tracks which teams should receive each inject and whether delivery has occurred.

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER PK | Auto-increment row ID |
| `inject_id` | INTEGER FK | References `injects(id)` |
| `team_id` | INTEGER FK | References `teams(id)` |
| `delivered_at` | TEXT | Set when the bot delivers to Discord; NULL = pending |

**Unique constraint:** `(inject_id, team_id)` -- a team can only be targeted
once per inject.

**Index:** `idx_inject_recipients_undelivered` -- partial index on rows where
`delivered_at IS NULL`, used by the bot's polling loop.

### intel_requests

Intel requests submitted by teams via Discord.

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER PK | Auto-increment request ID |
| `team_id` | INTEGER FK | References `teams(id)` |
| `content` | TEXT | The request text |
| `status` | TEXT | One of: `pending`, `approved`, `denied` |
| `response` | TEXT | C2 operator's response text (nullable) |
| `discord_message_id` | TEXT | Original Discord message snowflake (nullable) |
| `response_delivered_at` | TEXT | Set when the bot delivers the response |
| `created_at` | TEXT | ISO 8601 timestamp |
| `resolved_at` | TEXT | Set when the operator approves/denies |

**Check constraint:** `status IN ('pending', 'approved', 'denied')`

**Indexes:**
- `idx_intel_requests_status` -- on `status` for filtering pending requests
- `idx_intel_requests_undelivered_response` -- partial index for resolved but
  undelivered responses, used by the bot's polling loop

### inter_team_messages

Messages sent between teams via the `!msg` / `/msg` commands.

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER PK | Auto-increment message ID |
| `from_team_id` | INTEGER FK | References `teams(id)` |
| `to_team_id` | INTEGER FK | References `teams(id)` |
| `content` | TEXT | Message body |
| `created_at` | TEXT | ISO 8601 timestamp |

### game_events

Audit log of all significant actions in the wargame.

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER PK | Auto-increment event ID |
| `event_type` | TEXT | Event category (see below) |
| `team_id` | INTEGER FK | References `teams(id)` (nullable) |
| `details` | TEXT | JSON-encoded event metadata (nullable) |
| `created_at` | TEXT | ISO 8601 timestamp |

**Event types:**
- `inject_sent` -- inject queued for a team
- `inject_delivered` -- inject delivered to Discord
- `request_created` -- team submitted an intel request
- `request_resolved` -- operator approved or denied a request
- `response_delivered` -- response delivered to Discord
- `inter_team_msg` -- inter-team message sent or received
- `bot_connected` -- bot connected to Discord
- `bot_reconnected` -- bot session resumed after disconnect

**Index:** `idx_game_events_type` -- composite index on `(event_type, created_at)`
for filtered queries.

### attachments

File metadata for injects and request responses.

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER PK | Auto-increment attachment ID |
| `inject_id` | INTEGER FK | References `injects(id)` (nullable) |
| `request_id` | INTEGER FK | References `intel_requests(id)` (nullable) |
| `filename` | TEXT | Original filename |
| `stored_path` | TEXT | Path to file on disk (within `uploads/`) |
| `content_type` | TEXT | MIME type (nullable) |
| `size_bytes` | INTEGER | File size in bytes (nullable) |
| `created_at` | TEXT | ISO 8601 timestamp |

**Check constraint:** Exactly one of `inject_id` or `request_id` must be set
(XOR). An attachment belongs to either an inject or a request response, never both.

**Indexes:**
- `idx_attachments_inject` -- partial index where `inject_id IS NOT NULL`
- `idx_attachments_request` -- partial index where `request_id IS NOT NULL`

Actual files are stored in the `uploads/` directory. The `stored_path` column
contains the relative path from the project root.

### bot_heartbeat

Single-row table tracking bot liveness.

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER PK | Always 1 (enforced by CHECK constraint) |
| `last_beat` | TEXT | ISO 8601 timestamp of last heartbeat |
| `guild_count` | INTEGER | Number of Discord guilds the bot is in |

The bot updates this row every 3 seconds. The web dashboard considers the bot
online if the heartbeat is less than 15 seconds old.

## Key Relationships

```
teams
  |-- inject_recipients (team_id)
  |-- intel_requests (team_id)
  |-- inter_team_messages (from_team_id, to_team_id)
  |-- game_events (team_id)

injects
  |-- inject_recipients (inject_id)
  |-- attachments (inject_id)

intel_requests
  |-- attachments (request_id)
```

## Frozen Dataclass Models

All database entities are represented as frozen (immutable) dataclasses in
`src/quiver/db/models.py`:

- `Team`, `Inject`, `InjectRecipient`, `IntelRequest`, `InterTeamMessage`,
  `GameEvent`, `Attachment`

Each model has a `from_row(cls, row)` class method that converts a
`sqlite3.Row` (dict-like) into the dataclass. Timestamps are parsed from
ISO 8601 strings into `datetime` objects.

Frozen dataclasses enforce immutability: fields cannot be reassigned after
construction. Updates always go through the repository layer, which writes to
the database and returns a new dataclass instance.

## Repository Pattern

Data access is organized into repository modules under `src/quiver/repositories/`,
one per table or logical grouping:

- `team_repo` -- teams table
- `inject_repo` -- injects and inject_recipients tables
- `request_repo` -- intel_requests table
- `message_repo` -- inter_team_messages table
- `event_repo` -- game_events table
- `attachment_repo` -- attachments table
- `heartbeat_repo` -- bot_heartbeat table

Each module exposes functions like `create`, `get_by_id`, `get_all`, `count`,
and domain-specific queries (e.g., `get_pending`, `get_undelivered_recipients`).
All functions take a `sqlite3.Connection` as their first argument, keeping the
repository stateless and testable.
