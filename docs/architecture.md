# Architecture

## Two-Process Model

Quiver runs as two independent OS processes that communicate exclusively through
a shared SQLite database:

1. **Discord bot** (`scripts/run_bot.py`) -- a long-running async process built on
   discord.py that maintains a WebSocket connection to Discord.
2. **Web dashboard** (`scripts/run_web.py`) -- a Flask application serving the C2
   operator interface with HTMX-powered live updates.

Both processes can be launched together via `scripts/run_all.py`, which spawns
them as subprocesses and handles coordinated shutdown on Ctrl+C or SIGTERM.

```
+-----------------+          +-------------------+
|   Discord Bot   |          |   Flask Web App   |
|  (discord.py)   |          |  (Flask + HTMX)   |
|                 |          |                   |
| - Team commands |          | - Inject composer |
| - Delivery loop |          | - Request queue   |
| - Heartbeat     |          | - Game log        |
+--------+--------+          +---------+---------+
         |                             |
         |      +--------------+       |
         +----->|   SQLite DB  |<------+
                |  (WAL mode)  |
                +--------------+
                       |
              +--------+--------+
              |    uploads/     |
              | (file storage)  |
              +-----------------+
```

## Why Two Processes

A single process running both discord.py (async) and Flask (sync WSGI) introduces
complexity around event loop management and thread safety. Splitting them provides:

- **Isolation** -- a crash in the web server does not take down the bot, and vice
  versa. The `run_all.py` launcher detects when either exits and shuts down the
  other.
- **Simplicity** -- Flask runs as a standard synchronous WSGI app; the bot runs
  its own asyncio event loop. No need for ASGI adapters or hybrid threading.
- **Independent scaling** -- during heavy dashboard usage, the bot continues to
  deliver injects and responses on its own schedule without contention.

The tradeoff is that the two processes cannot share in-memory state. All
coordination happens through the database.

## SQLite WAL Mode

Both processes open their own connections using the shared connection factory
in `db/connection.py`. Every connection is configured with:

```python
conn.execute("PRAGMA journal_mode = WAL")
conn.execute("PRAGMA busy_timeout = 5000")
conn.execute("PRAGMA foreign_keys = ON")
conn.execute("PRAGMA synchronous = NORMAL")
```

- **WAL (Write-Ahead Logging)** allows multiple readers to proceed concurrently
  with a single writer. This is critical because the bot polls the database every
  3 seconds while the web app serves operator requests.
- **busy_timeout = 5000** -- if a write lock is held, the caller retries for up
  to 5 seconds before raising an error. In practice, writes are fast (single-row
  inserts and updates), so contention is rare.
- **foreign_keys = ON** -- enforces referential integrity between tables (e.g.,
  inject_recipients must reference a valid inject and team).
- **synchronous = NORMAL** -- a safe default for WAL mode that avoids the
  performance penalty of FULL while still protecting against corruption on
  process crash (though not power loss).

## Polling Mechanism

The bot runs a background task loop (`InjectDelivery` cog) that fires every
3 seconds:

```
Every 3 seconds:
  1. Write heartbeat to bot_heartbeat table
  2. Query inject_recipients WHERE delivered_at IS NULL
     -> For each: fetch inject content, resolve team channel, send embed + files,
        mark delivered_at
  3. Query intel_requests WHERE status != 'pending' AND response_delivered_at IS NULL
     -> For each: fetch team channel, send response embed + files,
        mark response_delivered_at
```

This polling approach was chosen over alternatives (e.g., file watches, Unix
signals, or a message queue) because:

- SQLite is already the shared state -- no additional infrastructure needed.
- 3-second latency is acceptable for a wargame exercise.
- The polling query is indexed (`idx_inject_recipients_undelivered` and
  `idx_intel_requests_undelivered_response`) and returns zero rows most of the
  time, making it extremely cheap.

## HTMX Live Updates

The web dashboard uses a combination of HTMX polling and JavaScript `fetch`
calls to keep the UI current without full page reloads:

