# YCF Bot

A fresh standalone Discord bot project.

## Files
- `ycf_bot.py` - Main bot entrypoint
- `tcf_bot.py` - TCF bot entrypoint
- `.env.example` - Environment variable template
- `requirements.txt` - Python dependencies
- `Procfile` - Railway/worker process command
- `render.yaml` - Render deployment config
- `start_ycf_bot.ps1` - Local Windows startup script
- `start_tcf_bot.ps1` - Local Windows startup script for TCF

## Local Setup (Windows PowerShell)
1. Open PowerShell in this folder.
2. Copy environment template:
   ```powershell
   Copy-Item .env.example .env
   ```
3. Put your Discord token in `.env` as `YCF_BOT_TOKEN`.
4. Start the bot:
   ```powershell
   .\start_ycf_bot.ps1
   ```

## Basic Commands
- `!ping`
- `!help`

Change prefix in `.env` by setting `YCF_BOT_PREFIX`.

## Run TCF Bot
1. Set `TCF_BOT_TOKEN` in `.env`.
2. Optional: set `TCF_BOT_PREFIX` and `TCF_BOT_STATUS`.
3. Start it:
   ```powershell
   .\start_tcf_bot.ps1
   ```
