# Quiver

Intelligence wargame management system powered by Discord and a web-based C2 dashboard.

## Features

- **Discord bot** for team interaction via prefix (`!`) and slash (`/`) commands
- **Web dashboard** (Flask + HTMX) for Command & Control operators
- **Intel inject system** -- compose injects on the web, deliver to teams via Discord
- **Intel request queue** -- teams submit requests in Discord, operators approve/deny on the web
- **Inter-team messaging** -- teams communicate through the bot with full audit logging
- **File attachments** on injects and request responses (up to 50 MB)
- **Live updates** -- dashboard polls for changes without requiring page refresh
- **Game event log** -- filterable, paginated, grouped timeline of all wargame activity
- **Bot heartbeat monitoring** -- dashboard shows real-time bot online/offline status
- **SQLite with WAL mode** -- both processes safely share a single database file

## Quick Start

### Prerequisites

- Python 3.11 or later
- A Discord bot token (see [docs/setup.md](docs/setup.md) for portal instructions)
- A Discord server with private channels for each team

### Setup

```bash
# Clone and enter the project
cd quiver

# Create a virtual environment and install
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Configure environment
cp .env.example .env
# Edit .env with your Discord token and channel IDs
```

### Environment Variables

Create a `.env` file in the project root:

```
DISCORD_TOKEN=your-bot-token-here
DATABASE_PATH=quiver.db
BOT_COMMAND_PREFIX=!
FLASK_HOST=127.0.0.1
FLASK_PORT=5000
UPLOADS_PATH=uploads
```

### Initialize the Database

```bash
python scripts/init_db.py
```

This creates the SQLite database with all tables and seeds the default team roster.

### Running

Start both the bot and web dashboard together:

```bash
python scripts/run_all.py
```

Or run them separately in two terminals:

```bash
# Terminal 1: Discord bot
python scripts/run_bot.py

# Terminal 2: Web dashboard
python scripts/run_web.py
```

The dashboard is available at `http://127.0.0.1:5000` by default.

## Architecture Overview

Quiver uses a **two-process architecture** with a shared SQLite database:

```
Teams (Discord)           C2 Operators (Browser)
      |                          |
      v                          v
 Discord Bot  <-- SQLite -->  Flask Web App
  (discord.py)   (WAL mode)   (Flask + HTMX)
```

**Discord bot** -- connects to Discord, handles team commands, and runs a 3-second
polling loop that checks the database for pending injects and approved/denied
request responses, then delivers them to the appropriate team channels.

**Flask web app** -- serves the C2 dashboard where operators compose injects,
approve or deny intel requests, and monitor game activity. Uses HTMX for
live partial updates without full page reloads.

**SQLite (WAL mode)** -- both processes connect to the same database file.
WAL (Write-Ahead Logging) mode allows concurrent readers and a single writer
without blocking. A 5-second busy timeout handles contention gracefully.

See [docs/architecture.md](docs/architecture.md) for the full design.

## Discord Commands

### Prefix Commands

| Command                     | Description                                    |
| --------------------------- | ---------------------------------------------- |
| `!request <text>`           | Submit an intel request to C2                  |
| `!msg <Team1,Team2> <text>` | Send a message to one or more teams            |
| `!status`                   | Show your team identity and available commands |
| `!teams`                    | List all teams in the wargame                  |
| `!help`                     | Show the full command list                     |

### Slash Commands

| Command    | Description                                           |
| ---------- | ----------------------------------------------------- |
| `/request` | Submit an intel request (text input)                  |
| `/msg`     | Send a message (team select menu, then compose modal) |
| `/status`  | Show your team identity                               |
| `/teams`   | List all teams                                        |

See [docs/discord-commands.md](docs/discord-commands.md) for detailed usage and examples.

## Web Dashboard Pages

| Page      | URL         | Purpose                                            |
| --------- | ----------- | -------------------------------------------------- |
| Dashboard | `/`         | Stats overview, bot status, recent activity        |
| Injects   | `/injects`  | Compose and send injects to teams                  |
| Requests  | `/requests` | Pending request queue, approve/deny with responses |
| Game Log  | `/log`      | Filterable, paginated timeline of all events       |
| Teams     | `/teams`    | Team overview with activity and channel status     |

See [docs/web-dashboard.md](docs/web-dashboard.md) for page details.

## Data Model

Eight tables track all wargame state:

- `teams` -- team roster with Discord channel mappings
- `injects` -- intel injects created by C2 operators
- `inject_recipients` -- per-team delivery tracking for each inject
- `intel_requests` -- team intel requests with status (pending/approved/denied)
- `inter_team_messages` -- messages between teams
- `game_events` -- full audit log of all wargame activity
- `attachments` -- file metadata for inject and response attachments
- `bot_heartbeat` -- single-row table tracking bot liveness

See [docs/data-model.md](docs/data-model.md) for schema details.

## Development

### Running Tests

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run a specific test module
pytest tests/test_services/test_inject_service.py
```

### Project Structure

```
quiver/
  scripts/
    init_db.py              # Database initialization
    run_all.py              # Launch both processes
    run_bot.py              # Launch bot only
    run_web.py              # Launch web only
  src/quiver/
    config.py               # Environment-based configuration
    logging_config.py       # Shared logging setup
    db/
      connection.py         # SQLite connection factory (WAL mode)
      migrate.py            # Schema and seed application
      models.py             # Frozen dataclass models
      schema.sql            # Table definitions
      seed.sql              # Default team data
    repositories/           # Data access layer (one module per table)
    services/               # Business logic layer
    bot/
      main.py               # Bot creation and startup
      embeds.py             # Discord embed builders
      utils.py              # Channel/team resolution helpers
      cogs/                 # Command modules (intel_requests, messaging, etc.)
    web/
      app.py                # Flask application factory
      routes/               # Blueprint modules (dashboard, injects, requests, etc.)
      templates/            # Jinja2 templates (pages + HTMX partials)
      static/               # CSS
  tests/                    # pytest test suite
  uploads/                  # File attachment storage (gitignored)
```

## Documentation

- [Architecture](docs/architecture.md) -- two-process design, SQLite WAL, polling
- [Setup Guide](docs/setup.md) -- prerequisites, Discord portal, environment config
- [Discord Commands](docs/discord-commands.md) -- command reference with examples
- [Web Dashboard](docs/web-dashboard.md) -- page-by-page guide
- [Data Model](docs/data-model.md) -- tables, relationships, frozen models

# TODO:

- Add linebreaks for requests (swap to modal)
- Show that a request is being worked on

Datetime:
Agency:
Contact:
Data:
Nature:
