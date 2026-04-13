CREATE TABLE IF NOT EXISTS teams (
    id                 INTEGER PRIMARY KEY,
    name               TEXT NOT NULL UNIQUE,
    discord_channel_id TEXT NOT NULL UNIQUE,
    created_at         TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE IF NOT EXISTS injects (
    id               INTEGER PRIMARY KEY,
    content          TEXT NOT NULL,
    sent_by_operator TEXT NOT NULL DEFAULT 'C2',
    created_at       TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE IF NOT EXISTS inject_recipients (
    id           INTEGER PRIMARY KEY,
    inject_id    INTEGER NOT NULL REFERENCES injects(id),
    team_id      INTEGER NOT NULL REFERENCES teams(id),
    delivered_at TEXT,
    UNIQUE(inject_id, team_id)
);

CREATE TABLE IF NOT EXISTS intel_requests (
    id                    INTEGER PRIMARY KEY,
    team_id               INTEGER NOT NULL REFERENCES teams(id),
    content               TEXT NOT NULL,
    status                TEXT NOT NULL DEFAULT 'pending'
                          CHECK(status IN ('pending', 'approved', 'denied')),
    response              TEXT,
    discord_message_id    TEXT,
    response_delivered_at TEXT,
    created_at            TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    resolved_at           TEXT
);

CREATE TABLE IF NOT EXISTS inter_team_messages (
    id           INTEGER PRIMARY KEY,
    from_team_id INTEGER NOT NULL REFERENCES teams(id),
    to_team_id   INTEGER NOT NULL REFERENCES teams(id),
    content      TEXT NOT NULL,
    created_at   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE IF NOT EXISTS game_events (
    id         INTEGER PRIMARY KEY,
    event_type TEXT NOT NULL,
    team_id    INTEGER REFERENCES teams(id),
    details    TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_inject_recipients_undelivered
    ON inject_recipients(inject_id) WHERE delivered_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_intel_requests_status
    ON intel_requests(status);

CREATE INDEX IF NOT EXISTS idx_intel_requests_undelivered_response
    ON intel_requests(id) WHERE status != 'pending' AND response_delivered_at IS NULL;

CREATE TABLE IF NOT EXISTS attachments (
    id           INTEGER PRIMARY KEY,
    inject_id    INTEGER REFERENCES injects(id),
    request_id   INTEGER REFERENCES intel_requests(id),
    filename     TEXT NOT NULL,
    stored_path  TEXT NOT NULL,
    content_type TEXT,
    size_bytes   INTEGER,
    created_at   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    CHECK(
        (inject_id IS NOT NULL AND request_id IS NULL) OR
        (inject_id IS NULL AND request_id IS NOT NULL)
    )
);

CREATE INDEX IF NOT EXISTS idx_attachments_inject
    ON attachments(inject_id) WHERE inject_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_attachments_request
    ON attachments(request_id) WHERE request_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS bot_heartbeat (
    id         INTEGER PRIMARY KEY CHECK(id = 1),
    last_beat  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    guild_count INTEGER NOT NULL DEFAULT 0
);

INSERT OR IGNORE INTO bot_heartbeat (id) VALUES (1);

CREATE INDEX IF NOT EXISTS idx_game_events_type
    ON game_events(event_type, created_at);

CREATE TABLE IF NOT EXISTS game_state (
    id         INTEGER PRIMARY KEY CHECK(id = 1),
    started_at TEXT,
    ended_at   TEXT
);

INSERT OR IGNORE INTO game_state (id) VALUES (1);
