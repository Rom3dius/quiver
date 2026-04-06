# Setup Guide

## Prerequisites

- **Python 3.11+** (3.12 or 3.14 recommended)
- **pip** (comes with Python)
- A **Discord account** with permission to create applications
- A **Discord server** (guild) where you have admin rights

## 1. Discord Developer Portal

### Create the Application

1. Go to https://discord.com/developers/applications
2. Click **New Application** and name it (e.g., "Quiver C2")
3. Note the **Application ID** -- you will need it for the OAuth2 URL

### Create the Bot

1. Navigate to the **Bot** tab in the left sidebar
2. Click **Add Bot** (if not already created)
3. Under **Token**, click **Reset Token** and copy the token
4. Store this token securely -- you will put it in your `.env` file

### Configure Intents

On the same Bot page, enable:

- **Message Content Intent** -- required for prefix commands (`!request`, `!msg`)

The other default intents (Guilds, Guild Messages) are sufficient.

### Generate the Invite URL

1. Navigate to the **OAuth2** tab, then **URL Generator**
2. Under **Scopes**, select: `bot`, `applications.commands`
3. Under **Bot Permissions**, select:
   - Send Messages
   - Send Messages in Threads
   - Embed Links
   - Attach Files
   - Read Message History
   - Use Slash Commands
4. Copy the generated URL and open it in your browser to add the bot to your server

## 2. Discord Server Setup

### Create Team Channels

Create a private text channel for each team. Recommended naming: `intel-cia`,
`intel-mi6`, `intel-bnd`, etc.

For each channel:

1. Right-click the channel and select **Copy Channel ID**
   (enable Developer Mode in Discord Settings > Advanced if you do not see this)
2. Record the channel ID -- you will need it for the seed data

### Set Permissions

Each team channel should be visible only to:

- The Quiver bot
- Members of that specific team

Use Discord role-based permissions to restrict channel visibility.

## 3. Environment Configuration

Create a `.env` file in the project root:

```
DISCORD_TOKEN=your-bot-token-here
DATABASE_PATH=quiver.db
BOT_COMMAND_PREFIX=!
FLASK_HOST=127.0.0.1
FLASK_PORT=5000
UPLOADS_PATH=uploads
```

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DISCORD_TOKEN` | Yes | -- | Bot token from the Developer Portal |
| `DATABASE_PATH` | No | `quiver.db` | Path to the SQLite database file |
| `BOT_COMMAND_PREFIX` | No | `!` | Prefix for text commands |
| `FLASK_HOST` | No | `127.0.0.1` | Web dashboard bind address |
| `FLASK_PORT` | No | `5000` | Web dashboard port |
| `UPLOADS_PATH` | No | `uploads` | Directory for file attachments |

**Security note:** Never commit the `.env` file or share your bot token. Add
`.env` to `.gitignore`.

## 4. Update Team Channel IDs

Edit `src/quiver/db/seed.sql` and replace the Discord channel IDs with the
real IDs you copied from your server:

```sql
INSERT OR IGNORE INTO teams (name, discord_channel_id) VALUES
    ('CIA',    '123456789012345678'),
    ('MOSSAD', '123456789012345679'),
    ('BND',    '123456789012345680'),
    ('MI6',    '123456789012345681');
```

Add or remove teams as needed for your exercise.

## 5. Install and Initialize

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate    # Linux/macOS
# .venv\Scripts\activate     # Windows

# Install the package with dev dependencies
pip install -e ".[dev]"

# Initialize the database
python scripts/init_db.py
```

You should see: `Database initialized at quiver.db`

## 6. Running

### Both Processes (Recommended)

```bash
python scripts/run_all.py
```

This launches the bot and web dashboard as subprocesses. Press Ctrl+C to stop both.

### Separate Terminals

```bash
# Terminal 1
python scripts/run_bot.py

# Terminal 2
python scripts/run_web.py
```

## 7. Verification

1. **Bot is online** -- the bot should appear online in your Discord server.
   Check the terminal for `Bot connected as <name>`.
2. **Channel validation** -- the bot logs which team channels are valid or
   invalid on startup. Fix any invalid channel IDs in `seed.sql` and re-run
   `init_db.py` (uses `INSERT OR IGNORE`, so it is safe to re-run).
3. **Dashboard loads** -- open `http://127.0.0.1:5000` in your browser. The
   dashboard should show the bot status as online (green indicator).
4. **Test a command** -- in a team channel, type `!status`. You should see an
   embed with the team name and available commands.
5. **Test an inject** -- on the web dashboard, go to Injects, compose a message,
   select a team, and send. Within 3 seconds, the inject should appear in the
   team's Discord channel.