- **Dashboard** -- stat cards update via `fetch` every 5 seconds; recent activity
  reloads via `fetch` every 5 seconds; bot status updates via `hx-get` every 5s.
- **Requests page** -- the pending queue uses JavaScript polling (`/requests/queue/sync`)
  that returns JSON with current pending IDs and HTML for new cards. The client
  compares server IDs against DOM IDs, appends new cards, and removes resolved ones.
- **Injects page** -- inject history reloads via HTMX after a new inject is sent
  (triggered by `hx-trigger="load"`).
- **Game Log** -- loads data on page load and when filters change; no automatic
  polling (operators manually refresh or navigate pages).

This approach keeps the dashboard usable for 6+ hours of continuous operation
without memory leaks or stale state accumulation.

## Data Flow Diagrams

### C2 Sends Inject

```
C2 Operator           Flask Web App           SQLite DB            Discord Bot           Team Channel
     |                      |                     |                     |                     |
     |-- POST /injects ---->|                     |                     |                     |
     |   (content, teams,   |-- INSERT inject --->|                     |                     |
     |    attachments)       |-- INSERT recipients>|                     |                     |
     |                      |-- INSERT game_events>|                     |                     |
     |                      |-- save files ------->| (uploads/)          |                     |
     |<-- inject_sent.html -|                     |                     |                     |
     |                      |                     |                     |                     |
     |                      |                     |<-- poll (3s loop) --|                     |
     |                      |                     |-- undelivered rows ->|                     |
     |                      |                     |                     |-- send embed+files ->|
     |                      |                     |<-- mark delivered --|                     |
```

### Team Submits Intel Request

```
Team Member          Discord Bot              SQLite DB            Flask Web App         C2 Operator
     |                    |                       |                     |                     |
     |-- !request text -->|                       |                     |                     |
     |                    |-- INSERT request ----->|                     |                     |
     |                    |-- INSERT game_event -->|                     |                     |
     |<-- confirm embed --|                       |                     |                     |
     |                    |                       |                     |                     |
     |                    |                       |<-- GET /requests ---|<-- open page -------|
     |                    |                       |-- pending rows ---->|-- render queue ----->|
     |                    |                       |                     |                     |
     |                    |                       |<-- POST resolve ----|<-- approve/deny ----|
     |                    |                       |-- UPDATE status --->|                     |
     |                    |                       |                     |                     |
     |                    |<-- poll (3s loop) ----|                     |                     |
     |                    |-- undelivered resp -->|                     |                     |
     |<-- response embed -|                       |                     |                     |
     |                    |-- mark delivered ---->|                     |                     |
```

### Inter-Team Messaging

```
Team A               Discord Bot              SQLite DB                               Team B
  |                       |                       |                                       |
  |-- !msg TeamB text --->|                       |                                       |
  |                       |-- INSERT message ----->|                                       |
  |                       |-- INSERT game_events ->| (sent + received)                     |
  |                       |                       |                                       |
  |                       |-- resolve Team B channel                                      |
  |                       |-- send embed ---------------------------------------->|
  |<-- confirm embed -----|                       |                                       |
```

Inter-team messages are delivered synchronously (not via the polling loop) because
the bot already has the target channel resolved when processing the command.

## Repository and Service Layers

The codebase follows a layered architecture:

- **Repositories** (`repositories/`) -- pure data access. Each module maps to one
  or two database tables and contains functions like `create`, `get_by_id`,
  `get_all`, `count`. No business logic or side effects beyond the SQL.
- **Services** (`services/`) -- business logic that coordinates repositories. For
  example, `inject_service.send_inject` creates the inject via `inject_repo` and
  then logs game events via `event_repo`.
- **Bot cogs** (`bot/cogs/`) -- Discord command handlers that call services and
  repositories, then format results as embeds.
- **Web routes** (`web/routes/`) -- Flask blueprint handlers that call services
  and repositories, then render Jinja2 templates.

All domain objects are frozen dataclasses (`db/models.py`), ensuring immutability
throughout the application.
