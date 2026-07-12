import os
import json
import re
import asyncio
import colorsys
import random
import aiohttp
from datetime import datetime, timezone
from threading import Lock
import discord
from discord import app_commands
from discord.ext import commands, tasks
from dotenv import load_dotenv

# Load only the dedicated env file for this bot.
BASE_DIR = os.path.dirname(__file__)
ENV_PATH = os.path.join(BASE_DIR, ".env.fas_farmers")
load_dotenv(dotenv_path=ENV_PATH)

# Use only the dedicated token variable for this bot.
TOKEN = (os.getenv("FAS_FARMERS_BOT_TOKEN") or "").strip()
if not TOKEN:
    print("Missing FAS_FARMERS_BOT_TOKEN in .env.fas_farmers.")
    raise SystemExit(1)

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="-", intents=intents, help_command=None)

DATA_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "data"))
VOUCH_DATA_FILE = os.path.join(DATA_DIR, "fas_farmers_reports.json")
SEED_SHOP_LIVE_FILE = os.path.join(DATA_DIR, "fas_seed_shop_live.json")
DATA_LOCK = Lock()

VOUCH_CHANNEL_ID = 1524283822512799824
SCAM_REPORT_CHANNEL_ID = 1525702427263631411
SEED_SHOP_CHANNEL_ID = 1525702441608282113
TARGET_GUILD_ID = 1521774456274686044

STOCK_API_URL = "https://api.gag2.gg/api/live/stock"
SELL_PRICE_API_URL = "https://api.gag2.gg/api/live/sell"
POLL_SECONDS = 10
SHOP_REFRESH_SECONDS = 300

RARITY_EMOJIS = {
    "common": "<:common:1525708045450084473>",
    "uncommon": "<:uncommon:1525703428821483660>",
    "rare": "<:rare:1525703476116717598>",
    "epic": "<:epic:1525703513638830141>",
    "legendary": "<:legendary:1525703562481500230>",
    "mythic": "<:Mythic:1525703606534148197>",
    "super": "<:super:1525703689459863703>",
}

STOCK_ROLE_PINGS = {
    "bamboo": "<@&1524530163155603677>",
    "cactus": "<@&1524530211453141132>",
    "corn": "<@&1524530317191549048>",
    "pineapple": "<@&1524530470526783639>",
    "mushroom": "<@&1524531045980962946>",
    "mango": "<@&1524530993636184284>",
    "green bean": "<@&1524530898773610536>",
    "grape": "<@&1524530832495083660>",
    "coconut": "<@&1524530659639562423>",
    "banana": "<@&1524530562386231416>",
    "sunflower": "<@&1524531635197055186>",
    "fire fern": "<@&1524531430036602880>",
    "dragon fruit": "<@&1524531322314555472>",
    "cherry": "<@&1524531247999746118>",
    "acorn": "<@&1524531183067730151>",
    "venom spitter": "<@&1524532091017105508>",
    "pomegranate": "<@&1524531974276907008>",
    "poison apple": "<@&1524531905066831912>",
    "venus fly trap": "<@&1524532173955272815>",
    "dragons breath": "<@&1524532301164314665>",
    "hypno bloom": "<@&1524532447893782758>",
    "moon bloom": "<@&1524532556609880215>",
    "rare sprinkler": "<@&1525725479506808892>",
    "trowel": "<@&1525725654165880903>",
    "speed mushroom": "<@&1525727705629458503>",
    "jump mushroom": "<@&1525727793386623157>",
    "basic pot": "<@&1525723932962062477>",
    "flashbang": "<@&1525724596651688016>",
    "gnome": "<@&1525724889145933854>",
    "supersize mushroom": "<@&1525725022382063687>",
    "shrink mushroom": "<@&1525725204649738311>",
    "legendary sprinkler": "<@&1525723352441032896>",
    "invisibility mushroom": "<@&1525723448578412544>",
    "super sprinkler": "<@&1525694327702028469>",
    "super watering can": "<@&1525694406018072587>",
}

