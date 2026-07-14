# SLCRP Main Bot (24/7)

## Deploy (Railway)
1. Create a new Railway project from this GitHub repository.
2. Add environment variables from .env.example in Railway Variables.
3. To run seed features on a separate bot token, also set `FAS_SEED_BOT_TOKEN`.
4. Deploy; Procfile runs the worker continuously.

## Seed Data Persistence (Render)
The seed balances and seed shop are stored in JSON files.
On Render, the app filesystem is replaced on deploy, so these files must live on a persistent disk.

This repo is configured in `render.yaml` to:
- Mount a persistent disk at `/var/data`
- Set `SEED_DATA_DIR=/var/data/seed-data`

Files persisted there include:
- `fas_seed_bank.json`
- `fas_seed_store.json`
- `fas_predictor_v2.json`

Important:
- Do not rely on committing runtime-updated JSON files to Git on each push.
- Keep seed data on the Render disk (or Redis) so deploys do not reset balances.

## Local Run
pip install -r requirements.txt
python bot_fresh_standalone.py

## Roblox HTTPS Hook (Render)
This repo now includes a Render web service called `gag2-webhook-api` for Roblox `HttpService` events.

### 1. Configure Environment Variables (Render)
- `ROBLOX_GAME_SECRET`: shared secret used by your Roblox server script.
- `ROBLOX_EVENTS_DISCORD_WEBHOOK_URL` (optional): Discord webhook URL for incoming event logs.

### 2. Endpoint
- `POST /gag2/events`
- Header `X-Game-Secret` must match `ROBLOX_GAME_SECRET`.
- Optional header `X-Event-Timestamp` should be Unix time (seconds).

### 2b. Dashboard Website
- `GET /` serves a web dashboard for:
	- Top 1000 guilds (`/api/top-guilds`)
	- Live seed shop (`/api/live-seed-shop`)
- Set `GAG2_TOP_GUILDS_API_URL` in Render to the upstream endpoint that returns guild rankings.
- `GAG2_STOCK_API_URL` defaults to `https://api.gag2.gg/api/live/stock`.

Example body:
```json
{
  "userId": 123456789,
  "action": "harvest",
  "amount": 25,
  "metadata": {"crop": "carrot"}
}
```

### 3. Roblox Script Example
```lua
local HttpService = game:GetService("HttpService")
local URL = "https://<your-render-service>.onrender.com/gag2/events"
local SECRET = "YOUR_SHARED_SECRET"

local payload = {
	userId = player.UserId,
	action = "harvest",
	amount = 25,
	metadata = { crop = "carrot" }
}

local ok, result = pcall(function()
	return HttpService:RequestAsync({
		Url = URL,
		Method = "POST",
		Headers = {
			["Content-Type"] = "application/json",
			["X-Game-Secret"] = SECRET,
			["X-Event-Timestamp"] = tostring(os.time())
		},
		Body = HttpService:JSONEncode(payload)
	})
end)

print("webhook ok:", ok)
if ok then
	print("status:", result.StatusCode)
end
```
