import os
import json
import re
import asyncio
import colorsys
import math
import random
import shutil
import uuid
import aiohttp
from datetime import datetime, timezone
from threading import Lock
import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv

try:
    import redis as redis_lib
except ImportError:
    redis_lib = None

try:
    from discord import app_commands
except ImportError:
    app_commands = None

# Load only the dedicated env file for this bot.
BASE_DIR = os.path.dirname(__file__)
ENV_PATH = os.path.join(BASE_DIR, ".env.fas_farmers")
load_dotenv(dotenv_path=ENV_PATH)

BOT_MODE = (os.getenv("FAS_BOT_MODE") or "farmers").strip().lower()
if BOT_MODE not in {"farmers", "seed"}:
    BOT_MODE = "farmers"

if BOT_MODE == "seed":
    TOKEN = (os.getenv("FAS_SEED_BOT_TOKEN") or "").strip()
    if not TOKEN:
        print("Missing FAS_SEED_BOT_TOKEN for seed bot mode.")
        raise SystemExit(1)
else:
    TOKEN = (os.getenv("FAS_FARMERS_BOT_TOKEN") or "").strip()
    if not TOKEN:
        print("Missing FAS_FARMERS_BOT_TOKEN in .env.fas_farmers.")
        raise SystemExit(1)

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.voice_states = True

bot = commands.Bot(command_prefix="-", intents=intents, help_command=None)

DATA_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "data"))
VOUCH_DATA_FILE = os.path.join(DATA_DIR, "fas_farmers_reports.json")
VOUCH_DATA_BACKUP_FILE = os.path.join(DATA_DIR, "fas_farmers_reports.backup.json")
SEED_SHOP_LIVE_FILE = os.path.join(DATA_DIR, "fas_seed_shop_live.json")
SEED_DATA_DIR = os.path.abspath(os.getenv("SEED_DATA_DIR") or os.getenv("RENDER_DISK_PATH") or DATA_DIR)
REDIS_URL = (os.getenv("REDIS_URL") or "").strip()
REDIS_VOUCH_DATA_KEY = "fas:vouch_reports"
REDIS_SEED_BANK_KEY = "fas:seed_bank"
REDIS_SEED_STORE_KEY = "fas:seed_store"
REDIS_PREDICTOR_V2_KEY = "fas:predictor_v2"
PREDICTOR_V2_FILE = os.path.join(SEED_DATA_DIR, "fas_predictor_v2.json")
SEED_BANK_FILE = os.path.join(SEED_DATA_DIR, "fas_seed_bank.json")
SEED_STORE_FILE = os.path.join(SEED_DATA_DIR, "fas_seed_store.json")
LEGACY_SEED_BANK_FILE = os.path.join(DATA_DIR, "fas_seed_bank.json")
LEGACY_SEED_STORE_FILE = os.path.join(DATA_DIR, "fas_seed_store.json")
DATA_LOCK = Lock()
SEED_REDIS_CLIENT = None
SEED_REDIS_DISABLED = False
BOT_INSTANCE_ID = uuid.uuid4().hex[:8]

VOUCH_CHANNEL_ID = 1524283822512799824
SCAM_REPORT_CHANNEL_ID = 1525702427263631411
SEED_SHOP_CHANNEL_ID = 1525702441608282113
TARGET_GUILD_ID = 1521774456274686044
SEED_SHOP_MANAGER_ROLE_ID = 1526225610022719589
SEED_PURCHASE_CHANNEL_ID = 1526224472858693696
SEED_TOP_1_ROLE_ID = 1525980861097574581
SEED_TOP_2_ROLE_ID = 1525980968958296154
SEED_TOP_3_ROLE_ID = 1525981030975275119
SEED_CLAIM_WIPE_ADMINS = {1273130266629640243, 1332458947067773072, 866957916933455912}
SEED_BALANCE_ADMIN_ROLE_ID = 1526236532980318462
GIVEAWAY_PING_ROLE_ID = 1526304210910449765
SEED_CLAIMWIPE_PING_ROLE_ID = 1526309075372085459
PREDICTOR_V2_CHANNEL_ID = 1526381177127043263
WATCHED_VOICE_CHANNEL_ID = 1521774457537167383
KICK_ALERT_CHANNEL_ID = 1521777234258432100
VOICE_KICK_AUDIT_LOOKBACK_SECONDS = 90
VOICE_KICK_AUDIT_RETRIES = 4
VOICE_KICK_AUDIT_RETRY_DELAY_SECONDS = 1.0
VOICE_KICK_ALERT_ON_UNRESOLVED_ACTOR = True
VOICE_KICK_WATCH_USER_IDS = {
    836330845538877461,
    252128902418268161,
    235088799074484224,
    814675864859836417,
    836330954972725289,
    814675803065155585,
    836330724990517248,
    836330384530735196,
    836330611337330768,
}

NO_VOUCH_ROLE_ID = 1526215394283487302
VOUCH_ANY_ROLE_ID = 1526214841264767139
VOUCH_ROLE_1_ID = 1526215545299533875
VOUCH_ROLE_5_ID = 1526214920574734426
VOUCH_ROLE_15_ID = 1526214766706561074
SCAM_ROLE_1_ID = 1526214986819698818
SCAM_ROLE_3_ID = 1526215243334942803

STOCK_API_URL = "https://api.gag2.gg/api/live/stock"
SELL_PRICE_API_URL = "https://api.gag2.gg/api/live/sell"
PREDICTIONS_API_URL = "https://api.gag2.gg/api/live/predictions/items"
POLL_SECONDS = 10
SHOP_REFRESH_SECONDS = 300
SEED_CLAIM_MIN = 100
SEED_CLAIM_MAX = 1000
BOOSTER_SEED_CLAIM_MIN = 100
BOOSTER_SEED_CLAIM_MAX = 2000
SEED_CLAIM_COOLDOWN_SECONDS = 86400
BOOSTER_CLAIM_MULTIPLIER = 2.5
BOOSTER_CLAIM_MULTIPLIER_CHANCE = 0.10
TOP1_CLAIM_MULTIPLIER = 1.75
TOP2_CLAIM_MULTIPLIER = 1.5
TOP3_CLAIM_MULTIPLIER = 1.25
SEED_SHOP_PAGE_SIZE = 8
SEED_LEADERBOARD_PAGE_SIZE = 10
MESSAGE_SEED_REWARD = 2
MESSAGE_MIN_WORDS = 2
MESSAGE_BONUS_TRIGGER_MESSAGES = 20
MESSAGE_BONUS_MESSAGES = 5
MESSAGE_BONUS_MULTIPLIER = 2
MESSAGE_SEED_ROLE_SYNC_INTERVAL = 30
SPAM_WINDOW_SECONDS = 8
SPAM_MESSAGE_THRESHOLD = 6
SPAM_TRACKER_LIMIT = 12
PREDICTOR_V2_MIN_SIGHTINGS = 4
PREDICTOR_V2_HISTORY_LIMIT = 12
PREDICTOR_V2_EMBED_COLOR = 0xF6B26B
PREDICTOR_V2_FOOTER = "Sported by Predictor V2 which could be very wrong. Do not trust this tell fully complete."

last_message_seed_role_sync = 0

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
    "sun bloom": "<@&1525983250877648997>",
    "star fruit": "<@&1525983397296476300>",
    "star fruits": "<@&1525983397296476300>",
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
    {"key": "carrot", "name": "Carrot", "emoji": "<:Carrot:1526209710531936326>", "rarity": "common"},
    {"key": "strawberry", "name": "Strawberry", "emoji": "<:Strawberry:1526209828282699776>", "rarity": "common"},
    {"key": "blueberry", "name": "Blueberry", "emoji": "<:Blueberry:1526209794329939998>", "rarity": "common"},
    {"key": "tulip", "name": "Tulip", "emoji": "<:Tulip:1526210020553920594>", "rarity": "uncommon"},
    {"key": "tomato", "name": "Tomato", "emoji": "<:Tomato:1526209984160071710>", "rarity": "uncommon"},
    {"key": "apple", "name": "Apple", "emoji": "<:Apple:1526209953491058798>", "rarity": "uncommon"},
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
    {"key": "sun bloom", "name": "Sun Bloom", "emoji": "<:Sun_bloom:1525983493451026452>", "rarity": "super"},
    {"key": "star fruit", "name": "Star Fruit", "emoji": "<:Star_Fruit:1525983435770957975>", "rarity": "super"},
    {"key": "hypno bloom", "name": "Hypno Bloom", "emoji": "<:Hypnobloomseed:1524538199446126622>", "rarity": "super"},
    {"key": "dragons breath", "name": "Dragons Breath", "emoji": "<:Dragons_Breath_seed:1524539236462624932>", "rarity": "super"},
]

SEED_LOOKUP = {entry["key"]: entry for entry in SEED_CONFIG}
PREDICTOR_V2_CUSTOM_ALIASES = {
    "star fruit": {"sf"},
    "sun bloom": {"sb"},
    "moon bloom": {"mb"},
    "hypno bloom": {"hb"},
    "dragons breath": {"db", "dragon's breath", "dragonsbreath", "dragonbreath"},
    "venus fly trap": {"vft", "venusflytrap"},
    "venom spitter": {"vs", "venom spiter", "venomspiter"},
    "poison apple": {"pa"},
    "fire fern": {"ff"},
    "dragon fruit": {"df"},
}

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
    {"name": "Sun Bloom"},
    {"name": "Star Fruit"},
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

SEED_PREDICT_CHANCES = {
    "carrot": "~95%",
    "strawberry": "~90%",
    "blueberry": "~85%",
    "tulip": "~70%",
    "tomato": "~65%",
    "apple": "~55%",
    "bamboo": "~30%",
    "corn": "~25%",
    "cactus": "~20%",
    "mushroom": "~8%",
    "dragon fruit": "~3%",
    "ghost pepper": "~1%",
    "venus fly trap": "~1%",
    "pomegranate": "~1%",
    "poison apple": "~1%",
    "dragons breath": "~0.3%",
    "moon bloom": "~0.3%",
}

http_session: aiohttp.ClientSession | None = None
last_live_post_ts: int | None = None
last_stock_signature: str | None = None

GIVEAWAYS: dict[int, dict] = {}
TREE_SYNCED = False
MODE_COMMANDS_CONFIGURED = False

XP_COMMAND_NAMES = {
    "seedclaim",
    "seedbalance",
    "seedleaderboard",
    "seedlb",
    "seeddebug",
    "seedclaimwipe",
    "addseeds",
    "removeseeds",
    "remove_seeds",
}

SEED_SHOP_COMMAND_NAMES = {
    "addtoshop",
    "addtosshop",
    "seedshop",
    "supershop",
    "register",
    "buy",
}

STOCK_COMMAND_NAMES = {
    "seedstock",
    "seedshoplive",
    "seedshopstop",
    "sellprice",
}

PREDICTOR_COMMAND_NAMES = {
    "predict",
}

NON_SEED_COMMAND_NAMES = {
    "ping",
    "greroll",
    "genterlist",
    "forceend",
    "vouch",
    "addvouch",
    "sreport",
    "vouchlist",
    "vouchremove",
    "sreportremove",
}


def _configure_commands_for_mode() -> None:
    global MODE_COMMANDS_CONFIGURED
    if MODE_COMMANDS_CONFIGURED:
        return

    if BOT_MODE == "farmers":
        # First bot: keep non-seed + predictor; remove XP, stock, and seed-shop commands.
        to_remove = XP_COMMAND_NAMES | STOCK_COMMAND_NAMES | SEED_SHOP_COMMAND_NAMES
    else:
        # Second bot: XP + seed-shop command surface.
        to_remove = NON_SEED_COMMAND_NAMES | STOCK_COMMAND_NAMES | PREDICTOR_COMMAND_NAMES
    for name in to_remove:
        try:
            bot.remove_command(name)
        except Exception:
            pass

    MODE_COMMANDS_CONFIGURED = True

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
    if not os.path.exists(VOUCH_DATA_BACKUP_FILE):
        with open(VOUCH_DATA_BACKUP_FILE, "w", encoding="utf-8") as f:
            json.dump({"next_vouch_id": 1, "next_scam_id": 1, "users": {}}, f, indent=2)