# Ordered output to match requested grouping.
SEED_CONFIG = [
    {"key": "carrot", "name": "Carrot", "emoji": "<:Carrot:1525704707451129926>", "rarity": "common"},
    {"key": "strawberry", "name": "Strawberry", "emoji": "<:Strawberry:1525704796424896522>", "rarity": "common"},
    {"key": "blueberry", "name": "Blueberry", "emoji": "<:Bluebarry:1525704857619533824>", "rarity": "common"},
    {"key": "tulip", "name": "Tulip", "emoji": "<:Tulip:1525705344511246346>", "rarity": "uncommon"},
    {"key": "tomato", "name": "Tomato", "emoji": "<:Tomato:1525705290371043378>", "rarity": "uncommon"},
    {"key": "apple", "name": "Apple", "emoji": "<:Apple_Tree:1525705192505344090>", "rarity": "uncommon"},
    {"key": "bamboo", "name": "Bamboo", "emoji": "<:Bamboo:1525705734518476810>", "rarity": "rare"},
    {"key": "corn", "name": "Corn", "emoji": "<:corn:1525705776713170986>", "rarity": "rare"},
    {"key": "cactus", "name": "Cactus", "emoji": "<:cactus:1525705829460869283>", "rarity": "rare"},
    {"key": "pineapple", "name": "Pineapple", "emoji": "<:Pineapple:1525705907151835277>", "rarity": "rare"},
    {"key": "mushroom", "name": "Mushroom", "emoji": "<:Mushroom:1525706543826206841>", "rarity": "epic"},
    {"key": "green bean", "name": "Green Bean", "emoji": "<:Greenbean:1525706587665338448>", "rarity": "epic"},
    {"key": "banana", "name": "Banana", "emoji": "<:banana:1525706698508079114>", "rarity": "epic"},
    {"key": "grape", "name": "Grape", "emoji": "<:Grape:1525706763977097216>", "rarity": "epic"},
    {"key": "coconut", "name": "Coconut", "emoji": "<:Coconut:1525706808881057792>", "rarity": "epic"},
    {"key": "mango", "name": "Mango", "emoji": "<:Mango:1525706852934094980>", "rarity": "epic"},
    {"key": "dragon fruit", "name": "Dragon Fruit", "emoji": "<:Dragon_fruit:1525705792186093629>", "rarity": "legendary"},
    {"key": "acorn", "name": "Acorn", "emoji": "<:Acorn:1525705828860956773>", "rarity": "legendary"},
    {"key": "cherry", "name": "Cherry", "emoji": "<:Cherry:1525705865049673829>", "rarity": "legendary"},
    {"key": "sunflower", "name": "Sunflower", "emoji": "<:Sunflower:1525712931252207747>", "rarity": "legendary"},
    {"key": "fire fern", "name": "Fire Fern", "emoji": "<:Fire_fern:1525705922209648751>", "rarity": "legendary"},
    {"key": "venus fly trap", "name": "Venus Fly Trap", "emoji": "<:Venus_fly_trap:1525705354204151879>", "rarity": "mythic"},
    {"key": "pomegranate", "name": "Pomegranate", "emoji": "<:Pomegranate:1525705291759358094>", "rarity": "mythic"},
    {"key": "poison apple", "name": "Poison Apple", "emoji": "<:Poison_apple:1525705159152369674>", "rarity": "mythic"},
    {"key": "venom spitter", "name": "Venom Spitter", "emoji": "<:Venom_spitter:1525705106786484234>", "rarity": "mythic"},
    {"key": "moon bloom", "name": "Moon Bloom", "emoji": "<:Moon_Bloom_Seed:1524539539081662537>", "rarity": "super"},
    {"key": "hypno bloom", "name": "Hypno Bloom", "emoji": "<:Hypnobloomseed:1524538199446126622>", "rarity": "super"},
    {"key": "dragons breath", "name": "Dragons Breath", "emoji": "<:Dragons_Breath_seed:1524539236462624932>", "rarity": "super"},
]

SEED_LOOKUP = {entry["key"]: entry for entry in SEED_CONFIG}

GEAR_CONFIG = [
    {"key": "common watering can", "name": "Common Watering Can", "emoji": "<:Common_watering_can:1525708071836323981>", "rarity": "common"},
    {"key": "common sprinkler", "name": "Common Sprinkler", "emoji": "<:Common_sprinkler:1525708123602685963>", "rarity": "common"},
    {"key": "sign", "name": "Sign", "emoji": "<:Sign:1525708337617043668>", "rarity": "common"},
    {"key": "uncommon sprinkler", "name": "Uncommon Sprinkler", "emoji": "<:Uncommon_sprinkler:1525708403618615406>", "rarity": "uncommon"},
    {"key": "trowel", "name": "Trowel", "emoji": "<:Trowel:1525708482890825808>", "rarity": "rare"},
    {"key": "rare sprinkler", "name": "Rare Sprinkler", "emoji": "<:Rare_sprinkler:1525708551576748172>", "rarity": "rare"},
    {"key": "jump mushroom", "name": "Jump Mushroom", "emoji": "<:Jump_mushroom:1525708622263484517>", "rarity": "rare"},
    {"key": "speed mushroom", "name": "Speed Mushroom", "emoji": "<:Speed_mushroom:1525708776899088474>", "rarity": "rare"},
    {"key": "megaphone", "name": "Megaphone", "emoji": "<:Megaphone:1525710097878089848>", "rarity": "rare"},
    {"key": "shrink mushroom", "name": "Shrink Mushroom", "emoji": "<:Shrink_mushroom:1525709208589439016>", "rarity": "epic"},
    {"key": "supersize mushroom", "name": "Supersize Mushroom", "emoji": "<:Supersize_mushroom:1525709268508999790>", "rarity": "epic"},
    {"key": "gnome", "name": "Gnome", "emoji": "<:Gnome:1525709394107568249>", "rarity": "epic"},
    {"key": "flashbang", "name": "Flashbang", "emoji": "<:Flashbang:1525709449514451044>", "rarity": "epic"},
    {"key": "basic pot", "name": "Basic Pot", "emoji": "<:Basic_pot:1525709494397440080>", "rarity": "epic"},
    {"key": "invisibility mushroom", "name": "Invisibility Mushroom", "emoji": "<:Invisibility_mushroom:1525709653940502538>", "rarity": "legendary"},
    {"key": "legendary sprinkler", "name": "Legendary Sprinkler", "emoji": "<:Legendary_sprinkler:1525709777181736985>", "rarity": "legendary"},
    {"key": "wheelbarrow", "name": "Wheelbarrow", "emoji": "<:Wheelbarrow:1525709875450089536>", "rarity": "legendary"},
    {"key": "player magnet", "name": "Player Magnet", "emoji": "<:Player_magnet:1525709947168358400>", "rarity": "mythic"},
    {"key": "strawberry sniper", "name": "Strawberry Sniper", "emoji": "<:Strawberry_sniper:1525710013669183639>", "rarity": "mythic"},
    {"key": "super sprinkler", "name": "Super Sprinkler", "emoji": "<:super_sprinkler:1525693433908564140>", "rarity": "super"},
    {"key": "super watering can", "name": "Super Watering Can", "emoji": "<:superwateringcan:1525693459749408888>", "rarity": "super"},
]

