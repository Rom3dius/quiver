# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build and Test Commands

```bash
# Install (editable, with dev deps)
pip install -e ".[dev]"

# Run all tests
pytest

# Run a specific test file
pytest tests/test_services/test_inject_service.py

# Run a single test by name
pytest -k test_send_inject_creates_inject_and_events

# Initialize or reset the database
python scripts/init_db.py

# Run both processes (bot + web)
python scripts/run_all.py

# Run individually
python scripts/run_bot.py
python scripts/run_web.py
```

Tests use in-memory SQLite via the `conn` fixture in `tests/conftest.py`. Bot cog tests use file-backed SQLite (backed up from the in-memory fixture) because cogs open their own connections by path. Async cog tests call `.callback(cog, ctx, ...)` to bypass discord.py command machinery.

## Architecture

Two separate processes share a single SQLite database (WAL mode):

- **Discord bot** (`src/quiver/bot/`) -- discord.py with async cogs. Handles team commands and runs a 3-second `tasks.loop` that polls the DB for pending injects and resolved request responses to deliver.
- **Flask web app** (`src/quiver/web/`) -- C2 operator dashboard. Uses HTMX for live updates. The request queue uses a custom JS incremental sync (not HTMX innerHTML) to avoid wiping form state during polling.

The bot and web never communicate directly. All coordination flows through the database:
- Web creates `inject_recipients` rows with `delivered_at=NULL` -> bot polls, delivers to Discord, marks delivered
- Bot creates `intel_requests` rows with `status='pending'` -> web displays queue -> operator resolves -> bot polls `response_delivered_at IS NULL`, delivers response

## Layered Code Organization

```
config.py              -- frozen Config dataclass from env vars
db/models.py           -- frozen dataclasses, one per table, with from_row() classmethod
repositories/          -- pure SQL data access, returns frozen models, one module per table
services/              -- business logic, orchestrates repos + event logging in transactions
bot/cogs/              -- discord.py command handlers, call services
web/routes/            -- Flask blueprints, call services and repos, return templates
```

Both bot cogs and web routes call into services, which call repositories. Neither the bot nor web layer executes SQL directly.

## Key Patterns

- **Immutable data**: All models are `@dataclass(frozen=True)`. Never mutate; create new objects.
- **Connection per request**: Web uses Flask `g.db` (opened in `before_request`, closed in `teardown_appcontext`). Bot cogs open/close connections within each method.
- **Event logging**: All state changes log to `game_events` via `event_repo.log()`. The game log UI groups consecutive related events (same inject_id, same message batch) into single display rows.
- **Incremental sync for request queue**: The pending request queue (`/requests/queue/sync`) returns JSON with current pending IDs + HTML for new cards only. JS adds new cards, removes resolved ones, never touches cards being edited. This preserves operator form input across poll cycles.
- **Slash command /msg flow**: Two-step interaction -- `TeamSelect` (multi-select dropdown) -> `ComposeModal` (message textarea). Defined in `bot/cogs/messaging.py`.

## Team Configuration

Teams are seeded from `db/seed.sql` with Discord channel IDs. The seed file is plain SQL with `INSERT OR IGNORE`. To change teams, edit `seed.sql` and re-run `init_db.py` (or delete the DB and reinitialize).

## File Attachments

Uploaded files are saved to `UPLOADS_PATH` (default: `uploads/`) with a UUID prefix for collision avoidance. The `attachments` table stores metadata; the bot reads `stored_path` and sends as `discord.File`. Files are stored on disk, not in the database.