def _ensure_live_file() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(SEED_SHOP_LIVE_FILE):
        with open(SEED_SHOP_LIVE_FILE, "w", encoding="utf-8") as f:
            json.dump({"channel_id": None, "message_id": None}, f, indent=2)


def _ensure_seed_bank_file() -> None:
    os.makedirs(SEED_DATA_DIR, exist_ok=True)
    if not os.path.exists(SEED_BANK_FILE) and os.path.exists(LEGACY_SEED_BANK_FILE):
        try:
            shutil.copy2(LEGACY_SEED_BANK_FILE, SEED_BANK_FILE)
        except Exception:
            pass
    if not os.path.exists(SEED_BANK_FILE):
        with open(SEED_BANK_FILE, "w", encoding="utf-8") as f:
            json.dump({"balances": {}}, f, indent=2)


def _ensure_seed_store_file() -> None:
    os.makedirs(SEED_DATA_DIR, exist_ok=True)
    if not os.path.exists(SEED_STORE_FILE) and os.path.exists(LEGACY_SEED_STORE_FILE):
        try:
            shutil.copy2(LEGACY_SEED_STORE_FILE, SEED_STORE_FILE)
        except Exception:
            pass
    if not os.path.exists(SEED_STORE_FILE):
        with open(SEED_STORE_FILE, "w", encoding="utf-8") as f:
            json.dump({"next_item_id": 1, "items": []}, f, indent=2)


def _ensure_predictor_v2_file() -> None:
    os.makedirs(SEED_DATA_DIR, exist_ok=True)
    if not os.path.exists(PREDICTOR_V2_FILE):
        with open(PREDICTOR_V2_FILE, "w", encoding="utf-8") as f:
            json.dump({"seeds": {}}, f, indent=2)


def _get_seed_redis_client():
    global SEED_REDIS_CLIENT, SEED_REDIS_DISABLED
    if SEED_REDIS_DISABLED:
        return None
    if SEED_REDIS_CLIENT is not None:
        return SEED_REDIS_CLIENT
    if not REDIS_URL or redis_lib is None:
        return None

    try:
        client = redis_lib.Redis.from_url(
            REDIS_URL,
            decode_responses=True,
            socket_timeout=5,
            socket_connect_timeout=5,
            health_check_interval=30,
        )
        client.ping()
        SEED_REDIS_CLIENT = client
        print("Seed data persistence: using Redis")
        return SEED_REDIS_CLIENT
    except Exception as exc:
        SEED_REDIS_DISABLED = True
        print(f"Seed data persistence: Redis unavailable ({exc}), falling back to file storage")
        return None


def _load_data() -> dict:
    client = _get_seed_redis_client()
    redis_data = None
    file_data = None

    if client is not None:
        with DATA_LOCK:
            try:
                raw = client.get(REDIS_VOUCH_DATA_KEY)
                if raw:
                    redis_data = json.loads(raw)
            except Exception:
                redis_data = None

    _ensure_data_file()
    with DATA_LOCK:
        try:
            with open(VOUCH_DATA_FILE, "r", encoding="utf-8") as f:
                file_data = json.load(f)
        except (json.JSONDecodeError, OSError):
            # Fall back to backup if the primary file is unreadable/corrupt.
            with open(VOUCH_DATA_BACKUP_FILE, "r", encoding="utf-8") as f:
                file_data = json.load(f)

    if client is not None:
        if not isinstance(redis_data, dict):
            data = file_data if isinstance(file_data, dict) else {"next_vouch_id": 1, "next_scam_id": 1, "users": {}}
            try:
                client.set(REDIS_VOUCH_DATA_KEY, json.dumps(data))
            except Exception:
                pass
        else:
            redis_updated = int(redis_data.get("updated_at", 0) or 0)
            file_updated = int(file_data.get("updated_at", 0) or 0) if isinstance(file_data, dict) else 0
            data = redis_data if redis_updated >= file_updated else file_data

            if data is file_data:
                try:
                    client.set(REDIS_VOUCH_DATA_KEY, json.dumps(data))
                except Exception:
                    pass
            elif isinstance(file_data, dict) and data is redis_data and redis_updated > file_updated:
                with DATA_LOCK:
                    try:
                        tmp = VOUCH_DATA_FILE + ".tmp"
                        with open(tmp, "w", encoding="utf-8") as f:
                            json.dump(data, f, indent=2)
                        os.replace(tmp, VOUCH_DATA_FILE)

                        backup_tmp = VOUCH_DATA_BACKUP_FILE + ".tmp"
                        with open(backup_tmp, "w", encoding="utf-8") as f:
                            json.dump(data, f, indent=2)
                        os.replace(backup_tmp, VOUCH_DATA_BACKUP_FILE)
                    except Exception:
                        pass
    else:
        data = file_data if isinstance(file_data, dict) else {"next_vouch_id": 1, "next_scam_id": 1, "users": {}}

    data.setdefault("next_vouch_id", 1)
    data.setdefault("next_scam_id", 1)
    data.setdefault("users", {})
    return data


def _save_data(data: dict) -> None:
    data["updated_at"] = int(datetime.now(timezone.utc).timestamp())
    client = _get_seed_redis_client()
    if client is not None:
        with DATA_LOCK:
            try:
                client.set(REDIS_VOUCH_DATA_KEY, json.dumps(data))
            except Exception:
                global SEED_REDIS_CLIENT, SEED_REDIS_DISABLED
                SEED_REDIS_CLIENT = None
                SEED_REDIS_DISABLED = True
                pass

    _ensure_data_file()
    with DATA_LOCK:
        tmp = VOUCH_DATA_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, VOUCH_DATA_FILE)

        backup_tmp = VOUCH_DATA_BACKUP_FILE + ".tmp"
        with open(backup_tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        os.replace(backup_tmp, VOUCH_DATA_BACKUP_FILE)


def _load_live_config() -> dict:
    _ensure_live_file()
    with DATA_LOCK:
        with open(SEED_SHOP_LIVE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    data.setdefault("channel_id", None)
    data.setdefault("message_id", None)
    return data


def _load_predictor_v2_data() -> dict:
    client = _get_seed_redis_client()
    redis_data = None
    file_data = None

    if client is not None:
        with DATA_LOCK:
            try:
                raw = client.get(REDIS_PREDICTOR_V2_KEY)
                if raw:
                    redis_data = json.loads(raw)
            except Exception:
                redis_data = None

    _ensure_predictor_v2_file()
    with DATA_LOCK:
        try:
            with open(PREDICTOR_V2_FILE, "r", encoding="utf-8") as f:
                file_data = json.load(f)
        except Exception:
            file_data = {"seeds": {}}

    if client is not None:
        if not isinstance(redis_data, dict):
            data = file_data if isinstance(file_data, dict) else {"seeds": {}}
            try:
                client.set(REDIS_PREDICTOR_V2_KEY, json.dumps(data))
            except Exception:
                pass
        else:
            redis_updated = int(redis_data.get("updated_at", 0) or 0)
            file_updated = int(file_data.get("updated_at", 0) or 0) if isinstance(file_data, dict) else 0
            data = redis_data if redis_updated >= file_updated else file_data

            if data is file_data:
                try:
                    client.set(REDIS_PREDICTOR_V2_KEY, json.dumps(data))
                except Exception:
                    pass
            elif isinstance(file_data, dict) and data is redis_data and redis_updated > file_updated:
                with DATA_LOCK:
                    try:
                        tmp = PREDICTOR_V2_FILE + ".tmp"
                        with open(tmp, "w", encoding="utf-8") as f:
                            json.dump(data, f, indent=2)
                        os.replace(tmp, PREDICTOR_V2_FILE)
                    except Exception:
                        pass
    else:
        data = file_data if isinstance(file_data, dict) else {"seeds": {}}

    data.setdefault("seeds", {})
    return data


def _save_predictor_v2_data(data: dict) -> None:
    data["updated_at"] = int(datetime.now(timezone.utc).timestamp())
    client = _get_seed_redis_client()
    if client is not None:
        with DATA_LOCK:
            try:
                client.set(REDIS_PREDICTOR_V2_KEY, json.dumps(data))
            except Exception:
                global SEED_REDIS_CLIENT, SEED_REDIS_DISABLED
                SEED_REDIS_CLIENT = None
                SEED_REDIS_DISABLED = True
                pass

    _ensure_predictor_v2_file()
    with DATA_LOCK:
        tmp = PREDICTOR_V2_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, PREDICTOR_V2_FILE)


def _save_live_config(data: dict) -> None:
    _ensure_live_file()
    with DATA_LOCK:
        tmp = SEED_SHOP_LIVE_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, SEED_SHOP_LIVE_FILE)


def _load_seed_bank() -> dict:
    client = _get_seed_redis_client()
    redis_data = None
    file_data = None

    if client is not None:
        with DATA_LOCK:
            try:
                raw = client.get(REDIS_SEED_BANK_KEY)
                if raw:
                    redis_data = json.loads(raw)
            except Exception:
                redis_data = None

        _ensure_seed_bank_file()
        with DATA_LOCK:
            try:
                with open(SEED_BANK_FILE, "r", encoding="utf-8") as f:
                    file_data = json.load(f)
            except Exception:
                file_data = {
                    "balances": {},
                    "claim_cooldowns": {},
                    "message_counts": {},
                    "message_bonus_remaining": {},
                    "roblox_users": {},
                    "spam_tracker": {},
                }

        if not isinstance(redis_data, dict):
            data = file_data if isinstance(file_data, dict) else {
                "balances": {},
                "claim_cooldowns": {},
                "message_counts": {},
                "message_bonus_remaining": {},
                "roblox_users": {},
                "spam_tracker": {},
            }
            try:
                client.set(REDIS_SEED_BANK_KEY, json.dumps(data))
            except Exception:
                pass
        else:
            redis_updated = int(redis_data.get("updated_at", 0) or 0)
            file_updated = int(file_data.get("updated_at", 0) or 0) if isinstance(file_data, dict) else 0
            data = redis_data if redis_updated >= file_updated else file_data

            # Keep both stores in sync with the newest copy.
            if data is file_data:
                try:
                    client.set(REDIS_SEED_BANK_KEY, json.dumps(data))
                except Exception:
                    pass
            elif isinstance(file_data, dict) and data is redis_data and redis_updated > file_updated:
                with DATA_LOCK:
                    try:
                        tmp = SEED_BANK_FILE + ".tmp"
                        with open(tmp, "w", encoding="utf-8") as f:
                            json.dump(data, f, indent=2)
                        os.replace(tmp, SEED_BANK_FILE)
                    except Exception:
                        pass
    else:
        _ensure_seed_bank_file()
        with DATA_LOCK:
            with open(SEED_BANK_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
    data.setdefault("balances", {})
    data.setdefault("claim_cooldowns", {})
    data.setdefault("message_counts", {})
    data.setdefault("message_bonus_remaining", {})
    data.setdefault("roblox_users", {})
    data.setdefault("spam_tracker", {})
    return data


def _save_seed_bank(data: dict) -> None:
    data["updated_at"] = int(datetime.now(timezone.utc).timestamp())
    client = _get_seed_redis_client()
    if client is not None:
        with DATA_LOCK:
            try:
                client.set(REDIS_SEED_BANK_KEY, json.dumps(data))
            except Exception:
                global SEED_REDIS_CLIENT, SEED_REDIS_DISABLED
                SEED_REDIS_CLIENT = None
                SEED_REDIS_DISABLED = True
                pass

    _ensure_seed_bank_file()
    with DATA_LOCK:
        tmp = SEED_BANK_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, SEED_BANK_FILE)


