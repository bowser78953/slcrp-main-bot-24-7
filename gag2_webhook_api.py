import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import aiohttp
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse

app = FastAPI(title="Grow a Garden 2 Webhook API", version="1.0.0")

ROBLOX_GAME_SECRET = (os.getenv("ROBLOX_GAME_SECRET") or "").strip()
ROBLOX_EVENTS_DISCORD_WEBHOOK_URL = (os.getenv("ROBLOX_EVENTS_DISCORD_WEBHOOK_URL") or "").strip()
MAX_EVENT_AGE_SECONDS = 300
GAG2_STOCK_API_URL = (os.getenv("GAG2_STOCK_API_URL") or "https://api.gag2.gg/api/live/stock").strip()
GAG2_TOP_GUILDS_API_URL = (os.getenv("GAG2_TOP_GUILDS_API_URL") or "https://api.gag2.gg/api/live/guilds").strip()

BASE_DIR = Path(__file__).resolve().parent
DASHBOARD_DIR = BASE_DIR / "web" / "gag2-dashboard"


def _extract_top_guilds(payload: Any) -> list[dict]:
    source: list[Any] | None = None

    if isinstance(payload, list):
        source = payload
    elif isinstance(payload, dict):
        for key in ("guilds", "data", "items", "leaderboard"):
            value = payload.get(key)
            if isinstance(value, list):
                source = value
                break

    if source is None:
        return []

    normalized: list[dict] = []
    for idx, item in enumerate(source, start=1):
        if not isinstance(item, dict):
            continue

        name = str(item.get("name") or item.get("guildName") or item.get("title") or "Unknown Guild")
        rank_value = item.get("rank")
        members = item.get("members") or item.get("memberCount") or item.get("players")
        score = item.get("score") or item.get("points") or item.get("power")

        try:
            rank = int(rank_value) if rank_value is not None else idx
        except Exception:
            rank = idx

        try:
            members_int = int(members) if members is not None else None
        except Exception:
            members_int = None

        try:
            score_num = float(score) if score is not None else None
        except Exception:
            score_num = None

        normalized.append(
            {
                "rank": rank,
                "name": name,
                "members": members_int,
                "score": score_num,
            }
        )

    normalized.sort(key=lambda row: row.get("rank") or 999999)
    return normalized[:1000]


def _extract_seed_shop(payload: Any) -> tuple[list[dict], str | None]:
    seed_items: list[dict] = []
    next_restock: str | None = None

    if isinstance(payload, dict) and isinstance(payload.get("stock"), list):
        seed_shop = next((shop for shop in payload["stock"] if isinstance(shop, dict) and shop.get("category") == "seed"), None)
        if isinstance(seed_shop, dict) and isinstance(seed_shop.get("items"), list):
            for item in seed_shop["items"]:
                if not isinstance(item, dict):
                    continue
                qty = int(item.get("quantity", 0) or 0)
                if qty <= 0:
                    continue
                seed_items.append(
                    {
                        "name": str(item.get("name", "Unknown")),
                        "quantity": qty,
                    }
                )
            raw_next = seed_shop.get("nextRestockAt")
            if raw_next:
                next_restock = str(raw_next)
    elif isinstance(payload, dict) and isinstance(payload.get("stock"), dict):
        seeds = payload.get("stock", {}).get("seeds", [])
        if isinstance(seeds, list):
            for item in seeds:
                if not isinstance(item, dict):
                    continue
                qty = int(item.get("quantity", 0) or 0)
                if qty <= 0:
                    continue
                seed_items.append(
                    {
                        "name": str(item.get("name", "Unknown")),
                        "quantity": qty,
                    }
                )

        rotation = payload.get("rotation") if isinstance(payload.get("rotation"), dict) else None
        if rotation and rotation.get("expiresAt"):
            next_restock = str(rotation["expiresAt"])

    return seed_items, next_restock


async def _fetch_json(url: str) -> Any:
    headers = {
        "Accept": "application/json,text/plain,*/*",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "User-Agent": "Mozilla/5.0",
    }
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20)) as session:
        async with session.get(url, headers=headers, params={"_": int(datetime.now(timezone.utc).timestamp())}) as response:
            if response.status != 200:
                raise HTTPException(status_code=502, detail=f"Upstream API returned {response.status}")
            return await response.json()


@app.get("/")
async def dashboard_home() -> FileResponse:
    page = DASHBOARD_DIR / "index.html"
    if not page.exists():
        raise HTTPException(status_code=500, detail="Dashboard file missing")
    return FileResponse(page)


@app.get("/api/top-guilds")
async def api_top_guilds() -> dict:
    if not GAG2_TOP_GUILDS_API_URL:
        raise HTTPException(status_code=500, detail="GAG2_TOP_GUILDS_API_URL is not configured")
    payload = await _fetch_json(GAG2_TOP_GUILDS_API_URL)
    guilds = _extract_top_guilds(payload)
    return {
        "ok": True,
        "count": len(guilds),
        "guilds": guilds,
        "source": GAG2_TOP_GUILDS_API_URL,
    }


@app.get("/api/live-seed-shop")
async def api_live_seed_shop() -> dict:
    payload = await _fetch_json(GAG2_STOCK_API_URL)
    seeds, next_restock = _extract_seed_shop(payload)
    return {
        "ok": True,
        "count": len(seeds),
        "nextRestock": next_restock,
        "seeds": seeds,
        "source": GAG2_STOCK_API_URL,
    }


@app.get("/health")
async def health() -> dict:
    return {
        "ok": True,
        "service": "gag2-webhook-api",
        "timestamp": int(datetime.now(timezone.utc).timestamp()),
    }


@app.post("/gag2/events")
async def gag2_events(
    request: Request,
    x_game_secret: str | None = Header(default=None),
    x_event_timestamp: str | None = Header(default=None),
) -> dict:
    if not ROBLOX_GAME_SECRET:
        raise HTTPException(status_code=500, detail="ROBLOX_GAME_SECRET is not configured")

    if x_game_secret != ROBLOX_GAME_SECRET:
        raise HTTPException(status_code=401, detail="unauthorized")

    if x_event_timestamp:
        try:
            event_ts = int(x_event_timestamp)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="invalid x-event-timestamp") from exc

        now_ts = int(datetime.now(timezone.utc).timestamp())
        if abs(now_ts - event_ts) > MAX_EVENT_AGE_SECONDS:
            raise HTTPException(status_code=400, detail="stale event")

    payload = await request.json()

    required_keys = {"userId", "action"}
    missing = [key for key in required_keys if key not in payload]
    if missing:
        raise HTTPException(status_code=400, detail=f"missing keys: {', '.join(missing)}")

    if ROBLOX_EVENTS_DISCORD_WEBHOOK_URL:
        amount = payload.get("amount")
        amount_text = f" amount={amount}" if amount is not None else ""
        content = (
            "[GAG2 Event] "
            f"action={payload.get('action')} "
            f"userId={payload.get('userId')}"
            f"{amount_text}"
        )
        try:
            async with aiohttp.ClientSession() as session:
                await session.post(
                    ROBLOX_EVENTS_DISCORD_WEBHOOK_URL,
                    json={"content": content[:1900]},
                    timeout=aiohttp.ClientTimeout(total=10),
                )
        except Exception:
            # Keep webhook ingestion available even if Discord forwarding fails.
            pass

    return {
        "ok": True,
        "received": True,
        "action": payload.get("action"),
        "userId": payload.get("userId"),
    }