GEAR_LOOKUP = {entry["key"]: entry for entry in GEAR_CONFIG}

SELL_PRICE_CONFIG = [
    {"name": "Ghost Pepper"},
    {"name": "Fire Fern"},
    {"name": "Rocket Pop"},
    {"name": "Mushroom"},
    {"name": "Glow Mushroom"},
    {"name": "Apple"},
    {"name": "Horned Melon"},
    {"name": "Green Bean"},
    {"name": "Carrot"},
    {"name": "Moon Bloom"},
    {"name": "Hypno Bloom"},
    {"name": "Tulip"},
    {"name": "Acorn"},
    {"name": "Pineapple"},
    {"name": "Tomato"},
    {"name": "Strawberry"},
    {"name": "Cactus"},
    {"name": "Banana"},
    {"name": "Dragon Fruit"},
    {"name": "Cherry"},
    {"name": "Poison Ivy"},
    {"name": "Briar Rose"},
    {"name": "Dragon's Breath"},
    {"name": "Baby Cactus"},
    {"name": "Blueberry"},
    {"name": "Venom Spitter"},
    {"name": "Sunflower"},
    {"name": "Coconut"},
    {"name": "Grape"},
    {"name": "Bamboo"},
    {"name": "Poison Apple"},
    {"name": "Mango"},
    {"name": "Corn"},
    {"name": "Pomegranate"},
    {"name": "Venus Fly Trap"},
]

SELL_PRICE_LOOKUP = {entry["name"].lower(): entry for entry in SELL_PRICE_CONFIG}

http_session: aiohttp.ClientSession | None = None
last_live_post_ts: int | None = None
last_stock_signature: str | None = None

GIVEAWAYS: dict[int, dict] = {}
TREE_SYNCED = False

RARITY_RANK = {
    "common": 1,
    "uncommon": 2,
    "rare": 3,
    "epic": 4,
    "legendary": 5,
    "mythic": 6,
    "super": 7,
}

RARITY_COLOR = {
    "common": 0x95A5A6,
    "uncommon": 0x2ECC71,
    "rare": 0x3498DB,
    "epic": 0x9B59B6,
    "legendary": 0xF1C40F,
    "mythic": 0xE74C3C,
}


def _ensure_data_file() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(VOUCH_DATA_FILE):
        with open(VOUCH_DATA_FILE, "w", encoding="utf-8") as f:
            json.dump({"next_vouch_id": 1, "next_scam_id": 1, "users": {}}, f, indent=2)


def _ensure_live_file() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(SEED_SHOP_LIVE_FILE):
        with open(SEED_SHOP_LIVE_FILE, "w", encoding="utf-8") as f:
            json.dump({"channel_id": None, "message_id": None}, f, indent=2)


def _load_data() -> dict:
    _ensure_data_file()
    with DATA_LOCK:
        with open(VOUCH_DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    data.setdefault("next_vouch_id", 1)
    data.setdefault("next_scam_id", 1)
    data.setdefault("users", {})
    return data


def _save_data(data: dict) -> None:
    _ensure_data_file()
    with DATA_LOCK:
        tmp = VOUCH_DATA_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, VOUCH_DATA_FILE)


def _load_live_config() -> dict:
    _ensure_live_file()
    with DATA_LOCK:
        with open(SEED_SHOP_LIVE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    data.setdefault("channel_id", None)
    data.setdefault("message_id", None)
    return data


def _save_live_config(data: dict) -> None:
    _ensure_live_file()
    with DATA_LOCK:
        tmp = SEED_SHOP_LIVE_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, SEED_SHOP_LIVE_FILE)


def _get_user_bucket(data: dict, user_id: int) -> dict:
    users = data.setdefault("users", {})
    key = str(user_id)
    if key not in users:
        users[key] = {"vouches": [], "scams": []}
    users[key].setdefault("vouches", [])
    users[key].setdefault("scams", [])
    return users[key]


def _mention_for_user(guild: discord.Guild | None, user_id: int) -> str:
    if guild:
        member = guild.get_member(user_id)
        if member:
            return member.mention
    return f"<@{user_id}>"


def _in_allowed_channel(ctx: commands.Context, channel_id: int) -> bool:
    return bool(ctx.guild and ctx.channel and ctx.channel.id == channel_id)


