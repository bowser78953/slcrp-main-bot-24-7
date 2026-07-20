# Discord Bot Starter (JSON Editable)

This folder is a clean starter Discord bot split into multiple files (not one giant script).
It supports both prefix commands and slash commands generated from JSON, with automatic JSON reload while the bot is running.

## Folder Layout

- `main.py` - App entry point.
- `bot/client.py` - Discord client setup and config loading.
- `bot/handlers.py` - Message command handling.
- `bot/json_store.py` - JSON load/save helper.
- `config/settings.json` - Bot token, prefix, presence settings.
- `config/commands.json` - Command names, aliases, and response mapping.
- `data/responses.json` - Response text used by commands.
- `requirements.txt` - Python package requirements.

## Setup

1. Open terminal in this folder:
   - `cd discord_bot`
2. Install packages:
   - `pip install -r requirements.txt`
3. Put your bot token into `config/settings.json`.
4. In Discord Developer Portal, enable **Message Content Intent** for your bot.
5. Run:
   - `python main.py`

## Slash Commands

- Slash commands are built from `config/commands.json` on startup.
- If you edit `config/commands.json`, the bot auto-reloads and re-syncs slash commands.
- Existing slash command text comes from `data/responses.json`.

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
