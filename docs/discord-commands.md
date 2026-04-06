# Discord Commands

Teams interact with Quiver through their private Discord channels. Every command
is available in both prefix form (`!command`) and slash form (`/command`).

## Prefix Commands

Prefix commands use the configured prefix (default `!`).

### !request

Submit an intelligence request to Command & Control.

```
!request <your request text>
```

**Aliases:** `!req`

**Example:**
```
!request Satellite imagery of sector 7-G from the last 48 hours
```

The bot responds with a confirmation embed containing the request ID. The request
appears in the web dashboard's pending queue for C2 operators to approve or deny.

### !msg

Send a message to one or more teams.

```
!msg <Team1,Team2,...> <message text>
```

**Aliases:** `!message`

**Examples:**
```
!msg CIA We have intel to share regarding the northern border
!msg CIA,MI6 Joint operation briefing at 1400 hours
```

Team names are comma-separated with no spaces around the commas. Names are
case-insensitive. The bot resolves each team, delivers the message to their
channel as an embed, and confirms delivery back to the sender.

If some teams cannot be reached (e.g., invalid name), the bot reports partial
success with errors for the failed deliveries.

### !status

Show your team's identity and a summary of available commands.

```
!status
```

Returns an embed with your team name, channel, and a command reference.

### !teams

List all teams participating in the wargame.

```
!teams
```

Returns an embed with team names and a total count.

### !help

Show the built-in command list with descriptions.

```
!help
!help request
```

## Slash Commands

Slash commands are registered with Discord on bot startup and appear in the
autocomplete menu when you type `/`.

### /request

Opens an input for your intel request text. Functionally identical to `!request`.

### /msg

Displays an ephemeral team selection dropdown (multi-select). After selecting one
or more recipient teams, a modal dialog opens for composing the message body.

This flow differs from `!msg` because slash commands cannot accept free-form
multi-argument input. The select menu and modal provide a guided experience.

**Flow:**
1. Type `/msg` and press Enter
2. An ephemeral message appears with a dropdown of all other teams
3. Select one or more teams, then click away or press Enter
4. A modal opens with a text area for your message
5. Type your message and submit
6. The bot delivers the message and confirms

### /status

Identical to `!status`. Returns your team identity embed.

### /teams

Identical to `!teams`. Returns the team roster embed.

## Error Handling

- **Unknown command** -- typing an unrecognized prefix command (e.g., `!foo`)
  returns an error embed suggesting `!help` or `/help`.
- **Missing arguments** -- `!request` or `!msg` without the required text returns
  an error embed naming the missing parameter.
- **Unrecognized team** -- `!msg UnknownTeam hello` returns an error listing which
  teams could not be found, with a suggestion to use `!teams`.
- **Self-messaging** -- attempting to message your own team returns an error.
- **Unbound channel** -- using a command in a channel not associated with any team
  returns an error asking the user to contact C2.
