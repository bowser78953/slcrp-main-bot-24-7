# Discord Bot Starter (JSON Editable)

This folder is a clean starter Discord bot split into multiple files (not one giant script).
It supports both prefix commands and slash commands generated from JSON, with automatic JSON reload while the bot is running.

## Folder Layout

- `main.py` - App entry point.
- `bot/client.py` - Discord client setup and config loading.
- `bot/handlers.py` - Message command handling.
- `bot/json_store.py` - JSON load/save helper.
- `config/settings.json` - Prefix and presence settings.
- `.env` - Local bot token; excluded from Git.
- `config/catagorys.json` - Category names used by the `reload` command.
- `config/commands.json` - Command names, aliases, and response mapping.
- `data/responses.json` - Response text used by commands.
- `data/saved_roles.json` - Runtime role snapshots, ignored by Git.
- `data/bot_state.json` - Runtime giveaway entries, timers, results, and ping-role settings, ignored by Git.
- `data/clear_transcripts.json` - Runtime clear transcripts, ignored by Git.
- `commands/*.json` - Optional one-file-per-command JSON (example: `commands/giveaway.json`).
- `requirements.txt` - Python package requirements.

## Setup

1. Open terminal in this folder:
   - `cd discord_bot`
2. Install packages:
   - `pip install -r requirements.txt`
3. Put your token in `.env` as `DISCORD_BOT_TOKEN=...` (copy the format from `.env.example`).
4. In Discord Developer Portal, enable **Message Content Intent** for your bot.
5. Run:
   - `python main.py`

## Render

Use a Render worker service for this bot.

- Build command: `pip install -r discord_bot/requirements.txt`
- Start command: `python discord_bot/main.py`
- Secret env var: `DISCORD_BOT_TOKEN`

The repo root includes `render.yaml`, so Render can import the service settings automatically.

## Slash Commands

- Slash commands are built from `config/commands.json` on startup.
- If you edit `config/commands.json`, the bot auto-reloads and re-syncs slash commands.
- Existing slash command text comes from `data/responses.json`.

## Role Commands

The administrator-only `!sr <user>` saves that member's assignable roles at or above role `1554533334955069632` in the current server. `!tar <user>` saves the same snapshot and removes those roles; `!gar <user>` restores the saved roles. Snapshots are kept separately for each user and server in `data/saved_roles.json`.

## Clear Commands

`!clear <number>` removes 1-1000 recent messages, saves a transcript, and logs its ID. Use `!cleartranscript <transcript ID>` to retrieve the transcript as a text file. Both commands require Manage Messages permission and are limited to the server where the transcript was created.

## Channel Lock

Use `!lockchannel` to deny Send Messages to @everyone and role `1554697553461903400` in the current channel. The bot keeps its own send permission so it can post the status embed and receive `?unlock`. Unlock restores the saved permission overwrites. Both commands require Manage Channels permission.

## Automod

Incoming member messages are checked case-insensitively for whole words listed in `config/automod.json`. Members with role `1556404763887800370` are exempt. Edit the `words` array and run `!reload automod` to apply changes immediately without restarting. Cases are logged in channel `1554592774626484404`; moderators with Manage Messages permission can record Take Action or Dismiss. These buttons record a case decision but do not automatically ban, kick, or warn the member.

## Bot Access Controls

The owner account `1332458947067773072` can toggle `!underdev`; while active, the bot is idle and only that account can use prefix or slash commands. `!disable bot <user>` asks for owner confirmation before disabling command access for a user. `!enable bot <user>` re-enables that account, including while under-development mode is active. These settings persist in `bot_state.json`.

## Edit Commands

To add a command, update two files:

1. `config/commands.json`
   - Add a command object with `description`, `response_key`, and `aliases`.
2. `data/responses.json`
   - Add matching `response_key` text.

Example command entry:

```json
"hello": {
  "description": "Say hello",
  "response_key": "hello_text",
  "aliases": ["hi"]
}
```

Example response entry:

```json
"hello_text": "Hello there!"
```

## One File Per Command (giveaway.json style)

You can create command files inside `commands/`.
Each file can define a single command and response.

Example `commands/giveaway.json`:

```json
{
   "name": "giveaway",
   "description": "Show giveaway info",
   "aliases": ["gaw", "give"],
   "response": "Giveaway is active. Use #giveaway-entry to join."
}
```

Notes:
- The bot auto-loads all `commands/*.json` files.
- These commands also become slash commands.
- If a command name exists in both `config/commands.json` and `commands/*.json`, the file in `commands/` wins.

## Reload By Catagory

Use the prefix command `-reload <catagory>` to force the bot to reload JSON files.

Example:

```text
-reload giveaway
```

The category names come from `config/catagorys.json`.

Example `config/catagorys.json`:

```json
{
   "commands": [
      "config/commands.json",
      "data/responses.json"
   ],
   "giveaway": [
      "commands/giveaway.json"
   ],
   "settings": [
      "config/settings.json"
   ]
}
```