def _get_seed_balance(bank_data: dict, user_id: int) -> int:
    balances = bank_data.setdefault("balances", {})
    key = str(user_id)
    return int(balances.get(key, 0) or 0)


def _set_seed_balance(bank_data: dict, user_id: int, amount: int) -> None:
    balances = bank_data.setdefault("balances", {})
    balances[str(user_id)] = max(0, int(amount))


def _get_registered_roblox_user(bank_data: dict, user_id: int) -> str | None:
    users = bank_data.setdefault("roblox_users", {})
    value = str(users.get(str(user_id), "") or "").strip()
    return value if value else None


def _set_registered_roblox_user(bank_data: dict, user_id: int, roblox_user: str) -> None:
    users = bank_data.setdefault("roblox_users", {})
    users[str(user_id)] = roblox_user.strip()


def _get_claim_cooldown_unix(bank_data: dict, user_id: int) -> int:
    cooldowns = bank_data.setdefault("claim_cooldowns", {})
    return int(cooldowns.get(str(user_id), 0) or 0)


def _set_claim_cooldown_unix(bank_data: dict, user_id: int, unix_ts: int) -> None:
    cooldowns = bank_data.setdefault("claim_cooldowns", {})
    cooldowns[str(user_id)] = int(unix_ts)


def _clear_claim_cooldown(bank_data: dict, user_id: int) -> None:
    cooldowns = bank_data.setdefault("claim_cooldowns", {})
    cooldowns.pop(str(user_id), None)


def _is_server_booster(member: discord.Member | None) -> bool:
    return bool(member and member.premium_since is not None)


def _has_seed_shop_seller_role(member: discord.Member | None) -> bool:
    if member is None:
        return False
    return any(role.id == SEED_SHOP_MANAGER_ROLE_ID for role in member.roles)


def _has_seed_balance_admin_role(member: discord.Member | None) -> bool:
    if member is None:
        return False
    return any(role.id == SEED_BALANCE_ADMIN_ROLE_ID for role in member.roles)


def _highest_seed_balances(bank_data: dict, top_n: int = 3) -> list[int]:
    balances = bank_data.get("balances", {})
    pairs: list[tuple[int, int]] = []
    if isinstance(balances, dict):
        for key, value in balances.items():
            try:
                pairs.append((int(key), int(value or 0)))
            except Exception:
                continue
    pairs.sort(key=lambda item: item[1], reverse=True)
    return [user_id for user_id, _amount in pairs[:top_n]]


def _seed_leaderboard_rows(bank_data: dict) -> list[tuple[int, int]]:
    balances = bank_data.get("balances", {})
    rows: list[tuple[int, int]] = []
    if isinstance(balances, dict):
        for key, value in balances.items():
            try:
                user_id = int(key)
                amount = max(0, int(value or 0))
            except Exception:
                continue
            rows.append((user_id, amount))
    rows.sort(key=lambda item: (-item[1], item[0]))
    return rows


def _seed_leaderboard_pages(rows: list[tuple[int, int]], page_size: int = SEED_LEADERBOARD_PAGE_SIZE) -> list[list[tuple[int, int]]]:
    if not rows:
        return [[]]
    pages: list[list[tuple[int, int]]] = []
    for idx in range(0, len(rows), page_size):
        pages.append(rows[idx: idx + page_size])
    return pages


def _build_seed_leaderboard_embed(
    guild: discord.Guild | None,
    page_rows: list[tuple[int, int]],
    page_index: int,
    total_pages: int,
    total_rows: int,
) -> discord.Embed:
    start_rank = page_index * SEED_LEADERBOARD_PAGE_SIZE
    lines: list[str] = []

    for offset, (user_id, amount) in enumerate(page_rows):
        rank = start_rank + offset + 1
        rank_prefix = ""
        if rank == 1:
            rank_prefix = "🥇 "
        elif rank == 2:
            rank_prefix = "🥈 "
        elif rank == 3:
            rank_prefix = "🥉 "

        lines.append(f"{rank_prefix}`#{rank}` <@{user_id}> - `{amount}` seeds")

    if not lines:
        lines = ["No seed balances are recorded yet."]

    title = "[FAS] Seed Leaderboard"
    if guild is not None:
        title = f"{guild.name} Seed Leaderboard"

    embed = discord.Embed(
        title=title,
        description="\n".join(lines),
        color=discord.Color.gold(),
    )
    embed.set_footer(text=f"Page {page_index + 1}/{total_pages} | {total_rows} players")
    return embed


async def _sync_seed_leader_roles(guild: discord.Guild | None, bank_data: dict) -> None:
    if guild is None:
        return

    role_map = {
        SEED_TOP_1_ROLE_ID: 0,
        SEED_TOP_2_ROLE_ID: 1,
        SEED_TOP_3_ROLE_ID: 2,
    }
    top_users = _highest_seed_balances(bank_data, top_n=3)
    desired_user_by_role = {
        role_id: (top_users[idx] if idx < len(top_users) else None)
        for role_id, idx in role_map.items()
    }

    for role_id, idx in role_map.items():
        role = guild.get_role(role_id)
        if role is None:
            continue
        desired_user = desired_user_by_role[role_id]

        for member in list(role.members):
            if desired_user is None or member.id != desired_user:
                try:
                    await member.remove_roles(role, reason="Seed leaderboard updated")
                except Exception:
                    pass

        if desired_user is not None:
            member = guild.get_member(desired_user)
            if member is None:
                try:
                    member = await guild.fetch_member(desired_user)
                except Exception:
                    member = None
            if member is not None and role not in member.roles:
                try:
                    await member.add_roles(role, reason="Seed leaderboard updated")
                except Exception:
                    pass


def _find_seed_shop_item_by_id(items: list[dict], item_id: int) -> dict | None:
    for item in items:
        if not isinstance(item, dict):
            continue
        if not bool(item.get("active", True)):
            continue
        if int(item.get("id", 0) or 0) == int(item_id):
            return item
    return None


def _parse_buy_item_id(raw: str) -> int | None:
    token = raw.strip()
    if not token or not token.isdigit():
        return None
    return int(token)


def _parse_item_price_arguments(raw: str) -> tuple[str, int] | None:
    tokens = raw.strip().split()
    if len(tokens) < 2:
        return None
    price_token = tokens[-1]
    if not price_token.isdigit():
        return None
    item_name = " ".join(tokens[:-1]).strip()
    if not item_name:
        return None
    return item_name, int(price_token)


def _load_seed_store() -> dict:
    client = _get_seed_redis_client()
    redis_data = None
    file_data = None

    if client is not None:
        with DATA_LOCK:
            try:
                raw = client.get(REDIS_SEED_STORE_KEY)
                if raw:
                    redis_data = json.loads(raw)
            except Exception:
                redis_data = None

        _ensure_seed_store_file()
        with DATA_LOCK:
            try:
                with open(SEED_STORE_FILE, "r", encoding="utf-8") as f:
                    file_data = json.load(f)
            except Exception:
                file_data = {"next_item_id": 1, "items": []}

        if not isinstance(redis_data, dict):
            data = file_data if isinstance(file_data, dict) else {"next_item_id": 1, "items": []}
            try:
                client.set(REDIS_SEED_STORE_KEY, json.dumps(data))
            except Exception:
                pass
        else:
            redis_updated = int(redis_data.get("updated_at", 0) or 0)
            file_updated = int(file_data.get("updated_at", 0) or 0) if isinstance(file_data, dict) else 0
            data = redis_data if redis_updated >= file_updated else file_data

            if data is file_data:
                try:
                    client.set(REDIS_SEED_STORE_KEY, json.dumps(data))
                except Exception:
                    pass
            elif isinstance(file_data, dict) and data is redis_data and redis_updated > file_updated:
                with DATA_LOCK:
                    try:
                        tmp = SEED_STORE_FILE + ".tmp"
                        with open(tmp, "w", encoding="utf-8") as f:
                            json.dump(data, f, indent=2)
                        os.replace(tmp, SEED_STORE_FILE)
                    except Exception:
                        pass
    else:
        _ensure_seed_store_file()
        with DATA_LOCK:
            with open(SEED_STORE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
    data.setdefault("next_item_id", 1)
    data.setdefault("items", [])
    return data


def _save_seed_store(data: dict) -> None:
    data["updated_at"] = int(datetime.now(timezone.utc).timestamp())
    client = _get_seed_redis_client()
    if client is not None:
        with DATA_LOCK:
            try:
                client.set(REDIS_SEED_STORE_KEY, json.dumps(data))
            except Exception:
                global SEED_REDIS_CLIENT, SEED_REDIS_DISABLED
                SEED_REDIS_CLIENT = None
                SEED_REDIS_DISABLED = True
                pass

    _ensure_seed_store_file()
    with DATA_LOCK:
        tmp = SEED_STORE_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, SEED_STORE_FILE)


def _active_seed_shop_items(store_data: dict) -> list[dict]:
    items = store_data.get("items", [])
    if not isinstance(items, list):
        return []
    return [item for item in items if isinstance(item, dict) and bool(item.get("active", True))]


def _seed_shop_item_pages(items: list[dict], page_size: int = SEED_SHOP_PAGE_SIZE) -> list[list[dict]]:
    if not items:
        return [[]]
    pages: list[list[dict]] = []
    for idx in range(0, len(items), page_size):
        pages.append(items[idx: idx + page_size])
    return pages


def _build_seed_shop_page_embed(page_items: list[dict], page_index: int, total_pages: int, total_items: int) -> discord.Embed:
    lines: list[str] = []
    for item in page_items:
        item_id = int(item.get("id", 0) or 0)
        item_name = str(item.get("name", "Unknown Item"))
        price = int(item.get("price", 0) or 0)
        host_id = int(item.get("host_id", 0) or 0)
        lines.append(f"ID `{item_id}` | {item_name} For {price} Seeds - <@{host_id}>")
        lines.append("-# Buy format: -buy <item_id>")

    if not lines:
        lines = ["No items are in stock right now."]

    embed = discord.Embed(
        description="## [FAS] Farmers Seed Shop has in-stock\n" + "\n".join(lines),
        color=discord.Color.green(),
    )
    embed.set_footer(text=f"Page {page_index + 1}/{total_pages}")
    return embed


class SeedShopPagesView(discord.ui.View):
    def __init__(self, pages: list[list[dict]], total_items: int):
        super().__init__(timeout=180)
        self.pages = pages
        self.total_items = total_items
        self.page_index = 0
        self._sync_buttons()

    def _sync_buttons(self) -> None:
        prev_button = None
        next_button = None
        for child in self.children:
            if isinstance(child, discord.ui.Button) and child.custom_id == "seedshop_prev":
                prev_button = child
            if isinstance(child, discord.ui.Button) and child.custom_id == "seedshop_next":
                next_button = child
        if prev_button is not None:
            prev_button.disabled = self.page_index <= 0
        if next_button is not None:
            next_button.disabled = self.page_index >= len(self.pages) - 1

    @discord.ui.button(label="Previous", style=discord.ButtonStyle.secondary, custom_id="seedshop_prev")
    async def previous_page(self, *args):
        interaction = next((arg for arg in args if isinstance(arg, discord.Interaction)), None)
        if not isinstance(interaction, discord.Interaction):
            return
        if self.page_index <= 0:
            await interaction.response.defer()
            return
        self.page_index -= 1
        self._sync_buttons()
        embed = _build_seed_shop_page_embed(self.pages[self.page_index], self.page_index, len(self.pages), self.total_items)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Next", style=discord.ButtonStyle.secondary, custom_id="seedshop_next")
    async def next_page(self, *args):
        interaction = next((arg for arg in args if isinstance(arg, discord.Interaction)), None)
        if not isinstance(interaction, discord.Interaction):
            return
        if self.page_index >= len(self.pages) - 1:
            await interaction.response.defer()
            return
        self.page_index += 1
        self._sync_buttons()
        embed = _build_seed_shop_page_embed(self.pages[self.page_index], self.page_index, len(self.pages), self.total_items)
        await interaction.response.edit_message(embed=embed, view=self)


