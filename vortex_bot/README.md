# Vortex Discord Bot

A small JSON-configured Discord bot. Prefix and slash commands are generated from `config.json`.

## Setup

1. Open a terminal in `vortex_bot`.
2. Install dependencies with `pip install -r requirements.txt`.
3. Copy `.env.example` to `.env` and set `DISCORD_BOT_TOKEN` to the Vortex bot token.
4. In the Discord Developer Portal, enable **Message Content Intent** for prefix commands.
5. Start the bot with `python main.py`.

The default commands are `!ping`, `!vortex`, `/ping`, and `/vortex`. Add or edit command entries under `commands` in `config.json`; slash commands sync when the bot starts.

## Shift Types

Server administrators can run `/setup` to post the Shift Types Components V2 panel. Its arrows switch between Shift Types, Universal Nicknames, Command Levels, and Leave of Absence; each page only shows its relevant setup action. Command Levels lets administrators assign roles to Level 1 (shift management, leaderboard, LOA requests, and related commands) and Level 2 (all commands). Administrators and members with the configured Level 2 role can run `/setup`. The LOA page configures an LOA role, ping role, and request channel before setup can be completed. Each shift type has required on-shift and on-break role selections plus a required duration.

The ER:LC API page supports multiple named private-server connections. Each server must have the ER:LC API pack enabled. Add a connection name and server key in the setup panel; the key is verified and stored in plain text in the local, Git-ignored `erlc_connections.json` file, so protect that file and never share or commit it. Members with Command Level 2 or Administrator permission can run `/erlc command`, choose a linked server, search command names seen in that server's recent command logs, and supply an optional `input`. The ER:LC API does not provide a complete command catalog; custom command names can still be typed. ER:LC limits command execution to one request every five seconds per server; repeated invalid keys can cause API access to be blocked.

Members with the configured Command Level 1 or Level 2 role can use `/shift manage` and `/shift leaderboard`. Configure a **Shift Log Channel** from the Shift Types page in `/setup` first. The shift picker and active shift controls are public; lifecycle events are also posted to the configured log channel. `/active shifts` posts a public snapshot of current on-shift and on-break members with their active duration. `/shift leaderboard` ranks completed and active shift time, excluding breaks. The workflow supports starting a configured shift type, starting and ending breaks, and ending the shift. Active sessions are saved per server and member in `shift_sessions.json`, cumulative shift time in `shift_totals.json`, and log channel settings in `shift_log_channels.json`; these files are excluded from Git.