def _normalize_seed_name(name: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", " ", name.lower()).strip()
    cleaned = cleaned.replace("dragon s", "dragons")
    if cleaned == "venus flytrap":
        cleaned = "venus fly trap"
    return cleaned


def _normalize_sell_query(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", text.lower()).strip()


def _sell_name_aliases(name: str, key: str | None = None) -> set[str]:
    words = re.findall(r"[a-z0-9]+", name.lower())
    aliases = {
        _normalize_sell_query(name),
        _normalize_sell_query(name.replace("'", "")),
        _normalize_sell_query((key or "").replace("_", " ")),
        _normalize_sell_query((key or "").replace("_", "")),
    }
    if words:
        aliases.add("".join(word[0] for word in words if word))
        aliases.add("".join(words))
    return {alias for alias in aliases if alias}


def _resolve_sell_query(query: str, rows: list[dict]) -> list[dict]:
    normalized_query = _normalize_sell_query(query)
    if not normalized_query:
        return []
    if normalized_query == "allfruits":
        return rows

    matches: list[dict] = []
    for row in rows:
        aliases = _sell_name_aliases(str(row.get("name", "")), str(row.get("key", "")))
        if normalized_query in aliases or any(alias.startswith(normalized_query) for alias in aliases):
            matches.append(row)
            continue
        if normalized_query in _normalize_sell_query(str(row.get("name", ""))):
            matches.append(row)
    return matches


def _extract_items_by_category(payload: dict, category: str) -> list[dict]:
    if isinstance(payload, dict) and isinstance(payload.get("stock"), list):
        shop = next((shop for shop in payload["stock"] if shop.get("category") == category), None)
        if isinstance(shop, dict) and isinstance(shop.get("items"), list):
            return shop["items"]
    if isinstance(payload, dict) and payload.get("schemaVersion"):
        stock = payload.get("stock", {})
        if not isinstance(stock, dict):
            return []
        if category == "seed":
            return stock.get("seeds", [])
        if category == "gear":
            return stock.get("gear", [])
        return []
    else:
        return payload.get(category, []) if isinstance(payload, dict) else []


def _extract_seed_entries(payload: dict) -> list[dict]:
    return _extract_items_by_category(payload, "seed")


def _extract_gear_entries(payload: dict) -> list[dict]:
    return _extract_items_by_category(payload, "gear")


async def _get_http_session() -> aiohttp.ClientSession:
    global http_session
    if http_session is None or http_session.closed:
        timeout = aiohttp.ClientTimeout(total=20)
        http_session = aiohttp.ClientSession(timeout=timeout)
    return http_session


async def _fetch_sell_price_rows() -> list[dict]:
    session = await _get_http_session()
    headers = {
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
        "Referer": "https://www.gag2.gg/stock/sell",
        "Origin": "https://www.gag2.gg",
    }
    params = {"_": str(int(datetime.now(timezone.utc).timestamp()))}

    async with session.get(SELL_PRICE_API_URL, headers=headers, params=params) as response:
        response.raise_for_status()
        payload = await response.json()

    sell_data = payload.get("sell", {}) if isinstance(payload, dict) else {}
    raw_rows = sell_data.get("entries", []) if isinstance(sell_data, dict) else []
    rows: list[dict] = []
    for item in raw_rows:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        key = str(item.get("key", "")).strip()
        multiplier = item.get("multiplier")
        if not name or multiplier is None:
            continue
        try:
            multiplier_value = float(multiplier)
        except (TypeError, ValueError):
            continue
        rows.append({"name": name, "key": key, "multiplier": multiplier_value, "tier": item.get("tier")})

    rows.sort(key=lambda item: item["multiplier"], reverse=True)
    return rows


def _format_sell_multiplier(multiplier: float) -> str:
    if multiplier.is_integer():
        return f"{int(multiplier)}×"
    return f"{multiplier:.2f}".rstrip("0").rstrip(".") + "×"


def _build_sellprice_embed(rows: list[dict], title: str = "Grow A Garden 2 Sell Prices") -> discord.Embed:
    lines = []
    for index, row in enumerate(rows, start=1):
        lines.append(f"{index}. {row['name']} - {_format_sell_multiplier(float(row['multiplier']))}")

    embed = discord.Embed(
        title=title,
        description="\n".join(lines) if lines else "No sell price data could be loaded right now.",
        color=discord.Color.gold(),
        timestamp=datetime.now(timezone.utc),
    )
    return embed


def _rainbow_color_value() -> int:
    phase = (datetime.now(timezone.utc).timestamp() % 12.0) / 12.0
    r, g, b = colorsys.hsv_to_rgb(phase, 0.85, 1.0)
    return (int(r * 255) << 16) + (int(g * 255) << 8) + int(b * 255)


def _color_for_best_rarity(best_rarity: str | None) -> discord.Color:
    if best_rarity == "super":
        return discord.Color(_rainbow_color_value())
    value = RARITY_COLOR.get(str(best_rarity), 0x95A5A6)
    return discord.Color(value)


def _parse_duration_to_seconds(duration_text: str) -> int:
    total = 0
    for part in duration_text.split("_"):
        part = part.strip().lower()
        if not part:
            continue
        match = re.fullmatch(r"(\d+)([dhms])", part)
        if not match:
            raise ValueError("Invalid duration format")
        value = int(match.group(1))
        unit = match.group(2)
        if unit == "d":
            total += value * 86400
        elif unit == "h":
            total += value * 3600
        elif unit == "m":
            total += value * 60
        elif unit == "s":
            total += value
    if total <= 0:
        raise ValueError("Duration must be greater than 0")
    return total


def _build_giveaway_embed(giveaway: dict) -> discord.Embed:
    entries_count = len(giveaway["entries"])
    if giveaway.get("ended"):
        time_display = "Ended"
    else:
        time_display = f"<t:{giveaway['end_ts']}:R>"

    embed = discord.Embed(
        description=f"## {giveaway['prize']}\n{giveaway['description']}",
        color=discord.Color.blurple(),
        timestamp=datetime.now(timezone.utc),
    )
    embed.add_field(name="<:Winners:1525734637383450634> Winners", value=str(giveaway["winner_count"]), inline=True)
    embed.add_field(name="<:Entrees:1525734579099533413> Entrees", value=str(entries_count), inline=True)
    embed.add_field(name="<:Time:1525734537940701266> Time", value=time_display, inline=True)
    return embed


class GiveawayView(discord.ui.View):
    def __init__(self, giveaway_key: int):
        super().__init__(timeout=None)
        self.giveaway_key = giveaway_key

    @discord.ui.button(label="🎉 Join the giveaway!", style=discord.ButtonStyle.success, custom_id="fas_giveaway_join")
    async def join_giveaway(self, interaction: discord.Interaction, button: discord.ui.Button):
        giveaway = GIVEAWAYS.get(self.giveaway_key)
        if giveaway is None or giveaway.get("ended"):
            await interaction.response.send_message("This giveaway has ended.", ephemeral=True)
            return

        user_id = interaction.user.id
        if user_id in giveaway["entries"]:
            await interaction.response.send_message("You are already in this giveaway!", ephemeral=True)
            return

        giveaway["entries"].add(user_id)
        await interaction.response.send_message("You have entered this giveaway! Good luck!", ephemeral=True)

        message = interaction.message
        if message:
            await message.edit(embed=_build_giveaway_embed(giveaway), view=self)


async def _finish_giveaway(giveaway_key: int):
    giveaway = GIVEAWAYS.get(giveaway_key)
    if not giveaway:
        return

    wait_for = max(0, giveaway["end_ts"] - int(datetime.now(timezone.utc).timestamp()))
    await asyncio.sleep(wait_for)

    giveaway = GIVEAWAYS.get(giveaway_key)
    if not giveaway:
        return

    giveaway["ended"] = True
    channel = bot.get_channel(giveaway["channel_id"])
    if channel is None:
        try:
            channel = await bot.fetch_channel(giveaway["channel_id"])
        except Exception:
            return
    if not isinstance(channel, discord.TextChannel):
        return

    try:
        message = await channel.fetch_message(giveaway["message_id"])
    except Exception:
        return

    view = GiveawayView(giveaway_key)
    for child in view.children:
        if isinstance(child, discord.ui.Button):
            child.disabled = True

    await message.edit(embed=_build_giveaway_embed(giveaway), view=view)

    entries = list(giveaway["entries"])
    if not entries:
        await channel.send(f"🎉 Giveaway ended for **{giveaway['prize']}**! No valid entries.")
        return

    winner_count = min(giveaway["winner_count"], len(entries))
    winners = random.sample(entries, k=winner_count)
    winner_mentions = " ".join(f"<@{winner_id}>" for winner_id in winners)
    await channel.send(f"🎉 Giveaway ended for **{giveaway['prize']}**!\nWinner(s): {winner_mentions}")


async def _create_giveaway_message(*, giveaway_key: int, channel: discord.abc.Messageable, channel_id: int, prize: str, description: str, duration_seconds: int, winner_count: int) -> discord.Message:
    now_ts = int(datetime.now(timezone.utc).timestamp())
    end_ts = now_ts + duration_seconds
    giveaway = {
        "prize": prize,
        "description": description,
        "end_ts": end_ts,
        "winner_count": winner_count,
        "entries": set(),
        "ended": False,
        "channel_id": channel_id,
        "message_id": None,
    }
    GIVEAWAYS[giveaway_key] = giveaway

    view = GiveawayView(giveaway_key)
    embed = _build_giveaway_embed(giveaway)
    message = await channel.send(content="@everyone", embed=embed, view=view, allowed_mentions=discord.AllowedMentions(everyone=True))
    giveaway["message_id"] = message.id
    asyncio.create_task(_finish_giveaway(giveaway_key))
    return message


async def _fetch_stock_lines_and_next_restock() -> tuple[list[str], list[str], str | None, int | None, str | None, list[str]]:
    session = await _get_http_session()
    now_unix = int(datetime.now(timezone.utc).timestamp())
    headers = {
        "Accept": "application/json,text/plain,*/*",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Referer": "https://www.gag2.gg/stock",
        "Origin": "https://www.gag2.gg",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }
    async with session.get(STOCK_API_URL, headers=headers, params={"_": now_unix}) as resp:
        if resp.status != 200:
            raise RuntimeError(f"Stock API HTTP {resp.status}")
        payload = await resp.json()

    raw_seeds = _extract_seed_entries(payload)
    raw_gear = _extract_gear_entries(payload)
    in_stock: dict[str, int] = {}
    for item in raw_seeds:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        qty = int(item.get("quantity", 0) or 0)
        if not name or qty <= 0:
            continue
        key = _normalize_seed_name(name)
        in_stock[key] = qty

    gear_in_stock: dict[str, int] = {}
    for item in raw_gear:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        qty = int(item.get("quantity", 0) or 0)
        if not name or qty <= 0:
            continue
        key = _normalize_seed_name(name)
        gear_in_stock[key] = qty

    lines: list[str] = []
    gear_lines: list[str] = []
    best_rarity: str | None = None
    role_mentions: list[str] = []
    for entry in SEED_CONFIG:
        key = entry["key"]
        if key not in in_stock:
            continue
        qty = in_stock[key]
        rarity = entry.get("rarity")
        rarity_emoji = RARITY_EMOJIS.get(str(rarity), "") if rarity else ""
        if rarity_emoji:
            lines.append(f"{entry['emoji']} {entry['name']} {rarity_emoji} `x{qty}`")
        else:
            lines.append(f"{entry['emoji']} {entry['name']} `x{qty}`")

        if rarity and (best_rarity is None or RARITY_RANK.get(str(rarity), 0) > RARITY_RANK.get(str(best_rarity), 0)):
            best_rarity = str(rarity)

        role_mention = STOCK_ROLE_PINGS.get(key)
        if role_mention:
            role_mentions.append(role_mention)

    for entry in GEAR_CONFIG:
        key = entry["key"]
        if key not in gear_in_stock:
            continue
        qty = gear_in_stock[key]
        rarity = entry.get("rarity")
        rarity_emoji = RARITY_EMOJIS.get(str(rarity), "") if rarity else ""
        if rarity_emoji:
            gear_lines.append(f"{entry['emoji']} {entry['name']} {rarity_emoji} `x{qty}`")
        else:
            gear_lines.append(f"{entry['emoji']} {entry['name']} `x{qty}`")

        if rarity and (best_rarity is None or RARITY_RANK.get(str(rarity), 0) > RARITY_RANK.get(str(best_rarity), 0)):
            best_rarity = str(rarity)

        role_mention = STOCK_ROLE_PINGS.get(key)
        if role_mention:
            role_mentions.append(role_mention)

    next_restock_text: str | None = None
    next_restock_unix: int | None = None
    try:
        if isinstance(payload, dict) and isinstance(payload.get("stock"), list):
            seed_shop = next((shop for shop in payload["stock"] if shop.get("category") == "seed"), None)
            next_restock_at = seed_shop.get("nextRestockAt") if isinstance(seed_shop, dict) else None
            if next_restock_at:
                dt = datetime.fromisoformat(str(next_restock_at).replace("Z", "+00:00"))
                next_restock_unix = int(dt.timestamp())
                next_restock_text = f"<t:{next_restock_unix}:R>"
        if isinstance(payload, dict) and payload.get("schemaVersion"):
            rotation = payload.get("rotation", {})
            expires_at = rotation.get("expiresAt") if isinstance(rotation, dict) else None
            if expires_at:
                dt = datetime.fromisoformat(str(expires_at).replace("Z", "+00:00"))
                next_restock_unix = int(dt.timestamp())
                next_restock_text = f"<t:{next_restock_unix}:R>"
    except Exception:
        next_restock_text = None
        next_restock_unix = None

    return lines, gear_lines, next_restock_text, next_restock_unix, best_rarity, role_mentions


def _compose_seed_shop_embed(lines: list[str], gear_lines: list[str], next_restock_text: str | None, best_rarity: str | None) -> discord.Embed:
    if not lines:
        lines = ["No tracked seeds in stock right now."]

    seed_block = "\n".join(f"• {line}" for line in lines) if lines else "No tracked seeds in stock right now."
    gear_block = "\n".join(f"• {line}" for line in gear_lines) if gear_lines else "No tracked gear in stock right now."

    embed = discord.Embed(
        title="Grow a Garden 2 Stock",
        description="🌱 **SEED STOCK**\n\n" + seed_block + "\n\n🛠️ **GEAR STOCK**\n\n" + gear_block,
        color=_color_for_best_rarity(best_rarity),
        timestamp=datetime.now(timezone.utc),
    )
    if next_restock_text:
        embed.add_field(name="Next Shop Refresh", value=next_restock_text, inline=False)
    embed.set_footer(text="Posts when the shop refreshes (about every 5 minutes)")
    return embed


async def _build_seed_shop_embed() -> discord.Embed:
    lines, gear_lines, next_restock_text, _, best_rarity, _ = await _fetch_stock_lines_and_next_restock()
    return _compose_seed_shop_embed(lines, gear_lines, next_restock_text, best_rarity)


def _build_stock_ping_content(role_mentions: list[str]) -> str | None:
    if not role_mentions:
        return None
    unique_mentions = list(dict.fromkeys(role_mentions))
    return " ".join(unique_mentions)


async def _resolve_seed_shop_channel() -> discord.TextChannel | None:
    channel = bot.get_channel(SEED_SHOP_CHANNEL_ID)
    if channel is None:
        try:
            channel = await bot.fetch_channel(SEED_SHOP_CHANNEL_ID)
        except Exception:
            return None
    return channel if isinstance(channel, discord.TextChannel) else None


async def _ensure_seed_shop_live_message_exists() -> None:
    global last_live_post_ts, last_stock_signature
    config = _load_live_config()
    config["channel_id"] = SEED_SHOP_CHANNEL_ID

    channel = await _resolve_seed_shop_channel()
    if channel is None:
        _save_live_config(config)
        return

    lines, gear_lines, next_restock_text, _next_restock_unix, best_rarity, role_mentions = await _fetch_stock_lines_and_next_restock()
    embed = _compose_seed_shop_embed(lines, gear_lines, next_restock_text, best_rarity)
    message = await channel.send(embed=embed, content=_build_stock_ping_content(role_mentions))
    config["message_id"] = message.id
    _save_live_config(config)
    last_live_post_ts = int(datetime.now(timezone.utc).timestamp())
    last_stock_signature = "\n".join(lines + ["---"] + gear_lines)


async def _update_seed_shop_live_message() -> None:
    global last_live_post_ts, last_stock_signature
    config = _load_live_config()
    channel_id = int(config.get("channel_id") or SEED_SHOP_CHANNEL_ID)
    if not channel_id:
        return

    channel = bot.get_channel(int(channel_id))
    if channel is None:
        try:
            channel = await bot.fetch_channel(int(channel_id))
        except Exception:
            return

    if not isinstance(channel, discord.TextChannel):
        return

    try:
        lines, gear_lines, next_restock_text, _next_restock_unix, best_rarity, role_mentions = await _fetch_stock_lines_and_next_restock()
        now_unix = int(datetime.now(timezone.utc).timestamp())

        stock_signature = "\n".join(lines + ["---"] + gear_lines)
        should_post = bool(stock_signature and stock_signature != last_stock_signature)
        if should_post and last_live_post_ts is not None and (now_unix - last_live_post_ts) < 2:
            should_post = False

        if should_post:
            embed = _compose_seed_shop_embed(lines, gear_lines, next_restock_text, best_rarity)
            message = await channel.send(embed=embed, content=_build_stock_ping_content(role_mentions))
            config["message_id"] = message.id
            _save_live_config(config)
            last_live_post_ts = now_unix
            last_stock_signature = stock_signature
    except Exception as exc:
        print(f"Seed shop live update failed: {exc}")


@tasks.loop(seconds=POLL_SECONDS)
async def seed_shop_live_loop():
    await _update_seed_shop_live_message()


@seed_shop_live_loop.before_loop
async def before_seed_shop_live_loop():
    await bot.wait_until_ready()


@bot.event
async def on_ready():
    global TREE_SYNCED
    if bot.user:
        print(f"{bot.user} is online.")
    if not TREE_SYNCED:
        guild_obj = discord.Object(id=TARGET_GUILD_ID)
        bot.tree.clear_commands(guild=guild_obj)
        bot.tree.copy_global_to(guild=guild_obj)

        for attempt in range(1, 6):
            try:
                await bot.tree.sync(guild=guild_obj)
                await bot.tree.sync()
                TREE_SYNCED = True
                print(f"Slash commands synced (guild {TARGET_GUILD_ID} + global).")
                break
            except Exception as exc:
                print(f"Slash sync attempt {attempt}/5 failed: {exc}")
                if attempt < 5:
                    await asyncio.sleep(attempt * 2)
    try:
        await _ensure_seed_shop_live_message_exists()
    except Exception as exc:
        print(f"Failed to initialize live seed shop message: {exc}")
    if not seed_shop_live_loop.is_running():
        seed_shop_live_loop.start()


@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.CommandNotFound):
        message = "That slash command is stale. Please close and reopen Discord (or Ctrl+R) and try again."
    else:
        message = "Something went wrong while running that slash command."

    try:
        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)
    except Exception:
        pass