class SeedLeaderboardPagesView(discord.ui.View):
    def __init__(self, guild: discord.Guild | None, pages: list[list[tuple[int, int]]], total_rows: int):
        super().__init__(timeout=180)
        self.guild = guild
        self.pages = pages
        self.total_rows = total_rows
        self.page_index = 0
        self._sync_buttons()

    def _sync_buttons(self) -> None:
        prev_button = None
        next_button = None
        for child in self.children:
            if isinstance(child, discord.ui.Button) and child.custom_id == "seedlb_prev":
                prev_button = child
            if isinstance(child, discord.ui.Button) and child.custom_id == "seedlb_next":
                next_button = child
        if prev_button is not None:
            prev_button.disabled = self.page_index <= 0
        if next_button is not None:
            next_button.disabled = self.page_index >= len(self.pages) - 1

    @discord.ui.button(label="Previous", style=discord.ButtonStyle.secondary, custom_id="seedlb_prev")
    async def previous_page(self, *args):
        interaction = next((arg for arg in args if isinstance(arg, discord.Interaction)), None)
        if not isinstance(interaction, discord.Interaction):
            return
        if self.page_index <= 0:
            await interaction.response.defer()
            return
        self.page_index -= 1
        self._sync_buttons()
        embed = _build_seed_leaderboard_embed(
            self.guild,
            self.pages[self.page_index],
            self.page_index,
            len(self.pages),
            self.total_rows,
        )
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Next", style=discord.ButtonStyle.secondary, custom_id="seedlb_next")
    async def next_page(self, *args):
        interaction = next((arg for arg in args if isinstance(arg, discord.Interaction)), None)
        if not isinstance(interaction, discord.Interaction):
            return
        if self.page_index >= len(self.pages) - 1:
            await interaction.response.defer()
            return
        self.page_index += 1
        self._sync_buttons()
        embed = _build_seed_leaderboard_embed(
            self.guild,
            self.pages[self.page_index],
            self.page_index,
            len(self.pages),
            self.total_rows,
        )
        await interaction.response.edit_message(embed=embed, view=self)


class CompleteSellView(discord.ui.View):
    def __init__(self, host_id: int, buyer_id: int, price: int):
        super().__init__(timeout=None)
        self.host_id = host_id
        self.buyer_id = int(buyer_id)
        self.price = max(0, int(price))
        self.completed = False

    def _disable_action_buttons(self) -> None:
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True

    @discord.ui.button(label="Complete Sell", style=discord.ButtonStyle.success, custom_id="fas_complete_sell")
    async def complete_sell(self, first, second):
        if isinstance(first, discord.ui.Button):
            button = first
            interaction = second
        else:
            interaction = first
            button = second
        if not isinstance(interaction, discord.Interaction) or not isinstance(button, discord.ui.Button):
            return
        if interaction.user.id != self.host_id:
            await interaction.response.send_message("Only the host can complete this sale.", ephemeral=True)
            return

        if self.completed:
            await interaction.response.send_message("This sale is already completed.", ephemeral=True)
            return

        message = interaction.message
        if message is None or not message.embeds:
            await interaction.response.send_message("Could not update this sale message.", ephemeral=True)
            return

        embed = message.embeds[0].copy()
        if embed.description:
            embed.description = embed.description.replace("In-complete", "Complete")
        embed.color = discord.Color.red()

        self.completed = True
        self._disable_action_buttons()
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Deny Sale", style=discord.ButtonStyle.danger, custom_id="fas_deny_sell")
    async def deny_sell(self, first, second):
        if isinstance(first, discord.ui.Button):
            button = first
            interaction = second
        else:
            interaction = first
            button = second
        if not isinstance(interaction, discord.Interaction) or not isinstance(button, discord.ui.Button):
            return
        if interaction.user.id != self.host_id:
            await interaction.response.send_message("Only the host can deny this sale.", ephemeral=True)
            return

        if self.completed:
            await interaction.response.send_message("This sale is already finalized.", ephemeral=True)
            return

        bank_data = _load_seed_bank()
        buyer_balance = _get_seed_balance(bank_data, self.buyer_id)
        host_balance = _get_seed_balance(bank_data, self.host_id)
        _set_seed_balance(bank_data, self.buyer_id, buyer_balance + self.price)
        _set_seed_balance(bank_data, self.host_id, max(0, host_balance - self.price))
        _save_seed_bank(bank_data)
        await _sync_seed_leader_roles(interaction.guild, bank_data)

        message = interaction.message
        if message is None or not message.embeds:
            await interaction.response.send_message("Sale denied and seeds refunded.", ephemeral=True)
            self.completed = True
            self._disable_action_buttons()
            return

        embed = message.embeds[0].copy()
        if embed.description:
            embed.description = embed.description.replace("In-complete", "Denied")
            embed.description += f"\n\nRefunded `{self.price}` seeds back to <@{self.buyer_id}>."
        embed.color = discord.Color.orange()

        self.completed = True
        self._disable_action_buttons()
        await interaction.response.edit_message(embed=embed, view=self)


def _get_user_bucket(data: dict, user_id: int) -> dict:
    users = data.setdefault("users", {})
    key = str(user_id)
    if key not in users:
        users[key] = {"vouches": [], "scams": []}
    bucket = users[key]
    bucket.setdefault("vouches", [])
    bucket.setdefault("scams", [])
    bucket.setdefault("trust_level", "positive")
    bucket.setdefault("trust_role_id", NO_VOUCH_ROLE_ID)
    _update_bucket_trust_level(bucket)
    return bucket


def _update_bucket_trust_level(bucket: dict) -> None:
    vouch_count = len(bucket.get("vouches", []))
    scam_count = len(bucket.get("scams", []))
    negative_role_id = _highest_negative_trust_role_id(scam_count)
    if negative_role_id is not None:
        bucket["trust_level"] = "negative"
        bucket["trust_role_id"] = int(negative_role_id)
    else:
        bucket["trust_level"] = "positive"
        bucket["trust_role_id"] = int(_highest_positive_trust_role_id(vouch_count))
    bucket["vouch_count"] = int(vouch_count)
    bucket["scam_count"] = int(scam_count)


def _mention_for_user(guild: discord.Guild | None, user_id: int) -> str:
    if guild:
        member = guild.get_member(user_id)
        if member:
            return member.mention
    return f"<@{user_id}>"


def _desired_vouch_role_ids(vouch_count: int) -> set[int]:
    if vouch_count >= 15:
        return {VOUCH_ANY_ROLE_ID, VOUCH_ROLE_15_ID}
    if vouch_count >= 5:
        return {VOUCH_ANY_ROLE_ID, VOUCH_ROLE_5_ID}
    if vouch_count >= 1:
        return {VOUCH_ANY_ROLE_ID, VOUCH_ROLE_1_ID}
    return {NO_VOUCH_ROLE_ID}


def _desired_scam_role_ids(scam_count: int) -> set[int]:
    if scam_count >= 3:
        return {SCAM_ROLE_3_ID}
    if scam_count >= 1:
        return {SCAM_ROLE_1_ID}
    return set()


async def _sync_vouch_scam_roles(guild: discord.Guild | None, user_id: int, bucket: dict) -> None:
    if guild is None:
        return

    member = guild.get_member(user_id)
    if member is None:
        try:
            member = await guild.fetch_member(user_id)
        except Exception:
            return

    tracked_role_ids = {
        NO_VOUCH_ROLE_ID,
        VOUCH_ANY_ROLE_ID,
        VOUCH_ROLE_1_ID,
        VOUCH_ROLE_5_ID,
        VOUCH_ROLE_15_ID,
        SCAM_ROLE_1_ID,
        SCAM_ROLE_3_ID,
    }
    desired_role_ids = _desired_vouch_role_ids(len(bucket.get("vouches", []))) | _desired_scam_role_ids(len(bucket.get("scams", [])))

    current_tracked_roles = [role for role in member.roles if role.id in tracked_role_ids]
    roles_to_remove = [role for role in current_tracked_roles if role.id not in desired_role_ids]
    roles_to_add = [role for role_id in desired_role_ids for role in [guild.get_role(role_id)] if role is not None and role not in member.roles]

    if roles_to_remove:
        try:
            await member.remove_roles(*roles_to_remove, reason="Updated vouch/scam tier roles")
        except Exception:
            pass

    if roles_to_add:
        try:
            await member.add_roles(*roles_to_add, reason="Updated vouch/scam tier roles")
        except Exception:
            pass


def _highest_positive_trust_role_id(vouch_count: int) -> int:
    if vouch_count >= 15:
        return VOUCH_ROLE_15_ID
    if vouch_count >= 5:
        return VOUCH_ROLE_5_ID
    if vouch_count >= 1:
        return VOUCH_ROLE_1_ID
    return NO_VOUCH_ROLE_ID


def _highest_negative_trust_role_id(scam_count: int) -> int | None:
    if scam_count >= 3:
        return SCAM_ROLE_3_ID
    if scam_count >= 1:
        return SCAM_ROLE_1_ID
    return None


def _in_allowed_channel(ctx: commands.Context, channel_id: int) -> bool:
    return bool(ctx.guild and ctx.channel and ctx.channel.id == channel_id)


