# Web Dashboard

The Quiver C2 dashboard is a Flask + HTMX application served at
`http://<FLASK_HOST>:<FLASK_PORT>` (default `http://127.0.0.1:5000`). It uses
the Pico CSS framework for styling and a dark theme by default.

The navigation bar provides links to all five pages: Dashboard, Injects,
Requests, Game Log, and Teams.

## Dashboard (`/`)

The landing page provides an at-a-glance overview of the wargame.

### Bot Status Indicator

A status badge in the header shows whether the Discord bot is online or offline.
The bot writes a heartbeat to the database every 3 seconds. If the last heartbeat
is older than 15 seconds, the indicator turns red. This section refreshes via
HTMX every 5 seconds.

### Stat Cards

Four cards display:

- **Teams** -- total number of registered teams (static)
- **Pending Requests** -- number of intel requests awaiting operator action
- **Total Injects** -- cumulative inject count
- **Total Requests** -- cumulative request count

The three dynamic stats update via a JSON endpoint (`/stats`) polled every
5 seconds by JavaScript.

### Recent Activity

A table showing the 10 most recent game events, with grouping applied (e.g.,
an inject sent to 4 teams appears as a single row). Events with expandable
content (inject text, request details) can be clicked to reveal the full text.
The table refreshes every 5 seconds, preserving the expanded/collapsed state
of rows.

## Injects Page (`/injects`)

### Inject Composer

The top section is a form for creating new injects:

- **Content** -- a text area for the inject body
- **Operator** -- optional name field (defaults to "C2")
- **Team Checkboxes** -- select which teams receive the inject; a "Select All"
  toggle is provided
- **File Attachments** -- a file input accepting multiple files (up to 50 MB total)
- **Send Inject** button -- submits via HTMX; the form area is replaced with a
  confirmation message showing which teams were targeted and how many files
  were attached

The form submits as `multipart/form-data` to `POST /injects`.

### Inject History

Below the composer, a paginated table shows all past injects ordered by most
recent. Each row displays:

- Inject ID and timestamp
- Operator name
- Targeted team names
- Delivery status (e.g., "3/4 delivered")
- Attachment count

Pagination controls at the bottom navigate between pages (10 injects per page).
The history reloads automatically after sending a new inject.

## Requests Page (`/requests`)

### Pending Request Queue

The top section shows all pending intel requests as individual cards, ordered
by submission time (oldest first, so operators process them in order).

Each card displays:

- Request ID and timestamp
- Team name
- Request content (full text)
- **Response** text area -- for the operator to type a reply
- **File Attachments** -- a file input for attaching documents to the response
- **Approve** and **Deny** buttons

Clicking Approve or Deny submits the form via HTMX. The card is replaced with
a confirmation notice showing the team name and resolution status.

**Live updates:** The queue uses JavaScript polling (`/requests/queue/sync`)
every 3 seconds. The endpoint returns JSON containing the current set of pending
request IDs and pre-rendered HTML for any new requests. The client:

1. Compares server IDs against cards currently in the DOM
2. Appends HTML for new requests
3. Removes cards for requests that are no longer pending (resolved by another
   operator or via a different browser tab)

This approach avoids replacing the entire queue, which would disrupt any
in-progress response the operator is typing.

### All Requests Table

Below the queue, a paginated table shows all requests (pending, approved,
denied) with their status, team, content preview, and resolution timestamp.
Pagination is 10 rows per page.

## Game Log Page (`/log`)

A comprehensive, filterable timeline of every event in the wargame.

### Filters

Two dropdown filters at the top:

- **Event Type** -- filter by inject_sent, inject_delivered, request_created,
  request_resolved, response_delivered, inter_team_msg, bot_connected,
  bot_reconnected
- **Team** -- filter to events involving a specific team

Changing either filter reloads the table via HTMX.

### Event Table

Events are displayed in reverse chronological order with the following columns:

- **Time** -- timestamp
- **Type** -- event type with a label and icon
- **Team** -- the team involved (or multiple teams for grouped events)
- **Summary** -- a one-line description of what happened

**Grouping:** Related events are collapsed into single rows. For example, an
inject sent to 4 teams produces 4 `inject_sent` events in the database, but
the game log displays them as one row: "Inject #5 queued by C2 to CIA, MI6,
BND, MOSSAD".

**Expandable content:** Rows with associated content (inject text, request
text, message body) can be clicked to expand and reveal the full text.

**Pagination:** 10 grouped rows per page with standard page navigation controls.

## Teams Page (`/teams`)

An overview table of all registered teams with:

- **Team name**
- **Total requests** submitted by the team
- **Pending requests** still awaiting resolution
- **Last activity** timestamp (most recent game event involving the team)
- **Channel configured** -- indicates whether the team has a real Discord
  channel ID or still has a placeholder

This page is useful before the wargame starts to verify that all teams are
properly configured and their channels are accessible.

## Live Update Behavior

The dashboard is designed for extended use during multi-hour wargame exercises.
Key design decisions for reliability:

- **No WebSockets** -- all live updates use HTTP polling (HTMX `hx-trigger`
  or JavaScript `setInterval` with `fetch`). This avoids connection management
  issues over long sessions.
- **Lightweight payloads** -- polling endpoints return small HTML partials or
  JSON rather than full pages. The request queue sync endpoint only sends HTML
  for genuinely new cards.
- **State preservation** -- the dashboard JavaScript preserves UI state (e.g.,
  expanded rows, in-progress form inputs) across polling updates by targeting
  specific DOM elements rather than replacing entire sections.
- **No client-side memory accumulation** -- resolved request cards are removed
  from the DOM, and event tables are paginated to keep the page weight constant.

These choices ensure the dashboard remains responsive and accurate over 6+
hours of continuous operation without requiring a page refresh.

## Health Endpoint

`GET /health` returns `{"status": "ok"}` with a 200 status code. This endpoint
is excluded from request logging and can be used for monitoring or load balancer
health checks.