@bot.command(name="ping")
async def ping(ctx: commands.Context):
    await ctx.send("Pong!")


@bot.tree.command(name="giveaway", description="Create a giveaway")
@app_commands.describe(prize="Giveaway prize", description="Giveaway description", time="Duration like 1d_1h_1m_1s", amount_of_winners="How many winners")
async def giveaway_slash(interaction: discord.Interaction, prize: str, description: str, time: str, amount_of_winners: app_commands.Range[int, 1, 100]):
    try:
        duration_seconds = _parse_duration_to_seconds(time)
    except ValueError:
        await interaction.response.send_message("Invalid time format. Use like 1d_1h_1m_1s.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)
    if interaction.channel is None:
        await interaction.followup.send("Could not create giveaway in this channel.", ephemeral=True)
        return

    await _create_giveaway_message(
        giveaway_key=interaction.id,
        channel=interaction.channel,
        channel_id=interaction.channel_id,
        prize=prize,
        description=description,
        duration_seconds=duration_seconds,
        winner_count=int(amount_of_winners),
    )
    await interaction.followup.send("Giveaway created.", ephemeral=True)


@bot.command(name="seedshop")
async def seedshop(ctx: commands.Context):
    try:
        embed = await _build_seed_shop_embed()
        await ctx.send(embed=embed)
    except Exception as exc:
        await ctx.send(f"Could not fetch live seed stock right now: {exc}")


@bot.command(name="seedshoplive")
async def seedshoplive(ctx: commands.Context):
    channel = await _resolve_seed_shop_channel()
    if channel is None:
        await ctx.send(f"I could not access <#{SEED_SHOP_CHANNEL_ID}>.")
        return

    try:
        embed = await _build_seed_shop_embed()
    except Exception as exc:
        await ctx.send(f"Could not start live seed shop: {exc}")
        return

    message = await channel.send(embed=embed)
    _save_live_config({"channel_id": SEED_SHOP_CHANNEL_ID, "message_id": message.id})
    await ctx.send(f"Live seed shop started in <#{SEED_SHOP_CHANNEL_ID}>. This message refreshes every 5 minutes.")
    await _update_seed_shop_live_message()


@bot.command(name="seedshopstop")
async def seedshopstop(ctx: commands.Context):
    _save_live_config({"channel_id": None, "message_id": None})
    await ctx.send("Live seed shop updates stopped.")


@bot.command(name="sellprice")
async def sellprice(ctx: commands.Context, *, fruit_name: str):
    query = fruit_name.strip()
    if not query:
        await ctx.send("Usage: -sellprice <Fruit_Name/Fruit_abbreviation/all_fruits>")
        return

    try:
        rows = await _fetch_sell_price_rows()
    except Exception as exc:
        await ctx.send(f"Could not fetch live sell prices right now: {exc}")
        return

    if _normalize_sell_query(query) == "allfruits":
        if not rows:
            await ctx.send("I could not load the live sell price list right now.")
            return
        await ctx.send(embed=_build_sellprice_embed(rows, title="Grow A Garden 2 Sell Prices - All Fruits"))
        return

    matches = _resolve_sell_query(query, rows)
    if not matches:
        await ctx.send(f"I could not find a fruit matching `{query}`.")
        return

    if len(matches) > 1:
        match_names = ", ".join(entry["name"] for entry in matches[:8])
        suffix = "" if len(matches) <= 8 else f" and {len(matches) - 8} more"
        await ctx.send(f"That abbreviation is ambiguous. Try one of: {match_names}{suffix}.")
        return

    selected_row = matches[0]
    embed = _build_sellprice_embed([selected_row], title=f"{selected_row['name']} Sell Price")
    embed.description = f"{selected_row['name']} - {_format_sell_multiplier(float(selected_row['multiplier']))}"
    await ctx.send(embed=embed)


@bot.command(name="vouch")
async def vouch(ctx: commands.Context, user: discord.Member, *, reason: str):
    if not _in_allowed_channel(ctx, VOUCH_CHANNEL_ID):
        await ctx.send(f"This command can only be used in <#{VOUCH_CHANNEL_ID}>.")
        return

    data = _load_data()
    bucket = _get_user_bucket(data, user.id)
    entry_id = int(data.get("next_vouch_id", 1))
    data["next_vouch_id"] = entry_id + 1
    bucket["vouches"].append({"id": entry_id, "by": ctx.author.id, "reason": reason.strip(), "created_at": datetime.now(timezone.utc).isoformat()})
    _save_data(data)
    await ctx.send(f"Added vouch for {user.mention}. Vouch ID: {entry_id}")


@bot.command(name="sreport")
async def sreport(ctx: commands.Context, user: discord.Member, *, reason: str):
    if not _in_allowed_channel(ctx, SCAM_REPORT_CHANNEL_ID):
        await ctx.send(f"This command can only be used in <#{SCAM_REPORT_CHANNEL_ID}>.")
        return

    data = _load_data()
    bucket = _get_user_bucket(data, user.id)
    entry_id = int(data.get("next_scam_id", 1))
    data["next_scam_id"] = entry_id + 1
    bucket["scams"].append({"id": entry_id, "reported_by": ctx.author.id, "reason": reason.strip(), "created_at": datetime.now(timezone.utc).isoformat()})
    _save_data(data)

    report_message = f"{ctx.author.mention} has reported {user.mention} for {reason.strip()}"
    scam_channel = bot.get_channel(SCAM_REPORT_CHANNEL_ID)
    if isinstance(scam_channel, discord.TextChannel):
        await scam_channel.send(report_message)
    else:
        await ctx.send(f"I could not access <#{SCAM_REPORT_CHANNEL_ID}> to post the report message.")
        return

    await ctx.send(f"Scam report added for {user.mention}. Scam ID: {entry_id}")


@bot.command(name="vouchlist")
async def vouchlist(ctx: commands.Context, user: discord.Member):
    data = _load_data()
    bucket = _get_user_bucket(data, user.id)
    vouches = bucket.get("vouches", [])
    scams = bucket.get("scams", [])

    vouch_lines = []
    for index, item in enumerate(vouches, start=1):
        by_user_id = int(item.get("by", 0))
        reason = str(item.get("reason", "No reason provided"))
        item_id = item.get("id", "?")
        vouch_lines.append(f"{index}. {by_user_id} {reason} <ID: {item_id}>")

    scam_lines = []
    for index, item in enumerate(scams, start=1):
        by_user_id = int(item.get("reported_by", 0))
        reason = str(item.get("reason", "No reason provided"))
        item_id = item.get("id", "?")
        scam_lines.append(f"{index}. {by_user_id} {reason} <ID: {item_id}>")

    vouch_text = "\n".join(vouch_lines) if vouch_lines else "None"
    scam_text = "\n".join(scam_lines) if scam_lines else "None"

    embed = discord.Embed(title=f"{user.display_name} Vouch and Scam Reports", color=discord.Color.green())
    embed.description = (
        f"User: {user.mention}\n\n"
        f"<:vouch_list:1525700827426066472>Vouch Reports: {len(vouches)}\n\n"
        f"<:Scam_list:1525701001858908251>Scam Reports: {len(scams)}\n\n"
        f"Vouch list,\n{vouch_text}\n\n"
        f"Scam List,\n{scam_text}"
    )

    if len(embed.description) > 4096:
        embed.description = (
            f"User: {user.mention}\n\n"
            f"<:vouch_list:1525700827426066472>Vouch Reports: {len(vouches)}\n\n"
            f"<:Scam_list:1525701001858908251>Scam Reports: {len(scams)}\n\n"
            "List is too long to display in one embed."
        )

    await ctx.send(embed=embed)


@bot.command(name="vouchremove")
async def vouchremove(ctx: commands.Context, vouch_id: int):
    data = _load_data()
    users = data.get("users", {})

    removed_for_user: int | None = None
    for user_id, bucket in users.items():
        vouches = bucket.get("vouches", [])
        for idx, entry in enumerate(vouches):
            if int(entry.get("id", -1)) == vouch_id:
                del vouches[idx]
                removed_for_user = int(user_id)
                break
        if removed_for_user is not None:
            break

    if removed_for_user is None:
        await ctx.send(f"No vouch found with ID {vouch_id}.")
        return

    _save_data(data)
    await ctx.send(f"Removed vouch ID {vouch_id} for {_mention_for_user(ctx.guild, removed_for_user)}.")


@bot.command(name="sreportremove")
async def sreportremove(ctx: commands.Context, scam_id: int):
    data = _load_data()
    users = data.get("users", {})

    removed_for_user: int | None = None
    for user_id, bucket in users.items():
        scams = bucket.get("scams", [])
        for idx, entry in enumerate(scams):
            if int(entry.get("id", -1)) == scam_id:
                del scams[idx]
                removed_for_user = int(user_id)
                break
        if removed_for_user is not None:
            break

    if removed_for_user is None:
        await ctx.send(f"No scam report found with ID {scam_id}.")
        return

    _save_data(data)
    await ctx.send(f"Removed scam report ID {scam_id} for {_mention_for_user(ctx.guild, removed_for_user)}.")


if __name__ == "__main__":
    bot.run(TOKEN)