def _normalize_seed_name(name: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", " ", name.lower()).strip()
    cleaned = cleaned.replace("dragon s", "dragons")
    if cleaned == "venus flytrap":
        cleaned = "venus fly trap"
    return cleaned


def _predictor_catalog_entries() -> list[dict]:
    return [*SEED_CONFIG, *GEAR_CONFIG]


def _predictor_aliases_for_seed(entry: dict) -> set[str]:
    key = str(entry.get("key", ""))
    name = str(entry.get("name", key))
    aliases = {
        key,
        name,
        key.replace("_", " "),
        key.replace("_", ""),
    }

    words = [word for word in re.findall(r"[a-z0-9]+", _normalize_seed_name(name)) if word]
    if words:
        aliases.add("".join(words))
        aliases.add("".join(word[0] for word in words))

    aliases |= PREDICTOR_V2_CUSTOM_ALIASES.get(key, set())
    return {_normalize_sell_query(alias) for alias in aliases if alias}


def _resolve_predictor_seed(query: str) -> list[dict]:
    normalized_query = _normalize_sell_query(query)
    if not normalized_query:
        return []

    exact_matches: list[dict] = []
    startswith_matches: list[dict] = []
    contains_matches: list[dict] = []

    for entry in _predictor_catalog_entries():
        aliases = _predictor_aliases_for_seed(entry)
        if normalized_query in aliases:
            exact_matches.append(entry)
            continue

        if any(alias.startswith(normalized_query) for alias in aliases):
            startswith_matches.append(entry)
            continue

        normalized_name = _normalize_sell_query(str(entry.get("name", "")))
        if normalized_query in normalized_name:
            contains_matches.append(entry)

    if exact_matches:
        return exact_matches
    if startswith_matches:
        return startswith_matches
    return contains_matches


def _record_predictor_v2_sightings(in_stock: dict[str, int], observed_at: int) -> None:
    data = _load_predictor_v2_data()
    seeds = data.setdefault("seeds", {})
    changed = False

    for entry in _predictor_catalog_entries():
        key = entry["key"]
        seed_state = seeds.setdefault(key, {"sightings": [], "currently_in_stock": False})
        currently_in_stock = bool(in_stock.get(key, 0) > 0)
        previous_in_stock = bool(seed_state.get("currently_in_stock", False))
        sightings = seed_state.setdefault("sightings", [])

        if currently_in_stock and not previous_in_stock:
            if not sightings or abs(int(sightings[-1]) - observed_at) > 60:
                sightings.append(int(observed_at))
                if len(sightings) > PREDICTOR_V2_HISTORY_LIMIT:
                    del sightings[:-PREDICTOR_V2_HISTORY_LIMIT]
                changed = True

        if previous_in_stock != currently_in_stock:
            seed_state["currently_in_stock"] = currently_in_stock
            changed = True

    if changed:
        _save_predictor_v2_data(data)


def _predictor_v2_chance(intervals: list[int], predicted_ts: int, now_ts: int, currently_in_stock: bool) -> int:
    if currently_in_stock:
        return 100
    if not intervals:
        return 0

    avg_interval = max(1.0, float(sum(intervals)) / float(len(intervals)))
    variance = sum((value - avg_interval) ** 2 for value in intervals) / float(max(1, len(intervals)))
    std_dev = math.sqrt(max(0.0, variance))
    coeff_var = std_dev / max(1.0, avg_interval)

    # More stable cycles should get a stronger confidence score.
    consistency = max(0.10, 1.0 - min(0.90, coeff_var))
    sample_score = min(1.0, float(len(intervals)) / 8.0)

    timing_sigma = max(300.0, avg_interval * max(0.35, 1.10 - consistency))
    time_gap = abs(now_ts - predicted_ts)
    time_score = math.exp(-0.5 * ((float(time_gap) / timing_sigma) ** 2))

    chance = int(round(((time_score * 0.55) + (consistency * 0.25) + (sample_score * 0.20)) * 100))

    # Far beyond the expected cadence should sharply reduce confidence.
    if time_gap > int(avg_interval * 4):
        chance = min(chance, 15)

    return max(1, min(99, chance))


def _apply_predictor_v2_embed_style(embed: discord.Embed, guild: discord.Guild | None) -> discord.Embed:
    embed.color = discord.Color(PREDICTOR_V2_EMBED_COLOR)
    if guild is not None and guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    embed.set_footer(text=PREDICTOR_V2_FOOTER)
    return embed


async def _build_predictor_v2_response(query: str, guild: discord.Guild | None) -> tuple[discord.Embed | None, str | None]:
    cleaned_query = query.strip()
    if not cleaned_query:
        return None, "Usage: -predict <item_name/item_abbreviation>"

    try:
        await _fetch_stock_lines_and_next_restock()
    except Exception as exc:
        return None, f"Could not fetch prediction data right now: {exc}"

    matches = _resolve_predictor_seed(cleaned_query)
    if not matches:
        return None, f"I could not find a fruit matching `{cleaned_query}`."

    if len(matches) > 1:
        match_names = ", ".join(entry["name"] for entry in matches[:8])
        suffix = "" if len(matches) <= 8 else f" and {len(matches) - 8} more"
        return None, f"That abbreviation is ambiguous. Try one of: {match_names}{suffix}."

    entry = matches[0]
    key = str(entry.get("key", ""))
    name = str(entry.get("name", key.title()))
    data = _load_predictor_v2_data()
    seed_state = (data.get("seeds", {}) or {}).get(key, {})
    sightings = [int(value) for value in (seed_state.get("sightings", []) or []) if str(value).isdigit()]
    currently_in_stock = bool(seed_state.get("currently_in_stock", False))

    if currently_in_stock:
        now_ts = int(datetime.now(timezone.utc).timestamp())
        last_seen = sightings[-1] if sightings else now_ts
        interval_count = max(0, len(sightings) - 1)
        embed = discord.Embed(
            description=(
                f"# 🤩 We Predict {name} Will be in-stock in <t:{now_ts}:R>\n"
                f"> Last seen in-stock: <t:{last_seen}:R>\n"
                f"> Estimated chance right now: `100%` (based on `{interval_count}` tracked cycles)."
            ),
            timestamp=datetime.now(timezone.utc),
        )
        return _apply_predictor_v2_embed_style(embed, guild), None

    if len(sightings) < PREDICTOR_V2_MIN_SIGHTINGS:
        embed = discord.Embed(
            description=(
                f"# ⏰I don't have enough data on {name}\n"
                "> We have not collected enough data to give you the prediction for this item please wait 5-20 minutes so I can get more data!"
            ),
            timestamp=datetime.now(timezone.utc),
        )
        return _apply_predictor_v2_embed_style(embed, guild), None

    recent_sightings = sightings[-PREDICTOR_V2_HISTORY_LIMIT:]
    intervals = [
        max(1, recent_sightings[idx] - recent_sightings[idx - 1])
        for idx in range(1, len(recent_sightings))
    ]
    recent_intervals = intervals[-8:] if len(intervals) > 8 else intervals
    last_seen = recent_sightings[-1]

    sorted_intervals = sorted(recent_intervals)
    mid = len(sorted_intervals) // 2
    if len(sorted_intervals) % 2 == 1:
        median_interval = sorted_intervals[mid]
    else:
        median_interval = int(round((sorted_intervals[mid - 1] + sorted_intervals[mid]) / 2))

    weights = list(range(1, len(recent_intervals) + 1))
    weighted_avg_interval = int(round(sum(value * weight for value, weight in zip(recent_intervals, weights)) / max(1, sum(weights))))
    predicted_interval = max(1, int(round((weighted_avg_interval * 0.7) + (median_interval * 0.3))))

    now_ts = int(datetime.now(timezone.utc).timestamp())
    predicted_ts = last_seen + predicted_interval
    chance = _predictor_v2_chance(recent_intervals, predicted_ts, now_ts, False)

    embed = discord.Embed(
        description=(
            f"# 🤩 We Predict {name} Will be in-stock in <t:{predicted_ts}:R>\n"
            f"> Last seen in-stock: <t:{last_seen}:R>\n"
            f"> Estimated chance right now: `{chance}%` (based on `{len(recent_intervals)}` tracked cycles)."
        ),
        timestamp=datetime.now(timezone.utc),
    )
    return _apply_predictor_v2_embed_style(embed, guild), None


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


async def _fetch_seed_prediction_rows() -> list[dict]:
    session = await _get_http_session()
    headers = {
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
        "Referer": "https://growagarden2stock.com/stock/predictions/",
        "Origin": "https://growagarden2stock.com",
    }
    params = {"_": str(int(datetime.now(timezone.utc).timestamp()))}

    async with session.get(PREDICTIONS_API_URL, headers=headers, params=params) as response:
        response.raise_for_status()
        payload = await response.json()

    items = payload.get("items", {}) if isinstance(payload, dict) else {}
    raw_rows = items.get("seed", []) if isinstance(items, dict) else []

    rows: list[dict] = []
    for item in raw_rows:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        key = str(item.get("key", "")).strip()
        next_boundary = int(item.get("nextBoundary", 0) or 0)
        if not name or next_boundary <= 0:
            continue
        rows.append({"name": name, "key": key, "next_boundary": next_boundary})

    rows.sort(key=lambda item: item["next_boundary"])
    return rows


def _get_seed_prediction_chance(name: str, key: str | None = None) -> str:
    normalized_name = _normalize_seed_name(name)
    if normalized_name in SEED_PREDICT_CHANCES:
        return SEED_PREDICT_CHANCES[normalized_name]

    normalized_key = _normalize_seed_name((key or "").replace("_", " "))
    if normalized_key in SEED_PREDICT_CHANCES:
        return SEED_PREDICT_CHANCES[normalized_key]

    return "Unknown"


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
    ended = bool(giveaway.get("ended"))
    time_display = f"<t:{giveaway['end_ts']}:R>"
    prize_display = f"{giveaway['prize']} - Ended" if ended else giveaway["prize"]

    embed = discord.Embed(
        description=f"## {prize_display}\n{giveaway['description']}",
        color=discord.Color.red() if ended else discord.Color.green(),
    )
    embed.add_field(name="<:Winners:1525734637383450634> Winners", value=str(giveaway["winner_count"]), inline=True)
    embed.add_field(name="<:Entrees:1525734579099533413> Entrees", value=str(entries_count), inline=True)
    embed.add_field(name="<:Time:1525734537940701266> Time", value=time_display, inline=True)
    host_user_id = int(giveaway.get("host_user_id", 0) or 0)
    if host_user_id > 0:
        embed.add_field(name="<:GWhost:1525990871777017906> Host", value=f"<@{host_user_id}>", inline=False)

    guild_icon_url = giveaway.get("guild_icon_url")
    if isinstance(guild_icon_url, str) and guild_icon_url:
        embed.set_thumbnail(url=guild_icon_url)

    giveaway_id = giveaway.get("giveaway_id")
    if giveaway_id is not None:
        embed.set_footer(text=f"ID: {giveaway_id}")
    return embed


class GiveawayView(discord.ui.View):
    def __init__(self, giveaway_key: int):
        super().__init__(timeout=None)
        self.giveaway_key = giveaway_key

    @discord.ui.button(label="🎉 Join the giveaway!", style=discord.ButtonStyle.success, custom_id="fas_giveaway_join")
    async def join_giveaway(self, first, second):
        # Support both callback orders across discord.py/py-cord variants.
        if isinstance(first, discord.ui.Button):
            button = first
            interaction = second
        else:
            interaction = first
            button = second

        if not isinstance(interaction, discord.Interaction):
            return

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
    if giveaway.get("ended"):
        return

    wait_for = max(0, giveaway["end_ts"] - int(datetime.now(timezone.utc).timestamp()))
    await asyncio.sleep(wait_for)

    giveaway = GIVEAWAYS.get(giveaway_key)
    if not giveaway:
        return
    if giveaway.get("ended"):
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
    winner_mentions = ", ".join(f"<@{winner_id}>" for winner_id in winners)
    await channel.send(f"<:tada:1525999768369631273> Congratulations {winner_mentions}, you won {giveaway['prize']}!")


async def _create_giveaway_message(*, giveaway_key: int, channel: discord.abc.Messageable, channel_id: int, prize: str, description: str, duration_seconds: int, winner_count: int, host_user_id: int, guild_icon_url: str | None = None) -> discord.Message:
    now_ts = int(datetime.now(timezone.utc).timestamp())
    end_ts = now_ts + duration_seconds
    giveaway = {
        "giveaway_id": giveaway_key,
        "prize": prize,
        "description": description,
        "end_ts": end_ts,
        "winner_count": winner_count,
        "entries": set(),
        "ended": False,
        "channel_id": channel_id,
        "message_id": None,
        "host_user_id": host_user_id,
        "guild_icon_url": guild_icon_url,
    }
    GIVEAWAYS[giveaway_key] = giveaway

    view = GiveawayView(giveaway_key)
    embed = _build_giveaway_embed(giveaway)
    message = await channel.send(
        content=f"<@&{GIVEAWAY_PING_ROLE_ID}>",
        embed=embed,
        view=view,
        allowed_mentions=discord.AllowedMentions(roles=True),
    )
    giveaway["message_id"] = message.id
    asyncio.create_task(_finish_giveaway(giveaway_key))
    return message


async def _create_giveaway_from_args(*, giveaway_key: int, channel: discord.abc.Messageable | None, channel_id: int | None, host_user_id: int, guild_icon_url: str | None, prize: str, description: str, time_text: str, amount_of_winners: int) -> str | None:
    if channel is None or channel_id is None:
        return "Could not create giveaway in this channel."

    try:
        duration_seconds = _parse_duration_to_seconds(time_text)
    except ValueError:
        return "Invalid time format. Use like 1d_1h_1m_1s."

    if amount_of_winners <= 0:
        return "Amount of winners must be at least 1."

    await _create_giveaway_message(
        giveaway_key=giveaway_key,
        channel=channel,
        channel_id=channel_id,
        prize=prize,
        description=description,
        duration_seconds=duration_seconds,
        winner_count=int(amount_of_winners),
        host_user_id=host_user_id,
        guild_icon_url=guild_icon_url,
    )
    return None


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

    if BOT_MODE == "farmers":
        predictor_stock = dict(in_stock)
        predictor_stock.update(gear_in_stock)
        _record_predictor_v2_sightings(predictor_stock, now_unix)

    lines: list[str] = []
    gear_lines: list[str] = []
    best_rarity: str | None = None
    role_ping_keys: list[str] = []
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

        if key in STOCK_ROLE_PINGS:
            role_ping_keys.append(key)

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

        if key in STOCK_ROLE_PINGS:
            role_ping_keys.append(key)

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

    return lines, gear_lines, next_restock_text, next_restock_unix, best_rarity, role_ping_keys


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


def _build_stock_ping_content(role_ping_keys: list[str]) -> str | None:
    if not role_ping_keys:
        return None

    rare_rank = RARITY_RANK.get("rare", 3)
    seed_order = {entry["key"]: idx for idx, entry in enumerate(SEED_CONFIG)}
    gear_order = {entry["key"]: idx for idx, entry in enumerate(GEAR_CONFIG)}

    def _sort_key(key: str) -> tuple[int, int, int, str]:
        seed_entry = SEED_LOOKUP.get(key)
        if seed_entry is not None:
            rarity = str(seed_entry.get("rarity", ""))
            rank = RARITY_RANK.get(rarity, 0)
            bucket = rank if rank >= rare_rank else 999
            return (bucket, 0, seed_order.get(key, 999), key)

        gear_entry = GEAR_LOOKUP.get(key)
        if gear_entry is not None:
            rarity = str(gear_entry.get("rarity", ""))
            rank = RARITY_RANK.get(rarity, 0)
            bucket = rank if rank >= rare_rank else 999
            return (bucket, 1, gear_order.get(key, 999), key)

        return (999, 2, 999, key)

    unique_keys = list(dict.fromkeys(role_ping_keys))
    ordered_keys = sorted(unique_keys, key=_sort_key)
    ordered_mentions = [STOCK_ROLE_PINGS.get(key) for key in ordered_keys if STOCK_ROLE_PINGS.get(key)]
    return " ".join(ordered_mentions) if ordered_mentions else None


async def _resolve_seed_shop_channel() -> discord.TextChannel | None:
    channel = bot.get_channel(SEED_SHOP_CHANNEL_ID)
    if channel is None:
        try:
            channel = await bot.fetch_channel(SEED_SHOP_CHANNEL_ID)
        except Exception:
            return None
    return channel if isinstance(channel, discord.TextChannel) else None


async def _find_voice_kick_actor(guild: discord.Guild, target_user_id: int) -> int | None:
    action_name_candidates = ("member_disconnect", "member_move", "disconnect", "move")

    for attempt in range(VOICE_KICK_AUDIT_RETRIES):
        for action_name in action_name_candidates:
            action = getattr(discord.AuditLogAction, action_name, None)
            if action is None:
                continue
            try:
                async for entry in guild.audit_logs(limit=40, action=action):
                    if entry is None or entry.user is None or entry.target is None:
                        continue
                    if int(getattr(entry.target, "id", 0) or 0) != int(target_user_id):
                        continue
                    created_at = getattr(entry, "created_at", None)
                    if created_at is not None:
                        delta = abs((datetime.now(timezone.utc) - created_at).total_seconds())
                        if delta > VOICE_KICK_AUDIT_LOOKBACK_SECONDS:
                            continue

                    # For move actions, ensure this was from the watched channel when available.
                    if "move" in action_name:
                        before_channel = None
                        before_state = getattr(entry, "before", None)
                        if before_state is not None:
                            before_channel = getattr(before_state, "channel", None)
                        if before_channel is None:
                            extra = getattr(entry, "extra", None)
                            before_channel = getattr(extra, "channel", None)
                        before_channel_id = int(getattr(before_channel, "id", 0) or 0)
                        if before_channel_id and before_channel_id != WATCHED_VOICE_CHANNEL_ID:
                            continue

                    return int(entry.user.id)
            except Exception:
                continue

        if attempt < (VOICE_KICK_AUDIT_RETRIES - 1):
            await asyncio.sleep(VOICE_KICK_AUDIT_RETRY_DELAY_SECONDS)

    return None


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
async def on_message(message: discord.Message):
    global last_message_seed_role_sync

    if message.author.bot:
        return

    content = (message.content or "").strip()

    if message.guild is not None and BOT_MODE == "farmers" and message.channel.id == PREDICTOR_V2_CHANNEL_ID and content and not content.startswith("-"):
        embed, error_message = await _build_predictor_v2_response(content, message.guild)
        if embed is not None:
            await message.channel.send(embed=embed)
        elif error_message is not None:
            await message.channel.send(error_message)

    if BOT_MODE == "seed" and message.guild is not None:
        if content and not content.startswith("-"):
            words = content.split()
            if len(words) >= MESSAGE_MIN_WORDS:
                bank_data = _load_seed_bank()
                user_key = str(message.author.id)
                now_unix = int(datetime.now(timezone.utc).timestamp())

                message_counts = bank_data.setdefault("message_counts", {})
                message_bonus_remaining = bank_data.setdefault("message_bonus_remaining", {})
                spam_tracker = bank_data.setdefault("spam_tracker", {})

                raw_recent = spam_tracker.get(user_key, [])
                recent_timestamps = [
                    int(value)
                    for value in raw_recent
                    if str(value).isdigit()
                ]
                recent_timestamps = [
                    ts for ts in recent_timestamps
                    if (now_unix - ts) <= SPAM_WINDOW_SECONDS
                ]
                recent_timestamps.append(now_unix)
                spam_tracker[user_key] = recent_timestamps[-SPAM_TRACKER_LIMIT:]

                if len(recent_timestamps) >= SPAM_MESSAGE_THRESHOLD:
                    _set_seed_balance(bank_data, message.author.id, 0)
                    message_counts.pop(user_key, None)
                    message_bonus_remaining.pop(user_key, None)
                    spam_tracker[user_key] = []
                    _save_seed_bank(bank_data)
                    await _sync_seed_leader_roles(message.guild, bank_data)
                    await message.channel.send(
                        f"{message.author.mention} stop spamming. Your seed balance has been reset to `0`."
                    )
                    return

                streak_count = int(message_counts.get(user_key, 0) or 0) + 1
                bonus_remaining = int(message_bonus_remaining.get(user_key, 0) or 0)

                earned = MESSAGE_SEED_REWARD
                if bonus_remaining > 0:
                    earned = MESSAGE_SEED_REWARD * MESSAGE_BONUS_MULTIPLIER
                    bonus_remaining -= 1

                current_balance = _get_seed_balance(bank_data, message.author.id)
                _set_seed_balance(bank_data, message.author.id, current_balance + earned)

                if streak_count >= MESSAGE_BONUS_TRIGGER_MESSAGES:
                    streak_count = 0
                    bonus_remaining += MESSAGE_BONUS_MESSAGES

                message_counts[user_key] = streak_count
                if bonus_remaining > 0:
                    message_bonus_remaining[user_key] = bonus_remaining
                else:
                    message_bonus_remaining.pop(user_key, None)

                _save_seed_bank(bank_data)

                if (now_unix - last_message_seed_role_sync) >= MESSAGE_SEED_ROLE_SYNC_INTERVAL:
                    last_message_seed_role_sync = now_unix
                    await _sync_seed_leader_roles(message.guild, bank_data)

    await bot.process_commands(message)


@bot.event
async def on_voice_state_update(member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
    if member.bot:
        return
    if member.guild is None:
        return
    if int(member.id) not in VOICE_KICK_WATCH_USER_IDS:
        return

    before_channel_id = int(before.channel.id) if before.channel is not None else 0
    after_channel_id = int(after.channel.id) if after.channel is not None else 0

    if before_channel_id != WATCHED_VOICE_CHANNEL_ID:
        return
    if after_channel_id == WATCHED_VOICE_CHANNEL_ID:
        return

    actor_user_id = await _find_voice_kick_actor(member.guild, member.id)
    if actor_user_id is None and not VOICE_KICK_ALERT_ON_UNRESOLVED_ACTOR:
        return

    alert_channel = bot.get_channel(KICK_ALERT_CHANNEL_ID)
    if alert_channel is None:
        try:
            alert_channel = await bot.fetch_channel(KICK_ALERT_CHANNEL_ID)
        except Exception:
            return

    if not isinstance(alert_channel, discord.TextChannel):
        return

    if actor_user_id is not None:
        message = (
            f"@everyone <@{actor_user_id}> Has Kicked <@{member.id}>. "
            f"Shame on <@{actor_user_id}> for kicking <@{member.id}>"
        )
    else:
        message = (
            f"@everyone Someone Has Kicked <@{member.id}>. "
            f"Shame on them for kicking <@{member.id}>"
        )

    await alert_channel.send(
        message,
        allowed_mentions=discord.AllowedMentions(everyone=True, users=True),
    )


@bot.event
async def on_ready():
    global TREE_SYNCED
    _configure_commands_for_mode()
    if bot.user:
        print(f"{bot.user} is online. mode={BOT_MODE}")
    if app_commands is not None and not TREE_SYNCED:
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
    if app_commands is None and hasattr(bot, "sync_commands") and not TREE_SYNCED:
        for attempt in range(1, 6):
            try:
                await bot.sync_commands(guild_ids=[TARGET_GUILD_ID])
                TREE_SYNCED = True
                print(f"Pycord slash commands synced for guild {TARGET_GUILD_ID}.")
                break
            except Exception as exc:
                print(f"Pycord slash sync attempt {attempt}/5 failed: {exc}")
                if attempt < 5:
                    await asyncio.sleep(attempt * 2)
    if BOT_MODE == "farmers":
        try:
            await _ensure_seed_shop_live_message_exists()
        except Exception as exc:
            print(f"Failed to initialize live seed shop message: {exc}")
        if not seed_shop_live_loop.is_running():
            seed_shop_live_loop.start()


if app_commands is not None:
    @bot.tree.error
    async def on_app_command_error(interaction: discord.Interaction, error):
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


if app_commands is not None:
    @bot.tree.command(name="giveaway", description="Create a giveaway")
    @app_commands.describe(prize="Giveaway prize", description="Giveaway description", time="Duration like 1d_1h_1m_1s", amount_of_winners="How many winners")
    async def giveaway_slash(interaction: discord.Interaction, prize: str, description: str, time: str, amount_of_winners: int):
        await interaction.response.defer(ephemeral=True)
        error_message = await _create_giveaway_from_args(
            giveaway_key=interaction.id,
            channel=interaction.channel,
            channel_id=interaction.channel_id,
            host_user_id=interaction.user.id,
            guild_icon_url=(interaction.guild.icon.url if interaction.guild and interaction.guild.icon else None),
            prize=prize,
            description=description,
            time_text=time,
            amount_of_winners=int(amount_of_winners),
        )
        if error_message:
            await interaction.followup.send(error_message, ephemeral=True)
            return
        await interaction.followup.send("Giveaway created.", ephemeral=True)


if app_commands is None and hasattr(bot, "slash_command"):
    @bot.slash_command(name="giveaway", description="Create a giveaway", guild_ids=[TARGET_GUILD_ID])
    async def giveaway_slash_fallback(ctx, prize: str, description: str, time: str, amount_of_winners: int):
        error_message = await _create_giveaway_from_args(
            giveaway_key=ctx.interaction.id,
            channel=ctx.channel,
            channel_id=(ctx.channel.id if ctx.channel else None),
            host_user_id=ctx.author.id,
            guild_icon_url=(ctx.guild.icon.url if getattr(ctx, "guild", None) and ctx.guild.icon else None),
            prize=prize,
            description=description,
            time_text=time,
            amount_of_winners=int(amount_of_winners),
        )
        if error_message:
            await ctx.respond(error_message, ephemeral=True)
            return
        await ctx.respond("Giveaway created.", ephemeral=True)


@bot.command(name="greroll")
async def greroll(ctx: commands.Context, giveaway_id: int):
    giveaway = GIVEAWAYS.get(giveaway_id)
    if giveaway is None:
        await ctx.send(f"I could not find a giveaway with ID {giveaway_id}.")
        return

    host_user_id = int(giveaway.get("host_user_id", 0) or 0)
    if host_user_id <= 0:
        await ctx.send("This giveaway is missing host data and cannot be rerolled.")
        return
    if ctx.author.id != host_user_id:
        await ctx.send(f"Only the giveaway host <@{host_user_id}> can reroll this giveaway.")
        return

    if not giveaway.get("ended"):
        await ctx.send("That giveaway has not ended yet. You can reroll after it ends.")
        return

    entries = list(giveaway.get("entries", set()))
    if not entries:
        await ctx.send("This giveaway has no valid entries to reroll.")
        return

    winner_count = min(int(giveaway.get("winner_count", 1) or 1), len(entries))
    winners = random.sample(entries, k=winner_count)
    winner_mentions = ", ".join(f"<@{winner_id}>" for winner_id in winners)
    await ctx.send(f"<:tada:1525999768369631273> Congratulations {winner_mentions}, you won {giveaway.get('prize', 'Unknown Prize')}!")


@bot.command(name="genterlist")
async def genterlist(ctx: commands.Context, giveaway_id: int):
    giveaway = GIVEAWAYS.get(giveaway_id)
    if giveaway is None:
        await ctx.send(f"I could not find a giveaway with ID {giveaway_id}.")
        return

    entries = sorted(int(user_id) for user_id in giveaway.get("entries", set()))
    if not entries:
        await ctx.send(f"Giveaway ID {giveaway_id} has no entries yet.")
        return

    lines = [f"{index}. <@{user_id}>" for index, user_id in enumerate(entries, start=1)]
    header = f"Giveaway ID {giveaway_id} entrants ({len(entries)}):\n"
    message = header + "\n".join(lines)

    if len(message) <= 1900:
        await ctx.send(message)
        return

    current = header
    for line in lines:
        candidate = current + line + "\n"
        if len(candidate) > 1900:
            await ctx.send(current.rstrip())
            current = line + "\n"
        else:
            current = candidate
    if current.strip():
        await ctx.send(current.rstrip())


@bot.command(name="forceend")
async def forceend(ctx: commands.Context, giveaway_id: int):
    giveaway = GIVEAWAYS.get(giveaway_id)
    if giveaway is None:
        await ctx.send(f"I could not find a giveaway with ID {giveaway_id}.")
        return

    if giveaway.get("ended"):
        await ctx.send(f"Giveaway ID {giveaway_id} is already ended.")
        return

    giveaway["end_ts"] = int(datetime.now(timezone.utc).timestamp())
    await _finish_giveaway(giveaway_id)
    await ctx.send(f"Force ended giveaway ID {giveaway_id}.")


@bot.command(name="seedclaim")
async def seedclaim(ctx: commands.Context):
    bank_data = _load_seed_bank()
    now_unix = int(datetime.now(timezone.utc).timestamp())
    next_claim_unix = _get_claim_cooldown_unix(bank_data, ctx.author.id)

    if next_claim_unix > now_unix:
        await ctx.send(f"You already claimed. Next claim is <t:{next_claim_unix}:R>.")
        return

    is_booster = _is_server_booster(ctx.author)
    top_users = _highest_seed_balances(bank_data, top_n=3)
    leaderboard_multiplier = 1.0
    if len(top_users) > 0 and top_users[0] == ctx.author.id:
        leaderboard_multiplier = TOP1_CLAIM_MULTIPLIER
    elif len(top_users) > 1 and top_users[1] == ctx.author.id:
        leaderboard_multiplier = TOP2_CLAIM_MULTIPLIER
    elif len(top_users) > 2 and top_users[2] == ctx.author.id:
        leaderboard_multiplier = TOP3_CLAIM_MULTIPLIER

    booster_multiplier_applied = False
    if is_booster:
        amount = random.randint(BOOSTER_SEED_CLAIM_MIN, BOOSTER_SEED_CLAIM_MAX)
        if random.random() < BOOSTER_CLAIM_MULTIPLIER_CHANCE:
            amount = int(amount * BOOSTER_CLAIM_MULTIPLIER)
            booster_multiplier_applied = True
    else:
        amount = random.randint(SEED_CLAIM_MIN, SEED_CLAIM_MAX)

    if leaderboard_multiplier > 1.0 and not booster_multiplier_applied:
        amount = int(amount * leaderboard_multiplier)

    current_balance = _get_seed_balance(bank_data, ctx.author.id)
    new_balance = current_balance + amount
    _set_seed_balance(bank_data, ctx.author.id, new_balance)
    _set_claim_cooldown_unix(bank_data, ctx.author.id, now_unix + SEED_CLAIM_COOLDOWN_SECONDS)
    _save_seed_bank(bank_data)
    await _sync_seed_leader_roles(ctx.guild, bank_data)

    bonus_parts: list[str] = []
    if booster_multiplier_applied:
        bonus_parts.append(f"Booster x{BOOSTER_CLAIM_MULTIPLIER:g}")
    if leaderboard_multiplier > 1.0 and not booster_multiplier_applied:
        bonus_parts.append(f"Collector x{leaderboard_multiplier:g}")
    bonus_text = f" ({', '.join(bonus_parts)})" if bonus_parts else ""
    await ctx.send(f"{ctx.author.mention} claimed `{amount}` seeds{bonus_text}. You now have `{new_balance}` seeds.")


@bot.command(name="seedbalance")
async def seedbalance(ctx: commands.Context):
    bank_data = _load_seed_bank()
    balance = _get_seed_balance(bank_data, ctx.author.id)
    await ctx.send(f"{ctx.author.mention} you currently have `{balance}` seeds.")


@bot.command(name="seeddebug")
async def seeddebug(ctx: commands.Context):
    if ctx.author.id not in SEED_CLAIM_WIPE_ADMINS:
        await ctx.send("You are not allowed to use this command.")
        return

    user_id = ctx.author.id
    effective_data = _load_seed_bank()
    effective_balance = _get_seed_balance(effective_data, user_id)
    effective_updated = int(effective_data.get("updated_at", 0) or 0)

    file_balance = None
    file_updated = None
    try:
        _ensure_seed_bank_file()
        with open(SEED_BANK_FILE, "r", encoding="utf-8") as f:
            file_data = json.load(f)
        if isinstance(file_data, dict):
            file_balance = int((file_data.get("balances", {}) or {}).get(str(user_id), 0) or 0)
            file_updated = int(file_data.get("updated_at", 0) or 0)
    except Exception:
        pass

    redis_balance = None
    redis_updated = None
    redis_ok = False
    client = _get_seed_redis_client()
    if client is not None:
        try:
            raw = client.get(REDIS_SEED_BANK_KEY)
            if raw:
                redis_data = json.loads(raw)
                if isinstance(redis_data, dict):
                    redis_balance = int((redis_data.get("balances", {}) or {}).get(str(user_id), 0) or 0)
                    redis_updated = int(redis_data.get("updated_at", 0) or 0)
                    redis_ok = True
        except Exception:
            redis_ok = False

    await ctx.send(
        "Seed Debug\n"
        f"Instance: `{BOT_INSTANCE_ID}` PID: `{os.getpid()}`\n"
        f"Redis URL set: `{bool(REDIS_URL)}` Redis connected: `{redis_ok}`\n"
        f"SEED_DATA_DIR: `{SEED_DATA_DIR}`\n"
        f"SEED_BANK_FILE: `{SEED_BANK_FILE}`\n"
        f"Effective balance: `{effective_balance}` updated_at: `{effective_updated}`\n"
        f"File balance: `{file_balance}` updated_at: `{file_updated}`\n"
        f"Redis balance: `{redis_balance}` updated_at: `{redis_updated}`"
    )


@bot.command(name="addtoshop")
async def addtoshop(ctx: commands.Context, *, raw_args: str):
    if not _has_seed_shop_seller_role(ctx.author):
        await ctx.send(f"This command can only be used by <@&{SEED_SHOP_MANAGER_ROLE_ID}>.")
        return
    parsed = _parse_item_price_arguments(raw_args)
    if parsed is None:
        await ctx.send("Usage: -addtoshop <Name> <Price>")
        return
    name, price = parsed
    if price <= 0:
        await ctx.send("Price must be greater than 0.")
        return

    store_data = _load_seed_store()
    item_id = int(store_data.get("next_item_id", 1))
    store_data["next_item_id"] = item_id + 1
    store_data.setdefault("items", []).append(
        {
            "id": item_id,
            "name": name.strip(),
            "price": int(price),
            "host_id": ctx.author.id,
            "shop_type": "normal",
            "active": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    _save_seed_store(store_data)
    await ctx.send(f"Added {name} For {price} Seeds.")


@bot.command(name="addtosshop")
async def addtosshop(ctx: commands.Context, *, raw_args: str):
    if not _has_seed_shop_seller_role(ctx.author):
        await ctx.send(f"This command can only be used by <@&{SEED_SHOP_MANAGER_ROLE_ID}>.")
        return
    parsed = _parse_item_price_arguments(raw_args)
    if parsed is None:
        await ctx.send("Usage: -addtosshop <Item> <Price>")
        return
    name, price = parsed
    if price <= 0:
        await ctx.send("Price must be greater than 0.")
        return

    store_data = _load_seed_store()
    item_id = int(store_data.get("next_item_id", 1))
    store_data["next_item_id"] = item_id + 1
    store_data.setdefault("items", []).append(
        {
            "id": item_id,
            "name": name.strip(),
            "price": int(price),
            "host_id": ctx.author.id,
            "shop_type": "super",
            "active": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    _save_seed_store(store_data)
    await ctx.send(f"Added {name} For {price} Seeds.")


@bot.command(name="seedshop")
async def seedshop(ctx: commands.Context):
    store_data = _load_seed_store()
    normal_items = [item for item in _active_seed_shop_items(store_data) if str(item.get("shop_type", "normal")) == "normal"]
    pages = _seed_shop_item_pages(normal_items)
    view = SeedShopPagesView(pages, total_items=len(normal_items))
    embed = _build_seed_shop_page_embed(pages[0], 0, len(pages), len(normal_items))
    await ctx.send(embed=embed, view=view)


@bot.command(name="supershop")
async def supershop(ctx: commands.Context):
    if not _is_server_booster(ctx.author):
        await ctx.send("Only server boosters can use -supershop.")
        return

    store_data = _load_seed_store()
    super_items = [item for item in _active_seed_shop_items(store_data) if str(item.get("shop_type", "normal")) == "super"]
    pages = _seed_shop_item_pages(super_items)
    view = SeedShopPagesView(pages, total_items=len(super_items))
    embed = _build_seed_shop_page_embed(pages[0], 0, len(pages), len(super_items))
    await ctx.send(embed=embed, view=view)


@bot.command(name="seedleaderboard", aliases=["seedlb"])
async def seedleaderboard(ctx: commands.Context):
    bank_data = _load_seed_bank()
    rows = _seed_leaderboard_rows(bank_data)
    pages = _seed_leaderboard_pages(rows)
    view = SeedLeaderboardPagesView(ctx.guild, pages, total_rows=len(rows))
    embed = _build_seed_leaderboard_embed(ctx.guild, pages[0], 0, len(pages), len(rows))
    await ctx.send(embed=embed, view=view)


@bot.command(name="register")
async def register(ctx: commands.Context, *, roblox_user: str):
    username = roblox_user.strip()
    if len(username) < 3:
        await ctx.send("Usage: -register <roblox user>")
        return
    if len(username) > 32:
        await ctx.send("Roblox username looks too long. Keep it under 33 characters.")
        return

    bank_data = _load_seed_bank()
    _set_registered_roblox_user(bank_data, ctx.author.id, username)
    _save_seed_bank(bank_data)
    await ctx.send(f"{ctx.author.mention} registered Roblox user: `{username}`")


@bot.command(name="buy")
async def buy(ctx: commands.Context, *, raw_args: str):
    item_id = _parse_buy_item_id(raw_args)
    if item_id is None:
        await ctx.send("Usage: -buy <item_id>")
        return

    bank_data = _load_seed_bank()
    roblox_user = _get_registered_roblox_user(bank_data, ctx.author.id)
    if not roblox_user:
        await ctx.send("You must register first with `-register <roblox user>` before buying.")
        return

    store_data = _load_seed_store()
    items = _active_seed_shop_items(store_data)
    item = _find_seed_shop_item_by_id(items, item_id)

    if item is None:
        await ctx.send(f"I could not find an active item with ID `{item_id}`.")
        return

    item_shop_type = str(item.get("shop_type", "normal"))
    if item_shop_type == "super" and not _is_server_booster(ctx.author):
        await ctx.send("That item is in Super Shop and only boosters can buy it.")
        return

    host_id = int(item.get("host_id", 0) or 0)
    if host_id <= 0:
        await ctx.send("This item has an invalid host and cannot be purchased.")
        return

    if host_id == ctx.author.id:
        await ctx.send("You cannot buy your own item.")
        return

    purchase_channel = bot.get_channel(SEED_PURCHASE_CHANNEL_ID)
    if purchase_channel is None:
        try:
            purchase_channel = await bot.fetch_channel(SEED_PURCHASE_CHANNEL_ID)
        except Exception:
            purchase_channel = None

    if not isinstance(purchase_channel, discord.TextChannel):
        await ctx.send(f"I could not access <#{SEED_PURCHASE_CHANNEL_ID}>.")
        return

    price = int(item.get("price", 0) or 0)
    buyer_balance = _get_seed_balance(bank_data, ctx.author.id)
    if buyer_balance < price:
        await ctx.send(f"You need `{price}` seeds, but you only have `{buyer_balance}`.")
        return

    _set_seed_balance(bank_data, ctx.author.id, buyer_balance - price)
    host_balance = _get_seed_balance(bank_data, host_id)
    _set_seed_balance(bank_data, host_id, host_balance + price)
    _save_seed_bank(bank_data)
    await _sync_seed_leader_roles(ctx.guild, bank_data)

    item["active"] = False
    _save_seed_store(store_data)

    sale_embed = discord.Embed(
        description=(
            "# Your Item has been bought!\n"
            f"{ctx.author.mention} has bought your {item.get('name', 'item')} (ID `{int(item.get('id', 0) or 0)}`) please send them the item!\n\n"
            f"Buyer Roblox: `{roblox_user}`\n\n"
            "Action - In-complete.\n\n"
            f"💰When comlpete you will get: `{price}`"
        ),
        color=discord.Color.green(),
    )
    sale_view = CompleteSellView(host_id=host_id, buyer_id=ctx.author.id, price=price)
    await purchase_channel.send(content=f"<@{host_id}>", embed=sale_embed, view=sale_view)

    await ctx.send(
        f"Purchase submitted for ID `{int(item.get('id', 0) or 0)}` (`{item.get('name', 'item')}`) from <@{host_id}>. "
        f"`{price}` seeds deducted. Your new balance is `{buyer_balance - price}`."
    )


@bot.command(name="seedclaimwipe")
async def seedclaimwipe(ctx: commands.Context, target: str):
    if ctx.author.id not in SEED_CLAIM_WIPE_ADMINS:
        await ctx.send("You are not allowed to use this command.")
        return

    bank_data = _load_seed_bank()
    target_clean = target.strip().lower()
    if target_clean == "all":
        bank_data["claim_cooldowns"] = {}
        _save_seed_bank(bank_data)
        await ctx.send(f"<@&{SEED_CLAIMWIPE_PING_ROLE_ID}> Wiped claim cooldowns for all users.")
        return

    target_id = None
    mention_match = re.fullmatch(r"<@!?(\d+)>", target.strip())
    if mention_match:
        target_id = int(mention_match.group(1))
    elif target.strip().isdigit():
        target_id = int(target.strip())

    if target_id is None:
        await ctx.send("Usage: -seedclaimwipe all OR -seedclaimwipe @user")
        return

    _clear_claim_cooldown(bank_data, target_id)
    _save_seed_bank(bank_data)
    await ctx.send(f"Wiped claim cooldown for <@{target_id}>.")


@bot.command(name="addseeds")
async def addseeds(ctx: commands.Context, user: discord.Member, amount: int):
    if not _has_seed_balance_admin_role(ctx.author):
        await ctx.send("You are not allowed to use this command.")
        return
    if amount <= 0:
        await ctx.send("Amount must be greater than 0.")
        return

    bank_data = _load_seed_bank()
    current = _get_seed_balance(bank_data, user.id)
    updated = current + int(amount)
    _set_seed_balance(bank_data, user.id, updated)
    _save_seed_bank(bank_data)
    await _sync_seed_leader_roles(ctx.guild, bank_data)
    await ctx.send(f"Added `{amount}` seeds to {user.mention}. New balance: `{updated}`.")


@bot.command(name="removeseeds", aliases=["remove_seeds"])
async def remove_seeds(ctx: commands.Context, user: discord.Member, amount: int):
    if not _has_seed_balance_admin_role(ctx.author):
        await ctx.send("You are not allowed to use this command.")
        return
    if amount <= 0:
        await ctx.send("Amount must be greater than 0.")
        return

    bank_data = _load_seed_bank()
    current = _get_seed_balance(bank_data, user.id)
    updated = max(0, current - int(amount))
    _set_seed_balance(bank_data, user.id, updated)
    _save_seed_bank(bank_data)
    await _sync_seed_leader_roles(ctx.guild, bank_data)
    await ctx.send(f"Removed `{amount}` seeds from {user.mention}. New balance: `{updated}`.")


@bot.command(name="seedstock")
async def seedstock(ctx: commands.Context):
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


@bot.command(name="predict")
async def predict(ctx: commands.Context, *, fruit_name: str):
    embed, error_message = await _build_predictor_v2_response(fruit_name, ctx.guild)
    if embed is not None:
        await ctx.send(embed=embed)
        return
    await ctx.send(error_message or "Could not build a prediction right now.")


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
    _update_bucket_trust_level(bucket)
    _save_data(data)
    await _sync_vouch_scam_roles(ctx.guild, user.id, bucket)
    await ctx.send(f"Added vouch for {user.mention}. Vouch ID: {entry_id}")


@bot.command(name="addvouch")
async def addvouch(ctx: commands.Context, user: discord.Member, voucher: discord.Member, *, reason: str):
    if not _in_allowed_channel(ctx, VOUCH_CHANNEL_ID):
        await ctx.send(f"This command can only be used in <#{VOUCH_CHANNEL_ID}>.")
        return

    data = _load_data()
    bucket = _get_user_bucket(data, user.id)
    entry_id = int(data.get("next_vouch_id", 1))
    data["next_vouch_id"] = entry_id + 1
    bucket["vouches"].append({
        "id": entry_id,
        "by": voucher.id,
        "reason": reason.strip(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    _update_bucket_trust_level(bucket)
    _save_data(data)
    await _sync_vouch_scam_roles(ctx.guild, user.id, bucket)
    await ctx.send(f"Added vouch for {user.mention} from {voucher.mention}. Vouch ID: {entry_id}")


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
    _update_bucket_trust_level(bucket)
    _save_data(data)
    await _sync_vouch_scam_roles(ctx.guild, user.id, bucket)

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
    _update_bucket_trust_level(bucket)
    vouches = bucket.get("vouches", [])
    scams = bucket.get("scams", [])

    vouch_lines = []
    for index, item in enumerate(vouches, start=1):
        by_user_id = int(item.get("by", 0))
        by_user_mention = _mention_for_user(ctx.guild, by_user_id) if by_user_id else "Unknown User"
        reason = str(item.get("reason", "No reason provided"))
        item_id = item.get("id", "?")
        vouch_lines.append(f"{index}. {by_user_mention} {reason} <ID: {item_id}>")

    scam_lines = []
    for index, item in enumerate(scams, start=1):
        by_user_id = int(item.get("reported_by", 0))
        by_user_mention = _mention_for_user(ctx.guild, by_user_id) if by_user_id else "Unknown User"
        reason = str(item.get("reason", "No reason provided"))
        item_id = item.get("id", "?")
        scam_lines.append(f"{index}. {by_user_mention} {reason} <ID: {item_id}>")

    vouch_text = "\n".join(vouch_lines) if vouch_lines else "None"
    scam_text = "\n".join(scam_lines) if scam_lines else "None"

    saved_level = str(bucket.get("trust_level", "")).strip().lower()
    saved_role_id = int(bucket.get("trust_role_id", 0) or 0)
    if saved_level == "negative" and saved_role_id > 0:
        trust_level_text = (
            f"<:Lowest:1526219034876579930> This users highest trusted role is in the negatives and is: <@&{saved_role_id}>"
        )
    else:
        positive_role_id = saved_role_id if saved_role_id > 0 else _highest_positive_trust_role_id(len(vouches))
        trust_level_text = (
            f"<:Highest:1526219072541556746> This users highest trust level is: <@&{positive_role_id}>"
        )

    embed = discord.Embed(title=f"{user.display_name} Vouch and Scam Reports", color=discord.Color.green())
    embed.description = (
        f"User: {user.mention}\n\n"
        f"<:vouch_list:1525700827426066472>Vouch Reports: {len(vouches)}\n\n"
        f"<:Scam_list:1525701001858908251>Scam Reports: {len(scams)}\n\n"
        f"{trust_level_text}\n\n"
        f"Vouch list,\n{vouch_text}\n\n"
        f"Scam List,\n{scam_text}"
    )

    if len(embed.description) > 4096:
        embed.description = (
            f"User: {user.mention}\n\n"
            f"<:vouch_list:1525700827426066472>Vouch Reports: {len(vouches)}\n\n"
            f"<:Scam_list:1525701001858908251>Scam Reports: {len(scams)}\n\n"
            f"{trust_level_text}\n\n"
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

    updated_bucket = _get_user_bucket(data, removed_for_user)
    _update_bucket_trust_level(updated_bucket)
    _save_data(data)
    await _sync_vouch_scam_roles(ctx.guild, removed_for_user, updated_bucket)
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

    updated_bucket = _get_user_bucket(data, removed_for_user)
    _update_bucket_trust_level(updated_bucket)
    _save_data(data)
    await _sync_vouch_scam_roles(ctx.guild, removed_for_user, updated_bucket)
    await ctx.send(f"Removed scam report ID {scam_id} for {_mention_for_user(ctx.guild, removed_for_user)}.")


if __name__ == "__main__":
    bot.run(TOKEN)
