# Vortex Discord Bot

Vortex is a Discord bot for staff shift management, activity tracking, command-level setup, LOA configuration, and ER:LC private-server API commands.

## Render Deployment

This repository includes a Render Blueprint at `render.yaml`.

1. In Render, create a new Blueprint instance from `bowser78953/slcrp-main-bot-24-7` on the `main` branch.
2. The Blueprint configures a paid `0.5c-512mb` background worker and a persistent 1 GB disk. Render bills for these resources at its current rates; review the price in your Render dashboard before confirming.
3. Set `DISCORD_BOT_TOKEN` to the Vortex bot token in the Render dashboard. Do not add the token to Git or `render.yaml`.
4. Deploy the service. The start command is `python vortex_bot/main.py`.

`VORTEX_DATA_DIR=/var/data` places shift settings, shift totals, session state, and ER:LC server keys on the persistent disk. ER:LC server keys are stored as plain text in the private disk-backed JSON file; restrict dashboard access and never share or commit that file.

## Local Development

1. Open a terminal in `vortex_bot`.
2. Install packages with `pip install -r requirements.txt`.
3. Copy `.env.example` to `.env` and set `DISCORD_BOT_TOKEN` locally.
4. Run `python main.py`.

Configure `/setup`, then use `/shift manage`, `/shift leaderboard`, `/active shifts`, or `/erlc command` as appropriate. ER:LC requires an API-enabled private server and enforces its own command rate limits.
