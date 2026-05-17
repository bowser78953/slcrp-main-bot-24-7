import os
import json
import re
import asyncio
import random
import time
import sys
import traceback
import aiohttp
from urllib.parse import unquote
from collections import deque
from datetime import datetime, timedelta, timezone
import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv


# Compatibility shims for modal APIs across py-cord / discord.py variants.
if not hasattr(discord, "InputTextStyle") and hasattr(discord, "TextStyle"):
    discord.InputTextStyle = discord.TextStyle
if not hasattr(discord.ui, "TextInput") and hasattr(discord.ui, "InputText"):
    discord.ui.TextInput = discord.ui.InputText


ENV_PATH = os.path.join(os.path.dirname(__file__), ".env.fresh")
if os.path.exists(ENV_PATH):
    load_dotenv(dotenv_path=ENV_PATH, override=True)

TOKEN = os.getenv("NEW_BOT_TOKEN")
PREFIX = os.getenv("NEW_BOT_PREFIX", "!")
STATUS_TEXT = os.getenv("NEW_BOT_STATUS", "Managing the server")
ERLC_API_KEY_PART = os.getenv("ERLC_API_KEY_PART", "DucAfpAQtDEaUScIirXg").strip()
ERLC_SERVER_ID = os.getenv("ERLC_SERVER_ID", "pLusPFVQAdmGTprXvWEutufuBUsgnyrcmfczzvcd").strip()
ERLC_API_KEY = f"{ERLC_API_KEY_PART}-{ERLC_SERVER_ID}"
ERLC_API_BASE_URL = "https://api.erlc.gg/v2"

if not TOKEN:
    print("Missing NEW_BOT_TOKEN in environment variables.")
    raise SystemExit(1)




intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix=PREFIX, intents=intents, help_command=None)

BASE_ROLE_ID = 1493343098296598538
WARN_COMMAND_ROLE_ID = 1493344271862988911
WARN_LOG_CHANNEL_ID = 1493428931829825586
MSWBAN_AUDIT_LOG_CHANNEL_ID = 1505310257436430387
AUTOMOD_LOG_CHANNEL_ID = 1493437523798790275
AUTOMOD_BYPASS_ROLE_ID = 1493712797203173417
SPAM_BYPASS_ROLE_ID = 1493712904116113639
ROLE_MANAGER_COMMAND_ROLE_ID = 1493713006549536798
ALL_SERVER_BAN_COMMAND_ROLE_ID = 1493713085012246609
AUTOMOD_TIMEOUT_MINUTES = 10
SPAM_AUTOMOD_WINDOW_SECONDS = 3
SPAM_AUTOMOD_THRESHOLD = 4
SPAM_AUTOMOD_REPORT_CHANNEL_ID = 1494025992811839711
SPAM_AUTOMOD_PING_ROLE_ID = WARN_COMMAND_ROLE_ID
WARN_DURATION_DAYS = 7
WARN_MAX_COUNT = 5
UNBAN_CHECK_INTERVAL_SECONDS = 30
AUTOMOD_NSFW_LOG_CHANNEL_ID = 1493708444421718076
TEMP_VC_TRIGGER_CHANNEL_ID = 1493100810593243321
BOOSTER_ROLE_ID = 1493085108792725504
VC_LOCK_BYPASS_ROLE_ID = 1493334798402588763
HELP_REQUEST_PING_ONLY_CHANNEL_ID = 1493098132773535795
HELP_REQUEST_LOG_CHANNEL_ID = 1494031013532139712
INVITE_AUTOMOD_LOG_CHANNEL_ID = 1494033274769637580
ALT_DETECTION_LOG_CHANNEL_ID = 1494039404652527787
ANTI_BOT_LOG_CHANNEL_ID = 1494414785763348621
TICKET_RULES_CHANNEL_ID = 1493095132852129873
TICKET_CLOSE_LOG_CHANNEL_ID = 1494822378851668121
MAIN_SERVER_GUILD_ID = 1397084580816621618
RELOAD_COMMAND_ROLE_ID = 1495581053862019215
RP_COMMAND_ROLE_ID = 1493343098296598538
TICKET_COMMAND_ROLE_ID = 1493343282820812872
MAIN_SERVER_ANY_ROLE_NAMES = {
    "->bot permissions<-",
    "bypass automod",
    "bypass spam",
    "no-roles permissions",
    "swban permissions",
    "bot control permissions",
    "->discord staff board<-",
    "discord staff overseer",
    "slcrp | discord staff board",
}
RP_CHANNEL_ID = 1504639818674471072
RP_CHANNEL_OPTIONS = {
    "1": "⟨🏙️ ⟩ 𝐑𝐢𝐯𝐞𝐫 𝐂𝐢𝐭𝐲 𝐑𝐏",
    "2": "⟨🛣️ ⟩ 𝐇𝐢𝐠𝐡𝐰𝐚𝐲 𝐑𝐏",
    "3": "⟨🏞️ ⟩ 𝐇𝐢𝐠𝐡 𝐑𝐨𝐜𝐤 𝐏𝐚𝐫𝐤 𝐑𝐏",
    "4": "⟨🌆 ⟩ 𝐑𝐢𝐯𝐞𝐫 𝐂𝐢𝐭𝐲 𝐂𝐨𝐮𝐧𝐭𝐲 𝐑𝐏",
    "5": "⟨🌇 ⟩ 𝐒𝐩𝐫𝐢𝐧𝐠𝐟𝐢𝐞𝐥𝐝 𝐂𝐨𝐮𝐧𝐭𝐲 𝐑𝐏",
    "6": "⟨🏢 ⟩ 𝐒𝐩𝐫𝐢𝐧𝐠𝐟𝐢𝐞𝐥𝐝 𝐑𝐏",
    "7": "⟨🌃 ⟩ 𝐅𝐮𝐥𝐥 𝐌𝐚𝐩 𝐑𝐏",
    "8": "⟨🎆 ⟩ 𝐈𝐧-𝐆𝐚𝐦𝐞 𝐄𝐯𝐞𝐧𝐭",
    "9": "⟨⛔⟩ 𝐒𝐞𝐫𝐯𝐞𝐫 𝐒𝐡𝐮𝐭 𝐃𝐨𝐰𝐧",
    "10": "⟨🔃⟩ 𝐒𝐞𝐫𝐯𝐞𝐫 𝐑𝐞𝐬𝐭𝐚𝐫𝐭",
}
RP_CHANNEL_COOLDOWN: dict[int, datetime] = {}
RP_COOLDOWN_SECONDS = 300
RP_HISTORY_LIMIT = 7
RP_CURRENT_NAME: str | None = None
RP_CURRENT_SINCE: datetime | None = None
RP_CHANGE_HISTORY: deque[tuple[str, datetime]] = deque(maxlen=RP_HISTORY_LIMIT)
ALT_DETECTION_MAX_ACCOUNT_AGE_DAYS = 7
TICKET_TRANSCRIPT_RETENTION_DAYS = 7
TICKET_TRANSCRIPT_CLEANUP_INTERVAL_SECONDS = 3600
SPAM_AUTOMOD_STATE: dict[tuple[int, int, int], deque] = {}
SPAM_AUTOMOD_RECENT_ACTION: dict[int, datetime] = {}
DISCORD_INVITE_CODE_REGEX = re.compile(
    r"(?:https?://)?(?:www\.)?(?:discord\.gg|discord(?:app)?\.com/invite)/([A-Za-z0-9-]+)",
    re.IGNORECASE,
)

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_LOCAL_DATA_DIR = os.path.abspath(os.path.join(_BASE_DIR, "data"))
_PARENT_DATA_DIR = os.path.abspath(os.path.join(_BASE_DIR, "..", "data"))

# Prefer repo-local data when running the root bot entrypoint; fallback keeps compatibility.
DATA_DIR = _LOCAL_DATA_DIR if os.path.isdir(_LOCAL_DATA_DIR) else _PARENT_DATA_DIR

ROLE_SAVE_PATH = os.path.join(DATA_DIR, "saved_roles_fresh.json")
WARNINGS_PATH = os.path.join(DATA_DIR, "warnings_fresh.json")
SANCTIONS_PATH = os.path.join(DATA_DIR, "sanctions_fresh.json")
AUTOMOD_BLACKLIST_PATH = os.path.join(DATA_DIR, "automod_blacklist_fresh.txt")
AUTOMOD_NSFW_BLACKLIST_PATH = os.path.join(DATA_DIR, "automod_nsfw_blacklist_fresh.txt")
TEMP_VC_DATA_PATH = os.path.join(DATA_DIR, "temp_vcs_fresh.json")
APPROVED_INVITES_PATH = os.path.join(DATA_DIR, "approved_invites.json")
APPROVED_BOTS_PATH = os.path.join(DATA_DIR, "approved_bots.json")
TICKET_TRANSCRIPTS_DIR = os.path.join(DATA_DIR, "ticket_transcripts")
LEVELS_PATH = os.path.join(DATA_DIR, "levels.json")
RUNTIME_SETTINGS_PATH = os.path.join(DATA_DIR, "runtime_settings.json")
REACTION_ROLE_MESSAGES_PATH = os.path.join(DATA_DIR, "reaction_role_messages.json")
BAN_APPEAL_GUILD_ID = 1500595644220444752
BAN_APPEAL_DM_QUEUE_PATH = os.path.join(DATA_DIR, "ban_appeal_dm_queue.jsonl")

GIVEAWAY_ENTRY_EMOJI = "🎉"
REACTION_ROLE_EMOJI_TO_ROLE_ID: dict[str, int] = {
    "📸": 1505614008437313697,
    "📊": 1505612901401104526,
    "🎮": 1495572658199462018,
    "🥳": 1505612508281442445,
    "🎪": 1505612781796462602,
    "👥": 1505612837089841172,
}

# Runtime caches refreshed by on_ready and ?reload
RUNTIME_AUTOMOD_TERMS: list[str] = []
RUNTIME_NSFW_TERMS: list[str] = []
RUNTIME_APPROVED_INVITE_CODES: set[str] = set()
RUNTIME_APPROVED_BOT_IDS: set[int] = set()
RUNTIME_SETTINGS: dict = {}
RUNTIME_REACTION_ROLE_MESSAGE_IDS: set[int] = set()

unban_task: asyncio.Task | None = None
transcript_cleanup_task: asyncio.Task | None = None
command_tree_synced = False

LEET_TRANSLATION = str.maketrans(
    {
        "0": "o",
        "1": "i",
        "3": "e",
        "4": "a",
        "5": "s",
        "7": "t",
        "8": "b",
        "@": "a",
        "$": "s",
        "!": "i",
        "+": "t",
    }
)


def _pick_payload_value(source: dict, *keys: str) -> object | None:
    lowered = {str(key).lower(): value for key, value in source.items()}
    for key in keys:
        if key in source:
            return source[key]
        lowered_key = key.lower()
        if lowered_key in lowered:
            return lowered[lowered_key]
    return None


def _extract_players(payload: dict | list) -> list[dict]:
    if isinstance(payload, list):
        return [entry for entry in payload if isinstance(entry, dict)]

    if not isinstance(payload, dict):
        return []

    candidate = _pick_payload_value(payload, "players", "data", "result")
    if isinstance(candidate, list):
        return [entry for entry in candidate if isinstance(entry, dict)]

    if isinstance(candidate, dict):
        nested = _pick_payload_value(candidate, "players")
        if isinstance(nested, list):
            return [entry for entry in nested if isinstance(entry, dict)]

    return []


def _extract_queue_count(payload: dict | list) -> int | None:
    if isinstance(payload, list):
        return len(payload)

    if not isinstance(payload, dict):
        return None

    direct_value = _pick_payload_value(
        payload,
        "queue",
        "queueLength",
        "queuedPlayers",
        "queued",
        "count",
    )
    if isinstance(direct_value, int):
        return direct_value
    if isinstance(direct_value, list):
        return len(direct_value)
    if isinstance(direct_value, dict):
        nested_count = _extract_queue_count(direct_value)
        if nested_count is not None:
            return nested_count

    for key, value in payload.items():
        if not isinstance(key, str):
            continue
        key_lower = key.lower()
        if "queue" not in key_lower and "count" not in key_lower:
            continue

        if isinstance(value, int):
            return value
        if isinstance(value, list):
            return len(value)
        if isinstance(value, dict):
            nested_count = _extract_queue_count(value)
            if nested_count is not None:
                return nested_count

    return None


def _format_erlc_player_line(player: dict) -> str:
    # v2 API: Player field is "Username:Id", split to get username
    raw_player = player.get("Player", "")
    username_text = str(raw_player).split(":")[0].strip() if raw_player else "Unknown"
    if not username_text:
        username_text = "Unknown"

    permission_text = str(player.get("Permission", "N/A")).strip() or "N/A"
    team_text = str(player.get("Team", "N/A")).strip() or "N/A"
    callsign_text = str(player.get("Callsign", "N/A")).strip() or "N/A"

    return (
        f"• **{username_text}** — `{permission_text}` | "
        f"Team: **{team_text}** | Callsign: **{callsign_text}**"
    )


def _is_staff_player(player: dict) -> bool:
    permission = str(player.get("Permission", "")).lower()
    return "administrator" in permission or "moderator" in permission or "owner" in permission


async def get_main_server_member(user_id: int) -> discord.Member | None:
    main_guild = bot.get_guild(MAIN_SERVER_GUILD_ID)
    if main_guild is None:
        try:
            main_guild = await bot.fetch_guild(MAIN_SERVER_GUILD_ID)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            return None

    if main_guild is None:
        return None

    member = main_guild.get_member(user_id)
    if member is not None:
        return member

    try:
        return await main_guild.fetch_member(user_id)
    except (discord.NotFound, discord.Forbidden, discord.HTTPException):
        return None


def member_has_any_named_role(member: discord.Member, role_names: set[str]) -> bool:
    def normalize_role_name(value: str) -> str:
        return re.sub(r"[^a-z0-9]+", "", value.lower())

    normalized_allowed = {normalize_role_name(name) for name in role_names}
    member_role_names = {normalize_role_name(role.name) for role in member.roles}
    return any(name in member_role_names for name in normalized_allowed)


def role_name_text(role_id: int, guild: discord.Guild | None = None) -> str:
    lookup_guilds: list[discord.Guild] = []
    if guild is not None:
        lookup_guilds.append(guild)

    main_guild = bot.get_guild(MAIN_SERVER_GUILD_ID)
    if main_guild is not None and (guild is None or main_guild.id != guild.id):
        lookup_guilds.append(main_guild)

    for lookup_guild in lookup_guilds:
        role = lookup_guild.get_role(role_id)
        if role is not None:
            return role.name

    return f"Role {role_id}"


def main_server_role_required(role_id: int):
    async def predicate(ctx: commands.Context) -> bool:
        member = await get_main_server_member(ctx.author.id)
        if member is None:
            raise commands.CheckFailure("Main server is not available.")

        if any(role.id == role_id for role in member.roles):
            return True

        raise commands.MissingRole(role_id)

    return commands.check(predicate)


async def _fetch_erlc_json(endpoint: str, params: dict | None = None) -> tuple[dict | list | None, str | None]:
    if not ERLC_API_KEY:
        return None, "ERLC API key is missing."

    url = f"{ERLC_API_BASE_URL}{endpoint}"
    timeout = aiohttp.ClientTimeout(total=12)
    headers = {
        "server-key": ERLC_API_KEY,
        "User-Agent": "SLCRP-Bot/1.0",
    }

    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url, headers=headers, params=params or {}) as response:
                raw_text = await response.text()
                if response.status != 200:
                    snippet = raw_text.strip().replace("\n", " ")[:180]
                    return None, f"ERLC API returned {response.status}. {snippet}" if snippet else f"ERLC API returned {response.status}."
                try:
                    return json.loads(raw_text), None
                except json.JSONDecodeError:
                    return None, "ERLC API returned invalid JSON."
    except asyncio.TimeoutError:
        return None, "ERLC API request timed out."
    except aiohttp.ClientError as api_error:
        return None, f"ERLC API request failed: {api_error}"


def load_saved_roles() -> dict:
    if not os.path.exists(ROLE_SAVE_PATH):
        return {}

    try:
        with open(ROLE_SAVE_PATH, "r", encoding="utf-8") as file:
            return json.load(file)
    except (json.JSONDecodeError, OSError):
        return {}


def save_saved_roles(data: dict) -> None:
    os.makedirs(os.path.dirname(ROLE_SAVE_PATH), exist_ok=True)
    temp_path = ROLE_SAVE_PATH + ".tmp"
    with open(temp_path, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=2)
    os.replace(temp_path, ROLE_SAVE_PATH)


def load_warning_data() -> dict:
    if not os.path.exists(WARNINGS_PATH):
        return {"next_case_id": 1, "warnings": []}

    try:
        with open(WARNINGS_PATH, "r", encoding="utf-8") as file:
            data = json.load(file)
            if "next_case_id" not in data:
                data["next_case_id"] = 1
            if "warnings" not in data:
                data["warnings"] = []
            return data
    except (json.JSONDecodeError, OSError):
        return {"next_case_id": 1, "warnings": []}


def save_warning_data(data: dict) -> None:
    os.makedirs(os.path.dirname(WARNINGS_PATH), exist_ok=True)
    temp_path = WARNINGS_PATH + ".tmp"
    with open(temp_path, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=2)
    os.replace(temp_path, WARNINGS_PATH)


def load_sanction_data() -> dict:
    if not os.path.exists(SANCTIONS_PATH):
        return {"temp_bans": []}

    try:
        with open(SANCTIONS_PATH, "r", encoding="utf-8") as file:
            data = json.load(file)
            if "temp_bans" not in data:
                data["temp_bans"] = []
            return data
    except (json.JSONDecodeError, OSError):
        return {"temp_bans": []}


def save_sanction_data(data: dict) -> None:
    os.makedirs(os.path.dirname(SANCTIONS_PATH), exist_ok=True)
    temp_path = SANCTIONS_PATH + ".tmp"
    with open(temp_path, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=2)
    os.replace(temp_path, SANCTIONS_PATH)


def ensure_levels_file() -> None:
    if os.path.exists(LEVELS_PATH):
        return

    os.makedirs(os.path.dirname(LEVELS_PATH), exist_ok=True)
    with open(LEVELS_PATH, "w", encoding="utf-8") as file:
        json.dump({"users": {}}, file, indent=2)


def load_levels_data() -> dict:
    ensure_levels_file()
    try:
        with open(LEVELS_PATH, "r", encoding="utf-8") as file:
            data = json.load(file)
    except (OSError, json.JSONDecodeError):
        return {"users": {}}

    if not isinstance(data, dict):
        return {"users": {}}
    if "users" not in data or not isinstance(data.get("users"), dict):
        data["users"] = {}
    return data


def save_levels_data(data: dict) -> None:
    os.makedirs(os.path.dirname(LEVELS_PATH), exist_ok=True)
    temp_path = LEVELS_PATH + ".tmp"
    with open(temp_path, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=2)
    os.replace(temp_path, LEVELS_PATH)


def get_levels_user_record(levels_data: dict, user_id: int) -> dict:
    users = levels_data.setdefault("users", {})
    record = users.setdefault(str(user_id), {})
    record.setdefault("xp", 0)
    record.setdefault("level", 0)
    record.setdefault("last_claim", None)
    return record


def xp_needed_for_next_level(level: int) -> int:
    # Harder progression: still doubles each level, but starts higher.
    base_xp = 500
    return base_xp * (2 ** max(level, 0))


def apply_xp_to_level_record(record: dict, gained_xp: int) -> int:
    current_xp = int(record.get("xp", 0))
    current_level = int(record.get("level", 0))
    current_xp += max(gained_xp, 0)

    leveled_up = 0
    while True:
        needed = xp_needed_for_next_level(current_level)
        if current_xp < needed:
            break
        current_xp -= needed
        current_level += 1
        leveled_up += 1

    record["xp"] = current_xp
    record["level"] = current_level
    return leveled_up


def parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def format_duration_short(duration: timedelta) -> str:
    total_seconds = int(max(duration.total_seconds(), 0))
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours}h {minutes}m {seconds}s"


def parse_duration_token(value: str) -> int | None:
    match = re.fullmatch(r"\s*(\d+)\s*([smhdSMHD])\s*", value or "")
    if not match:
        return None

    amount = int(match.group(1))
    unit = match.group(2).lower()
    if amount <= 0:
        return None

    multiplier = {
        "s": 1,
        "m": 60,
        "h": 3600,
        "d": 86400,
    }.get(unit)
    if multiplier is None:
        return None
    return amount * multiplier


def ensure_reaction_role_messages_file() -> None:
    if os.path.exists(REACTION_ROLE_MESSAGES_PATH):
        return

    os.makedirs(os.path.dirname(REACTION_ROLE_MESSAGES_PATH), exist_ok=True)
    with open(REACTION_ROLE_MESSAGES_PATH, "w", encoding="utf-8") as file:
        json.dump({"message_ids": []}, file, indent=2)


def load_reaction_role_message_ids() -> set[int]:
    ensure_reaction_role_messages_file()
    try:
        with open(REACTION_ROLE_MESSAGES_PATH, "r", encoding="utf-8") as file:
            raw_data = json.load(file)
    except (OSError, json.JSONDecodeError):
        return set()

    if isinstance(raw_data, dict):
        raw_ids = raw_data.get("message_ids", [])
    elif isinstance(raw_data, list):
        raw_ids = raw_data
    else:
        raw_ids = []

    parsed_ids: set[int] = set()
    for entry in raw_ids:
        try:
            parsed_ids.add(int(entry))
        except (TypeError, ValueError):
            continue
    return parsed_ids


def save_reaction_role_message_ids(message_ids: set[int]) -> None:
    os.makedirs(os.path.dirname(REACTION_ROLE_MESSAGES_PATH), exist_ok=True)
    with open(REACTION_ROLE_MESSAGES_PATH, "w", encoding="utf-8") as file:
        json.dump({"message_ids": sorted(message_ids)}, file, indent=2)


def refresh_runtime_reaction_role_message_ids() -> int:
    global RUNTIME_REACTION_ROLE_MESSAGE_IDS
    RUNTIME_REACTION_ROLE_MESSAGE_IDS = load_reaction_role_message_ids()
    return len(RUNTIME_REACTION_ROLE_MESSAGE_IDS)


def get_sorted_level_entries(levels_data: dict) -> list[tuple[int, int, int]]:
    entries: list[tuple[int, int, int]] = []
    for user_id_text, record in levels_data.get("users", {}).items():
        try:
            user_id = int(user_id_text)
        except (TypeError, ValueError):
            continue
        level = int(record.get("level", 0))
        xp = int(record.get("xp", 0))
        entries.append((user_id, level, xp))

    entries.sort(key=lambda item: (item[1], item[2], -item[0]), reverse=True)
    return entries


def filter_entries_to_main_server_members(
    entries: list[tuple[int, int, int]],
    main_guild: discord.Guild | None,
) -> list[tuple[int, int, int]]:
    if main_guild is None:
        return []

    member_ids = {member.id for member in main_guild.members}
    return [entry for entry in entries if entry[0] in member_ids]


def build_levels_leaderboard_embed(
    *,
    entries: list[tuple[int, int, int]],
    page_index: int,
    page_size: int,
) -> discord.Embed:
    total_entries = len(entries)
    total_pages = max((total_entries + page_size - 1) // page_size, 1)
    page_index = max(0, min(page_index, total_pages - 1))
    start = page_index * page_size
    end = start + page_size
    page_entries = entries[start:end]

    lines: list[str] = []
    for offset, (user_id, level, xp) in enumerate(page_entries, start=start + 1):
        lines.append(f"`#{offset}` <@{user_id}> - Level **{level}** | XP **{xp}**")

    description = "\n".join(lines) if lines else "No leaderboard data yet."
    embed = discord.Embed(
        title="SLCRP | Salt Lake City RP | Levels Leaderboard",
        description=description,
        color=discord.Color.blue(),
    )
    embed.set_footer(text=f"Page {page_index + 1}/{total_pages} • Total Users: {total_entries}")
    return embed


class LevelsLeaderboardView(discord.ui.View):
    def __init__(self, requester_id: int, entries: list[tuple[int, int, int]]) -> None:
        super().__init__(timeout=180)
        self.requester_id = requester_id
        self.entries = entries
        self.page_index = 0
        self.page_size = 20
        self._sync_buttons()

    def _sync_buttons(self) -> None:
        total_pages = max((len(self.entries) + self.page_size - 1) // self.page_size, 1)
        self.previous_button.disabled = self.page_index <= 0
        self.next_button.disabled = self.page_index >= total_pages - 1

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.requester_id:
            await interaction.response.send_message("Only the command runner can change leaderboard pages.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Previous", style=discord.ButtonStyle.secondary)
    async def previous_button(self, button: discord.ui.Button, interaction: discord.Interaction) -> None:
        self.page_index = max(self.page_index - 1, 0)
        self._sync_buttons()
        embed = build_levels_leaderboard_embed(entries=self.entries, page_index=self.page_index, page_size=self.page_size)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Next", style=discord.ButtonStyle.secondary)
    async def next_button(self, button: discord.ui.Button, interaction: discord.Interaction) -> None:
        total_pages = max((len(self.entries) + self.page_size - 1) // self.page_size, 1)
        self.page_index = min(self.page_index + 1, total_pages - 1)
        self._sync_buttons()
        embed = build_levels_leaderboard_embed(entries=self.entries, page_index=self.page_index, page_size=self.page_size)
        await interaction.response.edit_message(embed=embed, view=self)


def add_temp_ban_record(guild_id: int, user_id: int, case_id: int, unban_at: datetime, reason: str) -> None:
    data = load_sanction_data()
    data["temp_bans"].append(
        {
            "guild_id": guild_id,
            "user_id": user_id,
            "case_id": case_id,
            "reason": reason,
            "unban_at": unban_at.isoformat(),
            "active": True,
        }
    )
    save_sanction_data(data)


def load_temp_vc_data() -> dict:
    if not os.path.exists(TEMP_VC_DATA_PATH):
        return {"guilds": {}}

    try:
        with open(TEMP_VC_DATA_PATH, "r", encoding="utf-8") as file:
            data = json.load(file)
            if "guilds" not in data:
                data["guilds"] = {}
            return data
    except (json.JSONDecodeError, OSError):
        return {"guilds": {}}


def save_temp_vc_data(data: dict) -> None:
    os.makedirs(os.path.dirname(TEMP_VC_DATA_PATH), exist_ok=True)
    temp_path = TEMP_VC_DATA_PATH + ".tmp"
    with open(temp_path, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=2)
    os.replace(temp_path, TEMP_VC_DATA_PATH)


def get_temp_vc_entry(guild_id: int, owner_id: int) -> dict | None:
    data = load_temp_vc_data()
    guild_data = data.get("guilds", {}).get(str(guild_id), {})
    owners = guild_data.get("owners", {})
    return owners.get(str(owner_id))


def set_temp_vc_entry(
    guild_id: int,
    owner_id: int,
    voice_channel_id: int,
    text_channel_id: int,
    category_id: int,
) -> None:
    data = load_temp_vc_data()
    guild_data = data.setdefault("guilds", {}).setdefault(str(guild_id), {})
    owners = guild_data.setdefault("owners", {})
    owners[str(owner_id)] = {
        "voice_channel_id": voice_channel_id,
        "text_channel_id": text_channel_id,
        "category_id": category_id,
    }
    save_temp_vc_data(data)


def remove_temp_vc_entry(guild_id: int, owner_id: int) -> None:
    data = load_temp_vc_data()
    guild_data = data.get("guilds", {}).get(str(guild_id), {})
    owners = guild_data.get("owners", {})
    if str(owner_id) in owners:
        owners.pop(str(owner_id), None)
        if not owners:
            guild_data.pop("owners", None)
        if not guild_data:
            data.get("guilds", {}).pop(str(guild_id), None)
        save_temp_vc_data(data)


def find_temp_vc_owner_by_voice_channel(guild_id: int, voice_channel_id: int) -> int | None:
    data = load_temp_vc_data()
    guild_data = data.get("guilds", {}).get(str(guild_id), {})
    owners = guild_data.get("owners", {})
    for owner_id, entry in owners.items():
        if int(entry.get("voice_channel_id", 0)) == voice_channel_id:
            return int(owner_id)
    return None


def clean_channel_name(value: str, fallback: str) -> str:
    cleaned = " ".join(value.split()).strip()
    return (cleaned or fallback)[:90]


def clean_text_channel_name(value: str) -> str:
    slug = re.sub(r"[^a-z0-9-]", "-", value.lower())
    slug = re.sub(r"-+", "-", slug).strip("-")
    if not slug:
        slug = "user"
    return f"{slug[:70]}-vc-settings"


def build_vc_settings_embed(member: discord.Member) -> discord.Embed:
    embed = discord.Embed(
        title="Welcome to your VCs settings",
        description=(
            "You can use 2 commands and 1 booster only command!\n"
            f"{PREFIX}out <@user> - removes the targeted user from your vc\n"
            f"{PREFIX}lock / {PREFIX}unlock - Locks the VCs so no one else can join / unlocks the VC\n"
            f"{PREFIX}soundboard on/off - turns the soundboards on/off in your VC - Must be <@&{BOOSTER_ROLE_ID}>"
        ),
        color=discord.Color.blue(),
    )
    if member.guild.icon:
        embed.set_thumbnail(url=member.guild.icon.url)
    embed.set_footer(text="SLCRP | VC Settings")
    return embed


async def delete_temp_vc_resources(guild: discord.Guild, owner_id: int) -> None:
    entry = get_temp_vc_entry(guild.id, owner_id)
    if entry is None:
        return

    voice_channel = guild.get_channel(int(entry.get("voice_channel_id", 0)))
    text_channel = guild.get_channel(int(entry.get("text_channel_id", 0)))

    if isinstance(text_channel, discord.TextChannel):
        try:
            await text_channel.delete(reason="Temporary VC cleaned up")
        except (discord.Forbidden, discord.HTTPException):
            pass

    if isinstance(voice_channel, discord.VoiceChannel):
        try:
            await voice_channel.delete(reason="Temporary VC cleaned up")
        except (discord.Forbidden, discord.HTTPException):
            pass

    remove_temp_vc_entry(guild.id, owner_id)


async def get_temp_vc_channels(
    guild: discord.Guild,
    owner_id: int,
) -> tuple[dict, discord.VoiceChannel, discord.TextChannel] | None:
    entry = get_temp_vc_entry(guild.id, owner_id)
    if entry is None:
        return None

    voice_channel = guild.get_channel(int(entry.get("voice_channel_id", 0)))
    text_channel = guild.get_channel(int(entry.get("text_channel_id", 0)))
    if not isinstance(voice_channel, discord.VoiceChannel) or not isinstance(text_channel, discord.TextChannel):
        remove_temp_vc_entry(guild.id, owner_id)
        return None

    return entry, voice_channel, text_channel


async def create_or_get_temp_vc(member: discord.Member, trigger_channel: discord.VoiceChannel) -> discord.VoiceChannel | None:
    existing = await get_temp_vc_channels(member.guild, member.id)
    if existing is not None:
        _, voice_channel, _ = existing
        try:
            await member.move_to(voice_channel, reason="Moved to existing temporary VC")
        except (discord.Forbidden, discord.HTTPException):
            return None
        return voice_channel

    category = trigger_channel.category
    if category is None:
        return None

    everyone_role = member.guild.default_role
    bot_member = member.guild.me
    overwrites = {
        everyone_role: discord.PermissionOverwrite(connect=None, view_channel=None),
        member: discord.PermissionOverwrite(view_channel=True, connect=True, speak=True, use_soundboard=True),
    }
    if bot_member is not None:
        overwrites[bot_member] = discord.PermissionOverwrite(
            view_channel=True,
            connect=True,
            speak=True,
            manage_channels=True,
            manage_permissions=True,
            move_members=True,
        )

    voice_name = clean_channel_name(f"{member.display_name} VCs", "User VCs")
    text_name = clean_text_channel_name(f"{member.display_name} VC settings")

    voice_channel = await member.guild.create_voice_channel(
        name=voice_name,
        category=category,
        overwrites=overwrites,
        reason=f"Temporary VC created for {member}",
    )
    text_channel = await member.guild.create_text_channel(
        name=text_name,
        category=category,
        overwrites={
            everyone_role: discord.PermissionOverwrite(view_channel=False),
            member: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
            **({bot_member: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True)} if bot_member is not None else {}),
        },
        reason=f"Temporary VC settings channel created for {member}",
    )

    if category.channels:
        bottom_position = max(channel.position for channel in category.channels)
        try:
            await voice_channel.edit(position=bottom_position, reason="Move temporary VC to bottom of category")
            await text_channel.edit(position=bottom_position, reason="Move VC settings channel to bottom of category")
        except (discord.Forbidden, discord.HTTPException):
            pass

    set_temp_vc_entry(member.guild.id, member.id, voice_channel.id, text_channel.id, category.id)

    await text_channel.send(content=member.mention, embed=build_vc_settings_embed(member))
    try:
        await member.move_to(voice_channel, reason="Moved to temporary VC")
    except (discord.Forbidden, discord.HTTPException):
        pass
    return voice_channel


def ensure_automod_blacklist_file() -> None:
    if os.path.exists(AUTOMOD_BLACKLIST_PATH):
        return

    os.makedirs(os.path.dirname(AUTOMOD_BLACKLIST_PATH), exist_ok=True)
    with open(AUTOMOD_BLACKLIST_PATH, "w", encoding="utf-8") as file:
        file.write(
            "# One trigger per line. Lines starting with # are ignored.\n"
            "# You can add single words or phrases.\n"
            "examplebadword\n"
        )


def load_automod_blacklist_terms() -> list[str]:
    ensure_automod_blacklist_file()
    terms: list[str] = []

    try:
        with open(AUTOMOD_BLACKLIST_PATH, "r", encoding="utf-8") as file:
            for line in file:
                term = line.strip().lower()
                if not term or term.startswith("#"):
                    continue
                terms.append(term)
    except OSError:
        return []

    return terms


def ensure_automod_nsfw_blacklist_file() -> None:
    if os.path.exists(AUTOMOD_NSFW_BLACKLIST_PATH):
        return

    os.makedirs(os.path.dirname(AUTOMOD_NSFW_BLACKLIST_PATH), exist_ok=True)
    with open(AUTOMOD_NSFW_BLACKLIST_PATH, "w", encoding="utf-8") as file:
        file.write(
            "# NSFW / Offensive auto-ban blacklist. One term per line. # = comment.\n"
            "# Users who trigger this list are automatically banned from all servers.\n"
            "examplensfwword\n"
        )


def ensure_approved_invites_file() -> None:
    if os.path.exists(APPROVED_INVITES_PATH):
        return

    os.makedirs(os.path.dirname(APPROVED_INVITES_PATH), exist_ok=True)
    with open(APPROVED_INVITES_PATH, "w", encoding="utf-8") as file:
        json.dump({"invite_codes": []}, file, indent=2)


def normalize_invite_code(invite_code: str) -> str:
    return invite_code.strip().lower()


def extract_discord_invite_codes(text: str) -> list[str]:
    return [normalize_invite_code(code) for code in DISCORD_INVITE_CODE_REGEX.findall(text)]


def load_approved_invite_codes() -> set[str]:
    ensure_approved_invites_file()

    try:
        with open(APPROVED_INVITES_PATH, "r", encoding="utf-8") as file:
            raw_data = json.load(file)
    except (OSError, json.JSONDecodeError):
        return set()

    if isinstance(raw_data, dict):
        raw_codes = raw_data.get("invite_codes")
        if raw_codes is None:
            raw_codes = raw_data.get("approved_invites", [])
    elif isinstance(raw_data, list):
        raw_codes = raw_data
    else:
        raw_codes = []

    normalized_codes: set[str] = set()
    for raw_entry in raw_codes:
        if not isinstance(raw_entry, str):
            continue

        stripped = raw_entry.strip()
        if not stripped:
            continue

        extracted = extract_discord_invite_codes(stripped)
        if extracted:
            normalized_codes.update(extracted)
        else:
            normalized_codes.add(normalize_invite_code(stripped))

    return normalized_codes


def ensure_approved_bots_file() -> None:
    if os.path.exists(APPROVED_BOTS_PATH):
        return

    os.makedirs(os.path.dirname(APPROVED_BOTS_PATH), exist_ok=True)
    with open(APPROVED_BOTS_PATH, "w", encoding="utf-8") as file:
        json.dump({"bot_ids": []}, file, indent=2)


def load_approved_bot_ids() -> set[int]:
    ensure_approved_bots_file()

    try:
        with open(APPROVED_BOTS_PATH, "r", encoding="utf-8") as file:
            raw_data = json.load(file)
    except (OSError, json.JSONDecodeError):
        return set()

    if isinstance(raw_data, dict):
        raw_ids = raw_data.get("bot_ids")
        if raw_ids is None:
            raw_ids = raw_data.get("approved_bots", [])
    elif isinstance(raw_data, list):
        raw_ids = raw_data
    else:
        raw_ids = []

    approved_ids: set[int] = set()
    for raw_entry in raw_ids:
        try:
            approved_ids.add(int(raw_entry))
        except (TypeError, ValueError):
            continue

    return approved_ids


def build_default_runtime_settings() -> dict:
    return {
        "support_embed": {
            "title": "Support Channel",
            "description": "The support channel is right here: https://discord.com/channels/1397084580816621618/1493095132852129873",
        },
        "ticket_panel": {
            "rules_title": "SLCRP | Salt Lake City RP - Ticket System",
            "rules_description": "Kindly make sure to read our complete Ticket Terms of Service below before creating a ticket.",
            "footer": "SLCRP | Salt Lake City RP Support System",
            "select_title": "Open a Ticket",
            "select_description": "Select the type of ticket you would like to open from the menu below.",
        },
        "ticket_rules": dict(TICKET_RULES_REWORDED),
        "id_overrides": {
            "reload_command_role_id": RELOAD_COMMAND_ROLE_ID,
            "ticket_rules_channel_id": TICKET_RULES_CHANNEL_ID,
            "rp_channel_id": RP_CHANNEL_ID,
        },
    }


def ensure_runtime_settings_file() -> None:
    if os.path.exists(RUNTIME_SETTINGS_PATH):
        return

    os.makedirs(os.path.dirname(RUNTIME_SETTINGS_PATH), exist_ok=True)
    with open(RUNTIME_SETTINGS_PATH, "w", encoding="utf-8") as file:
        json.dump(build_default_runtime_settings(), file, indent=2)


def load_runtime_settings() -> dict:
    ensure_runtime_settings_file()

    default_settings = build_default_runtime_settings()
    try:
        with open(RUNTIME_SETTINGS_PATH, "r", encoding="utf-8") as file:
            raw = json.load(file)
    except (OSError, json.JSONDecodeError):
        return default_settings

    if not isinstance(raw, dict):
        return default_settings

    support_raw = raw.get("support_embed", {})
    ticket_panel_raw = raw.get("ticket_panel", {})
    ticket_rules_raw = raw.get("ticket_rules", {})

    support_embed = {
        "title": str(support_raw.get("title", default_settings["support_embed"]["title"])),
        "description": str(support_raw.get("description", default_settings["support_embed"]["description"])),
    } if isinstance(support_raw, dict) else dict(default_settings["support_embed"])

    ticket_panel = {
        "rules_title": str(ticket_panel_raw.get("rules_title", default_settings["ticket_panel"]["rules_title"])),
        "rules_description": str(ticket_panel_raw.get("rules_description", default_settings["ticket_panel"]["rules_description"])),
        "footer": str(ticket_panel_raw.get("footer", default_settings["ticket_panel"]["footer"])),
        "select_title": str(ticket_panel_raw.get("select_title", default_settings["ticket_panel"]["select_title"])),
        "select_description": str(ticket_panel_raw.get("select_description", default_settings["ticket_panel"]["select_description"])),
    } if isinstance(ticket_panel_raw, dict) else dict(default_settings["ticket_panel"])

    ticket_rules: dict[str, str] = {}
    if isinstance(ticket_rules_raw, dict):
        for key, value in ticket_rules_raw.items():
            key_text = str(key).strip()
            value_text = str(value).strip()
            if key_text and value_text:
                ticket_rules[key_text] = value_text

    if not ticket_rules:
        ticket_rules = dict(default_settings["ticket_rules"])

    default_id_overrides = default_settings["id_overrides"]
    id_overrides_raw = raw.get("id_overrides", {})
    id_overrides: dict[str, int] = {}
    if isinstance(id_overrides_raw, dict):
        for key, default_value in default_id_overrides.items():
            candidate = id_overrides_raw.get(key, default_value)
            try:
                id_overrides[key] = int(candidate)
            except (TypeError, ValueError):
                id_overrides[key] = int(default_value)
    else:
        id_overrides = dict(default_id_overrides)

    return {
        "support_embed": support_embed,
        "ticket_panel": ticket_panel,
        "ticket_rules": ticket_rules,
        "id_overrides": id_overrides,
    }


def save_runtime_settings(settings: dict) -> None:
    os.makedirs(os.path.dirname(RUNTIME_SETTINGS_PATH), exist_ok=True)
    temp_path = RUNTIME_SETTINGS_PATH + ".tmp"
    with open(temp_path, "w", encoding="utf-8") as file:
        json.dump(settings, file, indent=2)
    os.replace(temp_path, RUNTIME_SETTINGS_PATH)


def refresh_runtime_settings() -> int:
    global RUNTIME_SETTINGS
    RUNTIME_SETTINGS = load_runtime_settings()
    ticket_rules = RUNTIME_SETTINGS.get("ticket_rules", {}) if isinstance(RUNTIME_SETTINGS, dict) else {}
    return len(ticket_rules) if isinstance(ticket_rules, dict) else 0


def get_runtime_id(setting_key: str, fallback: int) -> int:
    if not isinstance(RUNTIME_SETTINGS, dict):
        return fallback
    overrides = RUNTIME_SETTINGS.get("id_overrides", {})
    if not isinstance(overrides, dict):
        return fallback
    raw = overrides.get(setting_key, fallback)
    try:
        return int(raw)
    except (TypeError, ValueError):
        return fallback


def get_reload_command_role_id() -> int:
    return get_runtime_id("reload_command_role_id", RELOAD_COMMAND_ROLE_ID)


def get_ticket_rules_channel_id() -> int:
    return get_runtime_id("ticket_rules_channel_id", TICKET_RULES_CHANNEL_ID)


def get_rp_channel_id() -> int:
    return get_runtime_id("rp_channel_id", RP_CHANNEL_ID)


def load_automod_nsfw_blacklist_terms() -> list[str]:
    ensure_automod_nsfw_blacklist_file()
    terms: list[str] = []

    try:
        with open(AUTOMOD_NSFW_BLACKLIST_PATH, "r", encoding="utf-8") as file:
            for line in file:
                term = line.strip().lower()
                if not term or term.startswith("#"):
                    continue
                terms.append(term)
    except OSError:
        return []

    return terms


def refresh_runtime_automod_terms() -> int:
    global RUNTIME_AUTOMOD_TERMS
    ensure_automod_blacklist_file()
    RUNTIME_AUTOMOD_TERMS = load_automod_blacklist_terms()
    return len(RUNTIME_AUTOMOD_TERMS)


def refresh_runtime_nsfw_terms() -> int:
    global RUNTIME_NSFW_TERMS
    ensure_automod_nsfw_blacklist_file()
    RUNTIME_NSFW_TERMS = load_automod_nsfw_blacklist_terms()
    return len(RUNTIME_NSFW_TERMS)


def refresh_runtime_approved_invites() -> int:
    global RUNTIME_APPROVED_INVITE_CODES
    ensure_approved_invites_file()
    RUNTIME_APPROVED_INVITE_CODES = load_approved_invite_codes()
    return len(RUNTIME_APPROVED_INVITE_CODES)


def refresh_runtime_approved_bots() -> int:
    global RUNTIME_APPROVED_BOT_IDS
    ensure_approved_bots_file()
    RUNTIME_APPROVED_BOT_IDS = load_approved_bot_ids()
    return len(RUNTIME_APPROVED_BOT_IDS)


def get_blacklist_file_stats(file_path: str) -> tuple[int, int]:
    """Return (raw_line_count, ignored_line_count) for blacklist-style files."""
    raw_line_count = 0
    ignored_line_count = 0

    try:
        with open(file_path, "r", encoding="utf-8") as file:
            for raw_line in file:
                raw_line_count += 1
                term = raw_line.strip()
                if not term or term.startswith("#"):
                    ignored_line_count += 1
    except OSError:
        return (0, 0)

    return (raw_line_count, ignored_line_count)


def refresh_all_runtime_caches() -> None:
    refresh_runtime_automod_terms()
    refresh_runtime_nsfw_terms()
    refresh_runtime_approved_invites()
    refresh_runtime_approved_bots()
    refresh_runtime_settings()
    refresh_runtime_reaction_role_message_ids()


def normalize_text_for_detection(text: str) -> str:
    normalized = text.lower().translate(LEET_TRANSLATION)
    return re.sub(r"[^a-z0-9]", "", normalized)


def tokenize_text_for_detection(text: str) -> list[str]:
    normalized = text.lower().translate(LEET_TRANSLATION)
    return [token for token in re.split(r"[^a-z0-9]+", normalized) if token]


def collapse_repeated_characters(text: str) -> str:
    return re.sub(r"(.)\1+", r"\1", text)


def find_blacklisted_term(message_content: str, terms: list[str]) -> str | None:
    content = message_content.lower()
    detection_tokens = tokenize_text_for_detection(message_content)
    collapsed_tokens = [collapse_repeated_characters(token) for token in detection_tokens]

    for term in terms:
        raw_term = term.strip().lower()
        normalized_term = normalize_text_for_detection(raw_term)
        collapsed_term = collapse_repeated_characters(normalized_term)

        if not raw_term:
            continue

        # Raw substring matching is required for emoji and other symbolic terms.
        # Plain alphanumeric terms still use stricter checks below to avoid false positives.
        if not re.fullmatch(r"[a-z0-9 ]+", raw_term) and raw_term in content:
            return term

        if " " in raw_term:
            phrase_pattern = rf"(?<![a-z0-9]){re.escape(raw_term)}(?![a-z0-9])"
            if re.search(phrase_pattern, content):
                return term
            continue

        # Whole-word check for plain alphanumeric terms.
        if re.fullmatch(r"[a-z0-9]+", raw_term):
            pattern = rf"(?<![a-z0-9]){re.escape(raw_term)}(?![a-z0-9])"
            if re.search(pattern, content):
                return term

        if normalized_term and normalized_term in detection_tokens:
            return term

        # Catch stretched variants like fuuuuuck / shiiiit without matching inside larger words.
        if collapsed_term and collapsed_term in collapsed_tokens:
            return term

        # Detect separators between letters, e.g. f.u.c.k / f u c k.
        if normalized_term and len(normalized_term) >= 3:
            split_pattern = rf"(?<![a-z0-9]){''.join(re.escape(char) + r'[\W_]*' for char in normalized_term)}(?![a-z0-9])"
            if re.search(split_pattern, content):
                return term

    return None


async def process_pending_unbans() -> None:
    await bot.wait_until_ready()
    while not bot.is_closed():
        data = load_sanction_data()
        now = datetime.now(timezone.utc)
        changed = False

        for entry in data.get("temp_bans", []):
            if not entry.get("active", True):
                continue

            unban_at_raw = entry.get("unban_at")
            try:
                unban_at = datetime.fromisoformat(unban_at_raw) if unban_at_raw else now
            except ValueError:
                unban_at = now

            if unban_at > now:
                continue

            guild = bot.get_guild(int(entry.get("guild_id", 0)))
            if guild is None:
                continue

            user_id = int(entry.get("user_id", 0))
            try:
                user = await bot.fetch_user(user_id)
                await guild.unban(user, reason="Temporary warning ban expired")
            except discord.NotFound:
                pass
            except discord.Forbidden:
                continue
            except discord.HTTPException:
                continue

            entry["active"] = False
            entry["unbanned_at"] = now.isoformat()
            changed = True

        if changed:
            save_sanction_data(data)

        await asyncio.sleep(UNBAN_CHECK_INTERVAL_SECONDS)


def parse_user_id(input_value: str) -> int | None:
    mention_match = re.fullmatch(r"<@!?(\d+)>", input_value)
    if mention_match:
        return int(mention_match.group(1))
    if input_value.isdigit():
        return int(input_value)
    return None


def count_active_warnings(warning_data: dict, guild_id: int, user_id: int, now: datetime) -> int:
    active_warning_count = 0
    for entry in warning_data.get("warnings", []):
        if int(entry.get("guild_id", 0)) != guild_id:
            continue
        if int(entry.get("user_id", 0)) != user_id:
            continue
        if entry.get("voided", False):
            continue

        expires_at_raw = entry.get("expires_at")
        try:
            expires_at = datetime.fromisoformat(expires_at_raw) if expires_at_raw else now
        except ValueError:
            expires_at = now

        if expires_at > now:
            active_warning_count += 1

    return active_warning_count


async def delete_recent_user_messages(guild: discord.Guild, user_id: int, days: int = 7) -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    deleted_count = 0

    for channel in guild.text_channels:
        permissions = channel.permissions_for(guild.me) if guild.me else None
        if permissions is None:
            continue
        if not permissions.read_message_history or not permissions.manage_messages:
            continue

        try:
            async for msg in channel.history(limit=None, after=cutoff):
                if msg.author.id != user_id:
                    continue
                try:
                    await msg.delete()
                    deleted_count += 1
                except (discord.Forbidden, discord.HTTPException):
                    continue
        except (discord.Forbidden, discord.HTTPException):
            continue

    return deleted_count


async def get_ban_appeal_invite_url() -> str | None:
    appeal_guild = bot.get_guild(BAN_APPEAL_GUILD_ID)
    if appeal_guild is None:
        return None

    try:
        invites = await appeal_guild.invites()
        for invite in invites:
            if invite.max_age == 0 and invite.max_uses == 0:
                return invite.url
    except (discord.Forbidden, discord.HTTPException):
        pass

    for channel in appeal_guild.text_channels:
        permissions = channel.permissions_for(appeal_guild.me) if appeal_guild.me else None
        if permissions is None or not permissions.create_instant_invite:
            continue

        try:
            invite = await channel.create_invite(
                max_age=0,
                max_uses=0,
                reason="Ban appeal invite for banned user",
            )
            return invite.url
        except (discord.Forbidden, discord.HTTPException):
            continue

    return None


async def send_main_bot_ban_appeal_dm(
    user: discord.abc.User,
    action_name: str,
    reason: str,
    moderator_name: str,
    invite_url: str | None,
) -> bool:
    embed = discord.Embed(
        title="SLCRP | Ban Notice",
        description=(
            f"You have been {action_name} by staff. "
            "If you want to appeal, join the ban appeal server below."
        ),
        color=discord.Color.red(),
        timestamp=datetime.now(timezone.utc),
    )
    embed.add_field(name="Reason", value=reason, inline=False)
    embed.add_field(name="Actioned By", value=moderator_name, inline=False)
    if invite_url:
        embed.add_field(name="Ban Appeal Server", value=invite_url, inline=False)
    else:
        embed.add_field(
            name="Ban Appeal Server",
            value="Invite unavailable right now. Contact staff if you need an appeal link.",
            inline=False,
        )

    try:
        await user.send(embed=embed)
        return True
    except (discord.Forbidden, discord.HTTPException):
        return False


def queue_modmail_ban_appeal_dm(
    user_id: int,
    action_name: str,
    reason: str,
    moderator_name: str,
    invite_url: str | None,
) -> bool:
    payload = {
        "user_id": user_id,
        "action": action_name,
        "reason": reason,
        "moderator": moderator_name,
        "appeal_invite_url": invite_url,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    try:
        os.makedirs(os.path.dirname(BAN_APPEAL_DM_QUEUE_PATH), exist_ok=True)
        with open(BAN_APPEAL_DM_QUEUE_PATH, "a", encoding="utf-8") as file:
            file.write(json.dumps(payload) + "\n")
        return True
    except OSError:
        return False


def get_all_server_ban_guilds(include_ban_appeal: bool = False) -> list[discord.Guild]:
    if include_ban_appeal:
        return list(bot.guilds)
    return [guild for guild in bot.guilds if guild.id != BAN_APPEAL_GUILD_ID]


TICKET_TYPES = [
    "General Support",
    "Production",
    "Media",
    "Report Member",
    "Department",
    "Report Department",
    "Blacklist Server",
    "Giveaways",
    "False Punishments",
    "IT Support",
    "Ownership",
]

TICKET_TYPE_ROUTING: dict[str, dict[str, object]] = {
    "General Support": {
        "category_id": 1494811541093224558,
        "ping_text": f"<@&1493343282820812872> | {{user_mention}}",
    },
    "Giveaways": {
        "category_id": 1494812777347284992,
        "ping_text": f"<@&1493343282820812872> | {{user_mention}}",
    },
    "Production": {
        "category_id": 1494811687738671184,
        "ping_text": f"<@&1493344270696845414> | {{user_mention}}",
    },
    "Media": {
        "category_id": 1494811888280666254,
        "ping_text": f"<@&1493343006651322549> <@&1493341444344381460> | {{user_mention}}",
    },
    "False Punishments": {
        "category_id": 1494812892732588082,
        "ping_text": f"<@&1493343282820812872> | {{user_mention}}",
    },
    "Report Member": {
        "category_id": 1494812210193764394,
        "ping_text": f"<@&1493343800691527710> | {{user_mention}}",
    },
    "Department": {
        "category_id": 1494812341152383127,
        "ping_text": "@here | {user_mention}",
    },
    "Report Department": {
        "category_id": 1494812448652398793,
        "ping_text": "@here | {user_mention}",
    },
    "Blacklist Server": {
        "category_id": 1494812667997847583,
        "ping_text": "@here | {user_mention}",
    },
    "IT Support": {
        "category_id": 1494813060060283020,
        "ping_text": "@here | {user_mention}",
    },
    "Ownership": {
        "category_id": 1494813060060283020,
        "ping_text": "@here | {user_mention}",
    },
}


class TicketTypeSelect(discord.ui.Select):
    def __init__(self) -> None:
        options = [
            discord.SelectOption(label=ticket_type, value=ticket_type)
            for ticket_type in TICKET_TYPES
        ]
        super().__init__(
            placeholder="Select a ticket type...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="ticket_type_select",
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        selected = self.values[0]
        try:
            await interaction.response.send_modal(TicketInfoModal(selected))
        except Exception as modal_error:
            if interaction.response.is_done():
                await interaction.followup.send(f"Ticket modal failed to open: {modal_error}", ephemeral=True)
            else:
                await interaction.response.send_message(f"Ticket modal failed to open: {modal_error}", ephemeral=True)


class TicketTypeSelectView(discord.ui.View):
    def __init__(self) -> None:
        super().__init__(timeout=None)
        self.add_item(TicketTypeSelect())


def is_ticket_channel(channel: discord.abc.GuildChannel | None) -> bool:
    return isinstance(channel, discord.TextChannel) and channel.name.startswith("ticket-")


def find_open_ticket_for_user(guild: discord.Guild, user_id: int) -> discord.TextChannel | None:
    for channel in guild.text_channels:
        if not is_ticket_channel(channel):
            continue

        owner_id, _ = parse_ticket_topic_metadata(channel.topic)
        if owner_id == user_id:
            return channel

    return None


def parse_ticket_topic_metadata(topic: str | None) -> tuple[int | None, str | None]:
    if not topic:
        return None, None

    owner_id: int | None = None
    ticket_type: str | None = None
    for token in topic.split(";"):
        part = token.strip()
        if part.startswith("ticket_owner_id="):
            raw = part.split("=", 1)[1].strip()
            if raw.isdigit():
                owner_id = int(raw)
        elif part.startswith("ticket_type="):
            ticket_type = part.split("=", 1)[1].strip() or None

    return owner_id, ticket_type


def build_ticket_transcript_filename(channel_name: str) -> str:
    now_tag = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    return f"transcript_{channel_name}_{now_tag}.txt"


def build_ticket_transcript_storage_filename(ticket_id: int, channel_name: str) -> str:
    now_tag = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", channel_name)[:80]
    return f"transcript_{ticket_id}_{safe_name}_{now_tag}.txt"


def save_ticket_transcript_file(ticket_id: int, channel_name: str, transcript_bytes: bytes) -> str | None:
    os.makedirs(TICKET_TRANSCRIPTS_DIR, exist_ok=True)
    filename = build_ticket_transcript_storage_filename(ticket_id, channel_name)
    file_path = os.path.join(TICKET_TRANSCRIPTS_DIR, filename)

    try:
        with open(file_path, "wb") as file:
            file.write(transcript_bytes)
    except OSError:
        return None

    return filename


def delete_expired_ticket_transcripts() -> tuple[int, int]:
    if not os.path.isdir(TICKET_TRANSCRIPTS_DIR):
        return 0, 0

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=TICKET_TRANSCRIPT_RETENTION_DAYS)
    deleted_count = 0
    failed_count = 0

    for filename in os.listdir(TICKET_TRANSCRIPTS_DIR):
        if not (filename.startswith("transcript_") and filename.endswith(".txt")):
            continue

        file_path = os.path.join(TICKET_TRANSCRIPTS_DIR, filename)
        try:
            modified_at = datetime.fromtimestamp(os.path.getmtime(file_path), tz=timezone.utc)
            if modified_at <= cutoff:
                os.remove(file_path)
                deleted_count += 1
        except OSError:
            failed_count += 1

    return deleted_count, failed_count


async def run_ticket_transcript_cleanup_loop() -> None:
    while not bot.is_closed():
        deleted_count, failed_count = delete_expired_ticket_transcripts()
        if deleted_count or failed_count:
            print(
                "Transcript cleanup: "
                f"deleted={deleted_count}, failed={failed_count}, "
                f"retention_days={TICKET_TRANSCRIPT_RETENTION_DAYS}"
            )
        await asyncio.sleep(TICKET_TRANSCRIPT_CLEANUP_INTERVAL_SECONDS)


def find_saved_transcript_filename(ticket_id: int) -> str | None:
    if not os.path.isdir(TICKET_TRANSCRIPTS_DIR):
        return None

    prefix = f"transcript_{ticket_id}_"
    candidates = [name for name in os.listdir(TICKET_TRANSCRIPTS_DIR) if name.startswith(prefix) and name.endswith(".txt")]
    if not candidates:
        return None

    # Return newest transcript for this ticket ID.
    candidates.sort(reverse=True)
    return candidates[0]


async def build_ticket_transcript(channel: discord.TextChannel) -> tuple[str, bytes]:
    lines: list[str] = []
    async for msg in channel.history(limit=None, oldest_first=True):
        created = msg.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        stamp = created.strftime("%Y-%m-%d %H:%M:%S UTC")

        body = msg.content if msg.content else "[No text content]"
        if msg.attachments:
            attachment_urls = ", ".join(att.url for att in msg.attachments if att.url)
            if attachment_urls:
                body = f"{body} | Attachments: {attachment_urls}"

        lines.append(f"[{stamp}] {msg.author} ({msg.author.id}): {body}")

    transcript_text = "\n".join(lines) if lines else "No messages recorded in this ticket."
    filename = build_ticket_transcript_filename(channel.name)
    return filename, transcript_text.encode("utf-8")


async def send_ticket_close_log(
    channel: discord.TextChannel,
    closed_by: discord.Member,
    reason: str,
) -> None:
    guild = channel.guild
    owner_id, ticket_type = parse_ticket_topic_metadata(channel.topic)

    ticket_owner_mention = f"<@{owner_id}>" if owner_id else "Unknown"
    category_name = ticket_type or (channel.category.name if channel.category else "Unknown")
    now = datetime.now(timezone.utc)

    _, transcript_bytes = await build_ticket_transcript(channel)
    saved_transcript_filename = save_ticket_transcript_file(channel.id, channel.name, transcript_bytes)

    close_embed = discord.Embed(
        title="SLCRP | Salt Lake City RP - Ticket Closed",
        description="Ticket Closure Log",
        color=discord.Color.blue(),
        timestamp=now,
    )
    close_embed.add_field(
        name="Info",
        value=f"Ticket {channel.name} closed by {closed_by.mention}.",
        inline=False,
    )
    close_embed.add_field(name="Ticket ID", value=str(channel.id), inline=False)
    close_embed.add_field(name="Reason", value=reason[:1024], inline=False)
    close_embed.add_field(name="Category", value=category_name, inline=False)
    if saved_transcript_filename:
        close_embed.add_field(
            name="Transcript",
            value=f"Saved. Use `{PREFIX}transcript {channel.id}` to view it.",
            inline=False,
        )
    else:
        close_embed.add_field(name="Transcript", value="Failed to save transcript file.", inline=False)
    close_embed.add_field(name="User", value=ticket_owner_mention, inline=True)
    close_embed.add_field(name="User ID", value=str(owner_id) if owner_id else "Unknown", inline=True)
    close_embed.add_field(
        name="Closed at",
        value=f"{now.strftime('%Y-%m-%d %H:%M:%S UTC')} ({discord.utils.format_dt(now, style='F')})",
        inline=False,
    )
    if guild.icon:
        close_embed.set_thumbnail(url=guild.icon.url)
    close_embed.set_footer(
        text=(
            "SLCRP | Salt Lake City RP | Close Ticket System | "
            f"{now.strftime('%Y-%m-%d, %H:%M:%S')}"
        )
    )

    close_log_channel = guild.get_channel(TICKET_CLOSE_LOG_CHANNEL_ID) or bot.get_channel(TICKET_CLOSE_LOG_CHANNEL_ID)
    if isinstance(close_log_channel, discord.TextChannel):
        await close_log_channel.send(embed=close_embed)


async def close_ticket_channel(
    channel: discord.TextChannel,
    closed_by: discord.Member,
    reason: str,
) -> None:
    await send_ticket_close_log(channel, closed_by, reason)
    await channel.delete(reason=f"Ticket closed by {closed_by} | Reason: {reason}")


class AutomodReportView(discord.ui.View):
    """Buttons attached to normal automod log embeds for staff action."""

    def __init__(self, flagged_user: discord.abc.User) -> None:
        super().__init__(timeout=None)
        self.flagged_user = flagged_user

    def _disable_all(self) -> None:
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True

    @discord.ui.button(label="Accept Report", style=discord.ButtonStyle.green)
    async def accept_report(self, button: discord.ui.Button, interaction: discord.Interaction) -> None:
        self._disable_all()
        await interaction.response.edit_message(view=self)
        await interaction.followup.send(
            f"{interaction.user.mention} has moderated {self.flagged_user.mention}."
        )

    @discord.ui.button(label="Dismiss Report", style=discord.ButtonStyle.red)
    async def dismiss_report(self, button: discord.ui.Button, interaction: discord.Interaction) -> None:
        self._disable_all()
        await interaction.response.edit_message(view=self)
        await interaction.followup.send(
            f"{interaction.user.mention} dismissed the automod report without action."
        )


class SpamReportView(discord.ui.View):
    """One-time action buttons for anti-spam reports."""

    def __init__(self, flagged_user: discord.abc.User) -> None:
        super().__init__(timeout=None)
        self.flagged_user = flagged_user
        self.handled = False

    async def _handle_once(self, interaction: discord.Interaction, action_text: str) -> None:
        if self.handled:
            await interaction.response.send_message("This spam report has already been handled.", ephemeral=True)
            return

        self.handled = True
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True

        await interaction.response.edit_message(view=self)
        await interaction.followup.send(
            action_text,
            allowed_mentions=discord.AllowedMentions(users=True),
        )

    @discord.ui.button(label="Deal With", style=discord.ButtonStyle.green, custom_id="spam_report_deal_with")
    async def deal_with(self, button: discord.ui.Button, interaction: discord.Interaction) -> None:
        await self._handle_once(
            interaction,
            f"{interaction.user.mention} has moderated {self.flagged_user.mention} for spam.",
        )

    @discord.ui.button(label="Dismiss", style=discord.ButtonStyle.danger, custom_id="spam_report_dismiss")
    async def dismiss(self, button: discord.ui.Button, interaction: discord.Interaction) -> None:
        await self._handle_once(
            interaction,
            f"{interaction.user.mention} dismissed the spam report without further action.",
        )


class HelpRequestLogView(discord.ui.View):
    """One-time button to mark a help request as handled by staff."""

    def __init__(self, requester: discord.abc.User, source_channel_id: int) -> None:
        super().__init__(timeout=None)
        self.requester = requester
        self.source_channel_id = source_channel_id
        self.handled = False

    @discord.ui.button(label="Mark as Dealt With", style=discord.ButtonStyle.secondary, custom_id="help_mark_dealt_with")
    async def mark_dealt_with(self, button: discord.ui.Button, interaction: discord.Interaction) -> None:
        if self.handled:
            await interaction.response.send_message("This help request has already been marked as dealt with.", ephemeral=True)
            return

        self.handled = True
        button.disabled = True

        guild = interaction.guild
        source_channel = guild.get_channel(self.source_channel_id) if guild else None
        source_channel_text = source_channel.mention if isinstance(source_channel, discord.abc.GuildChannel) else f"<#{self.source_channel_id}>"

        dealt_embed = discord.Embed(
            title="Help Request - Dealt with",
            description=(
                f"{self.requester.mention} has requested help in {source_channel_text}.\n"
                f"This help request has been marked as dealt with by {interaction.user.mention}."
            ),
            color=discord.Color.blue(),
            timestamp=datetime.now(timezone.utc),
        )
        dealt_embed.add_field(name="Channel", value=source_channel_text, inline=True)
        dealt_embed.add_field(name="User", value=self.requester.mention, inline=True)
        if guild and guild.icon:
            dealt_embed.set_thumbnail(url=guild.icon.url)

        await interaction.response.edit_message(embed=dealt_embed, view=self)


class HelpRequestConfirmView(discord.ui.View):
    """Prompt view for ?help confirmation before notifying staff."""

    def __init__(self, requester: discord.Member, source_channel: discord.TextChannel) -> None:
        super().__init__(timeout=120)
        self.requester = requester
        self.source_channel = source_channel
        self.completed = False

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.requester.id:
            await interaction.response.send_message("Only the user who ran this command can use these buttons.", ephemeral=True)
            return False
        return True

    async def _disable_buttons(self, interaction: discord.Interaction) -> None:
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True
        await interaction.response.edit_message(view=self)

    @discord.ui.button(label="Yes", style=discord.ButtonStyle.green, custom_id="help_confirm_yes")
    async def confirm_yes(self, button: discord.ui.Button, interaction: discord.Interaction) -> None:
        if self.completed:
            await interaction.response.send_message("This help request prompt is already handled.", ephemeral=True)
            return

        self.completed = True
        await self._disable_buttons(interaction)

        guild = interaction.guild
        if guild is None:
            await interaction.followup.send("This command can only be used inside a server.", ephemeral=True)
            return

        log_channel = guild.get_channel(HELP_REQUEST_LOG_CHANNEL_ID) or bot.get_channel(HELP_REQUEST_LOG_CHANNEL_ID)
        if not isinstance(log_channel, discord.TextChannel):
            await interaction.followup.send("I could not find the help request log channel.", ephemeral=True)
            return

        embed = discord.Embed(
            title="Help Request!",
            description=f"{self.requester.mention} has requested help in {self.source_channel.mention}.",
            color=discord.Color.blue(),
            timestamp=datetime.now(timezone.utc),
        )
        embed.add_field(name="Channel", value=self.source_channel.mention, inline=True)
        embed.add_field(name="User", value=self.requester.mention, inline=True)
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)

        message_content = None
        if self.source_channel.id == HELP_REQUEST_PING_ONLY_CHANNEL_ID:
            message_content = f"<@&{WARN_COMMAND_ROLE_ID}>"

        await log_channel.send(
            content=message_content,
            embed=embed,
            view=HelpRequestLogView(self.requester, self.source_channel.id),
            allowed_mentions=discord.AllowedMentions(roles=True),
        )
        await interaction.followup.send("Staff has been notified.", ephemeral=True)

    @discord.ui.button(label="No", style=discord.ButtonStyle.red, custom_id="help_confirm_no")
    async def confirm_no(self, button: discord.ui.Button, interaction: discord.Interaction) -> None:
        if self.completed:
            await interaction.response.send_message("This help request prompt is already handled.", ephemeral=True)
            return

        self.completed = True
        await self._disable_buttons(interaction)
        await interaction.followup.send("Help request cancelled.", ephemeral=True)


class ProhibitedInviteReportView(discord.ui.View):
    """One-time action buttons for prohibited invite reports."""

    def __init__(self, offender_id: int, invite_code: str) -> None:
        super().__init__(timeout=None)
        self.offender_id = offender_id
        self.invite_code = invite_code
        self.handled = False

    async def _disable_buttons(self, interaction: discord.Interaction) -> None:
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True
        await interaction.response.edit_message(view=self)

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.danger, custom_id="prohibited_invite_confirm")
    async def confirm(self, button: discord.ui.Button, interaction: discord.Interaction) -> None:
        if self.handled:
            await interaction.response.send_message("This report has already been handled.", ephemeral=True)
            return

        self.handled = True
        await self._disable_buttons(interaction)

        target = discord.Object(id=self.offender_id)
        banned_count = 0
        failed_count = 0
        for guild in bot.guilds:
            try:
                await guild.ban(
                    target,
                    reason=(
                        f"Prohibited invite confirmed by {interaction.user} "
                        f"(code: {self.invite_code})"
                    ),
                    delete_message_days=0,
                )
                banned_count += 1
            except (discord.Forbidden, discord.HTTPException):
                failed_count += 1

        updated_embed = interaction.message.embeds[0] if interaction.message and interaction.message.embeds else None
        if updated_embed is not None:
            updated_embed = updated_embed.copy()
            updated_embed.title = "Prohibited Invite - Confirmed"
            updated_embed.add_field(name="Action", value=f"SWBAN complete in {banned_count} server(s).", inline=False)
            if failed_count:
                updated_embed.add_field(name="Failed Servers", value=str(failed_count), inline=False)
            await interaction.edit_original_response(embed=updated_embed, view=self)

    @discord.ui.button(label="Dismiss", style=discord.ButtonStyle.secondary, custom_id="prohibited_invite_dismiss")
    async def dismiss(self, button: discord.ui.Button, interaction: discord.Interaction) -> None:
        if self.handled:
            await interaction.response.send_message("This report has already been handled.", ephemeral=True)
            return

        self.handled = True
        await self._disable_buttons(interaction)


async def post_ticket_panel() -> None:
    """Rebuild and post the ticket rules + ticket type panel in the configured channel."""
    try:
        settings = RUNTIME_SETTINGS if isinstance(RUNTIME_SETTINGS, dict) else {}
        support_panel = settings.get("ticket_panel", {}) if isinstance(settings.get("ticket_panel"), dict) else {}
        rules_raw = settings.get("ticket_rules", {}) if isinstance(settings.get("ticket_rules"), dict) else {}
        rules = rules_raw if rules_raw else TICKET_RULES_REWORDED

        rules_title = str(support_panel.get("rules_title", "SLCRP | Salt Lake City RP - Ticket System"))
        rules_description = str(
            support_panel.get(
                "rules_description",
                "Kindly make sure to read our complete Ticket Terms of Service below before creating a ticket.",
            )
        )
        panel_footer = str(support_panel.get("footer", "SLCRP | Salt Lake City RP Support System"))
        select_title = str(support_panel.get("select_title", "Open a Ticket"))
        select_description = str(
            support_panel.get("select_description", "Select the type of ticket you would like to open from the menu below.")
        )

        ticket_channel = bot.get_channel(get_ticket_rules_channel_id())
        if isinstance(ticket_channel, discord.TextChannel):
            try:
                async for msg in ticket_channel.history(limit=None):
                    await msg.delete()
            except (discord.Forbidden, discord.HTTPException):
                pass

            embed = discord.Embed(
                title=rules_title,
                description=rules_description,
                color=discord.Color.blue(),
                timestamp=datetime.now(timezone.utc),
            )
            for rule_name, rule_text in rules.items():
                label = str(rule_name).strip()
                text = str(rule_text).strip()
                if not label or not text:
                    continue
                emoji = TICKET_EMOJIS.get(label, "•")
                embed.add_field(name=f"{emoji} {label}", value=text, inline=True)
            if bot.user and bot.user.avatar:
                embed.set_thumbnail(url=bot.user.avatar.url)
            embed.set_footer(text=panel_footer)

            await ticket_channel.send(embed=embed)

            ticket_select_embed = discord.Embed(
                title=select_title,
                description=select_description,
                color=discord.Color.blue(),
            )
            ticket_select_embed.set_footer(text=panel_footer)
            await ticket_channel.send(embed=ticket_select_embed, view=TicketTypeSelectView())
    except Exception as panel_error:
        print(f"Failed to post ticket rules message: {panel_error}")


async def sync_slash_commands_now() -> tuple[int, int, str | None]:
    try:
        guild_obj = discord.Object(id=MAIN_SERVER_GUILD_ID)
        bot.tree.copy_global_to(guild=guild_obj)
        guild_synced_commands = await bot.tree.sync(guild=guild_obj)
        global_synced_commands = await bot.tree.sync()
        return len(guild_synced_commands), len(global_synced_commands), None
    except Exception as sync_error:
        return 0, 0, str(sync_error)


@bot.event
async def on_ready() -> None:
    global unban_task, transcript_cleanup_task, command_tree_synced
    await bot.change_presence(activity=discord.Game(name=STATUS_TEXT))
    bot.add_view(RPChannelView())
    bot.add_view(TicketTypeSelectView())
    ensure_automod_blacklist_file()
    ensure_automod_nsfw_blacklist_file()
    ensure_approved_invites_file()
    ensure_approved_bots_file()
    refresh_all_runtime_caches()
    delete_expired_ticket_transcripts()
    if unban_task is None or unban_task.done():
        unban_task = asyncio.create_task(process_pending_unbans())
    if transcript_cleanup_task is None or transcript_cleanup_task.done():
        transcript_cleanup_task = asyncio.create_task(run_ticket_transcript_cleanup_loop())
    if not command_tree_synced:
        guild_synced_count, global_synced_count, sync_error = await sync_slash_commands_now()
        if sync_error is None:
            command_tree_synced = True
            print(
                f"Slash commands synced: guild={guild_synced_count}, "
                f"global={global_synced_count}"
            )
        else:
            print(f"Failed to sync slash commands: {sync_error}")
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    print(f"Prefix: {PREFIX}")
    registered_commands = sorted(cmd.qualified_name for cmd in bot.commands)
    print(f"Loaded prefix commands: {len(registered_commands)}")
    print(f"baninfo loaded: {'baninfo' in registered_commands}")

    await post_ticket_panel()


@bot.event
async def on_member_join(member: discord.Member) -> None:
    guild = member.guild
    now = datetime.now(timezone.utc)

    if member.bot:
        if member.id in RUNTIME_APPROVED_BOT_IDS:
            return

        inviter: discord.abc.User | None = None
        try:
            async for entry in guild.audit_logs(limit=10, action=discord.AuditLogAction.bot_add):
                target = entry.target
                target_id = getattr(target, "id", None)
                entry_created = entry.created_at
                if entry_created.tzinfo is None:
                    entry_created = entry_created.replace(tzinfo=timezone.utc)
                if target_id == member.id and (now - entry_created) <= timedelta(minutes=2):
                    inviter = entry.user
                    break
        except (discord.Forbidden, discord.HTTPException):
            inviter = None

        try:
            await member.kick(reason="Unauthorized bot invitation attempt")
        except (discord.Forbidden, discord.HTTPException):
            pass

        log_channel = guild.get_channel(ANTI_BOT_LOG_CHANNEL_ID) or bot.get_channel(ANTI_BOT_LOG_CHANNEL_ID)
        if isinstance(log_channel, discord.TextChannel):
            inviter_text = f"{inviter.mention}" if inviter else "Unknown (audit log unavailable)"
            embed = discord.Embed(
                title="Unauthorised Bot Invitation Attempt",
                description="A user tried to invite an Unauthorised bot.",
                color=discord.Color.blue(),
                timestamp=now,
            )
            embed.add_field(name="Banned Bot", value=f"{member.mention} ({member.id})", inline=False)
            embed.add_field(name="Invited By", value=inviter_text, inline=False)
            embed.add_field(name="Server", value=f"{guild.name} ({guild.id})", inline=False)
            if guild.icon:
                embed.set_thumbnail(url=guild.icon.url)
            embed.set_footer(text="SLCRP | Salt Lake City RP Anti-Bot System")
            await log_channel.send(embed=embed)

        return

    created_at = member.created_at or now
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)

    age_delta = now - created_at
    if age_delta > timedelta(days=ALT_DETECTION_MAX_ACCOUNT_AGE_DAYS):
        return

    log_channel = guild.get_channel(ALT_DETECTION_LOG_CHANNEL_ID) or bot.get_channel(ALT_DETECTION_LOG_CHANNEL_ID)
    if not isinstance(log_channel, discord.TextChannel):
        return

    age_days = max(age_delta.days, 0)
    age_hours = max(age_delta.seconds // 3600, 0)
    has_avatar = "Yes" if member.display_avatar else "No"
    mutual_servers = len(member.mutual_guilds)

    embed = discord.Embed(
        title="Suspected Alt Account Detected",
        color=discord.Color.blue(),
        timestamp=now,
    )
    embed.add_field(name="Member", value=member.mention, inline=False)
    embed.add_field(name="Member ID", value=str(member.id), inline=False)
    embed.add_field(
        name="Account Created",
        value=created_at.strftime("%Y-%m-%d %H:%M:%S UTC"),
        inline=False,
    )
    embed.add_field(name="Account Age", value=f"{age_days} days, {age_hours} hours", inline=False)
    embed.add_field(name="Has Avatar", value=has_avatar, inline=False)
    embed.add_field(name="Mutual Servers", value=str(mutual_servers), inline=False)
    embed.add_field(name="Server", value=f"{guild.name} ({guild.id})", inline=False)
    embed.add_field(name="Date", value=discord.utils.format_dt(now, style="F"), inline=False)
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    embed.set_footer(
        text=(
            "SLCRP | Salt Lake City RP Alt Account Detection System | "
            f"{now.strftime('%Y-%m-%d, %H:%M:%S')}"
        )
    )

    await log_channel.send(embed=embed)

    # Time out the suspected alt until their account is 7 days old
    time_until_7_days = timedelta(days=7) - age_delta
    timeout_until = now + time_until_7_days
    try:
        await member.timeout(timeout_until, reason="Suspected alt account — account under 7 days old.")
        timeout_embed = discord.Embed(
            title="Alt Account Timed Out",
            description=(
                f"{member.mention} has been timed out until their account is 7 days old.\n"
                f"Timeout expires: {discord.utils.format_dt(timeout_until, style='F')}"
            ),
            color=discord.Color.orange(),
            timestamp=now,
        )
        timeout_embed.set_footer(text="SLCRP | Salt Lake City RP Alt Account Detection System")
        await log_channel.send(embed=timeout_embed)
    except (discord.Forbidden, discord.HTTPException):
        pass


@bot.event
async def on_voice_state_update(
    member: discord.Member,
    before: discord.VoiceState,
    after: discord.VoiceState,
) -> None:
    if member.bot:
        return

    if after.channel is not None and after.channel.id == TEMP_VC_TRIGGER_CHANNEL_ID:
        await create_or_get_temp_vc(member, after.channel)

    if before.channel is None:
        return

    owner_id = find_temp_vc_owner_by_voice_channel(member.guild.id, before.channel.id)
    if owner_id is None:
        return

    remaining_members = [channel_member for channel_member in before.channel.members if not channel_member.bot]
    if remaining_members:
        return

    await delete_temp_vc_resources(member.guild, owner_id)


async def handle_reaction_role_event(payload: discord.RawReactionActionEvent, *, add_role: bool) -> None:
    if payload.guild_id is None:
        return
    if payload.user_id == bot.user.id:
        return
    if payload.message_id not in RUNTIME_REACTION_ROLE_MESSAGE_IDS:
        return

    role_id = REACTION_ROLE_EMOJI_TO_ROLE_ID.get(str(payload.emoji))
    if role_id is None:
        return

    guild = bot.get_guild(payload.guild_id)
    if guild is None:
        return

    role = guild.get_role(role_id)
    if role is None:
        return

    member = guild.get_member(payload.user_id)
    if member is None:
        try:
            member = await guild.fetch_member(payload.user_id)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            return

    if member.bot:
        return

    try:
        if add_role:
            if role not in member.roles:
                await member.add_roles(role, reason="Reaction role selected")
        else:
            if role in member.roles:
                await member.remove_roles(role, reason="Reaction role removed")
    except (discord.Forbidden, discord.HTTPException):
        return


@bot.event
async def on_raw_reaction_add(payload: discord.RawReactionActionEvent) -> None:
    await handle_reaction_role_event(payload, add_role=True)


@bot.event
async def on_raw_reaction_remove(payload: discord.RawReactionActionEvent) -> None:
    await handle_reaction_role_event(payload, add_role=False)


@bot.event
async def on_message(message: discord.Message) -> None:
    if message.author.bot:
        return

    # --- Ticket auto-close on pinging closeticket role ---
    CLOSE_TICKET_ROLE_NAME = "closeticket"
    if is_ticket_channel(message.channel):
        guild = message.guild
        if guild:
            closeticket_role = discord.utils.get(guild.roles, name=CLOSE_TICKET_ROLE_NAME)
            if closeticket_role and any(role.id == closeticket_role.id for role in message.role_mentions):
                try:
                    await close_ticket_channel(message.channel, message.author, "Closed by pinging closeticket role.")
                except Exception:
                    pass
                return

    if message.guild is None:
        await bot.process_commands(message)
        return

    # Never treat command messages as automod violations.
    stripped_content = (message.content or "").lstrip()
    if stripped_content.startswith(PREFIX):
        await bot.process_commands(message)
        return

    has_automod_bypass = False
    has_spam_bypass = False
    if isinstance(message.author, discord.Member):
        member_role_ids = {role.id for role in message.author.roles}
        has_automod_bypass = AUTOMOD_BYPASS_ROLE_ID in member_role_ids
        has_spam_bypass = SPAM_BYPASS_ROLE_ID in member_role_ids

    if isinstance(message.author, discord.Member) and not has_spam_bypass:
        now = datetime.now(timezone.utc)
        user_key = (message.guild.id, message.channel.id, message.author.id)
        recent_messages = SPAM_AUTOMOD_STATE.setdefault(user_key, deque())
        recent_messages.append((now, message))

        while recent_messages and (now - recent_messages[0][0]).total_seconds() > SPAM_AUTOMOD_WINDOW_SECONDS:
            recent_messages.popleft()

        if len(recent_messages) >= SPAM_AUTOMOD_THRESHOLD:
            last_action = SPAM_AUTOMOD_RECENT_ACTION.get(message.author.id)
            if last_action and (now - last_action).total_seconds() < SPAM_AUTOMOD_WINDOW_SECONDS:
                return

            SPAM_AUTOMOD_RECENT_ACTION[message.author.id] = now

            captured_entries = list(recent_messages)
            recent_messages.clear()

            deleted_count = 0
            unique_messages = {spam_message.id: spam_message for _, spam_message in captured_entries}
            for spam_message in unique_messages.values():
                try:
                    await spam_message.delete()
                    deleted_count += 1
                except (discord.Forbidden, discord.HTTPException):
                    continue

            timeout_result = "Failed (missing permissions or API error)"
            timeout_until = now + timedelta(minutes=AUTOMOD_TIMEOUT_MINUTES)
            try:
                await message.author.timeout(
                    timeout_until,
                    reason=(
                        f"Spam detected: {len(captured_entries)} messages in "
                        f"{SPAM_AUTOMOD_WINDOW_SECONDS} seconds"
                    ),
                )
                timeout_result = f"User timed out for {AUTOMOD_TIMEOUT_MINUTES} minutes"
            except (discord.Forbidden, discord.HTTPException):
                timeout_result = "Failed to timeout user (missing permissions or API error)"

            recent_lines = []
            for received_at, spam_message in captured_entries:
                if spam_message.content and spam_message.content.strip():
                    preview = spam_message.content.strip().replace("`", "'")
                elif spam_message.attachments:
                    preview = "[Attachment message]"
                else:
                    preview = "[No text content]"

                if len(preview) > 140:
                    preview = preview[:137] + "..."

                recent_lines.append(f"[{received_at.strftime('%H:%M:%S')}] {preview}")

            recent_messages_value = "\n".join(recent_lines) or "[No messages captured]"
            if len(recent_messages_value) > 1024:
                recent_messages_value = recent_messages_value[:1021] + "..."

            embed = discord.Embed(
                title="Spam Attempt Detected",
                color=discord.Color.blue(),
                timestamp=now,
            )
            embed.add_field(name="User", value=message.author.mention, inline=False)
            embed.add_field(name="User ID", value=str(message.author.id), inline=False)
            embed.add_field(
                name=f"Messages in {SPAM_AUTOMOD_WINDOW_SECONDS}s",
                value=str(len(captured_entries)),
                inline=False,
            )
            embed.add_field(name="Recent Messages", value=recent_messages_value, inline=False)
            embed.add_field(name="Channel", value=message.channel.mention, inline=False)
            embed.add_field(
                name="Date",
                value=discord.utils.format_dt(now, style="F"),
                inline=False,
            )
            embed.add_field(name="Action", value=timeout_result, inline=False)
            embed.add_field(name="Deleted Messages", value=str(deleted_count), inline=False)
            if message.guild.icon:
                embed.set_thumbnail(url=message.guild.icon.url)
            embed.set_footer(text="SLCRP | Salt Lake City RP Anti-spam")

            log_channel = message.guild.get_channel(SPAM_AUTOMOD_REPORT_CHANNEL_ID) or bot.get_channel(SPAM_AUTOMOD_REPORT_CHANNEL_ID)
            if isinstance(log_channel, discord.TextChannel):
                await log_channel.send(
                    content=f"<@&{SPAM_AUTOMOD_PING_ROLE_ID}>",
                    embed=embed,
                    view=SpamReportView(message.author),
                    allowed_mentions=discord.AllowedMentions(roles=True, users=True),
                )

            return

    # Build combined content for scanning (text + attachment filenames/URLs).
    content_parts = [message.content or ""]
    if message.attachments:
        content_parts.extend(att.url for att in message.attachments if att.url)
        content_parts.extend(att.filename for att in message.attachments if att.filename)
    combined_content = "\n".join(part for part in content_parts if part)

    invite_codes = extract_discord_invite_codes(combined_content)
    if invite_codes and not has_automod_bypass:
        approved_invite_codes = load_approved_invite_codes()
        unapproved_invites = [code for code in invite_codes if code not in approved_invite_codes]
        if unapproved_invites:
            blocked_invite = unapproved_invites[0]
            try:
                await message.delete()
            except (discord.Forbidden, discord.HTTPException):
                pass

            invite_log_channel = message.guild.get_channel(INVITE_AUTOMOD_LOG_CHANNEL_ID) or bot.get_channel(INVITE_AUTOMOD_LOG_CHANNEL_ID)
            if isinstance(invite_log_channel, discord.TextChannel):
                embed = discord.Embed(
                    title="Prohibited Invite Detected",
                    color=discord.Color.blue(),
                    timestamp=datetime.now(timezone.utc),
                )
                embed.add_field(name="User", value=f"{message.author.mention} ({message.author.id})", inline=False)
                embed.add_field(name="Message", value=(message.content or "[No text content]")[:1024], inline=False)
                embed.add_field(name="Blacklisted Invite", value=f"`{blocked_invite}`", inline=False)
                embed.add_field(name="Server", value=message.guild.name, inline=False)
                embed.add_field(name="Channel", value=message.channel.mention, inline=False)
                embed.add_field(
                    name="Date",
                    value=discord.utils.format_dt(datetime.now(timezone.utc), style="F"),
                    inline=False,
                )
                if message.guild.icon:
                    embed.set_thumbnail(url=message.guild.icon.url)
                embed.set_footer(
                    text=(
                        "SLCRP | Salt Lake City RP Anti-Invite System | "
                        f"{datetime.now().strftime('%m/%d/%Y %I:%M %p')}"
                    )
                )

                await invite_log_channel.send(
                    content=f"<@&{WARN_COMMAND_ROLE_ID}>",
                    embed=embed,
                    view=ProhibitedInviteReportView(message.author.id, blocked_invite),
                    allowed_mentions=discord.AllowedMentions(roles=True),
                )

            return

    blacklist_terms = load_automod_blacklist_terms()
    nsfw_terms = load_automod_nsfw_blacklist_terms()

    normal_matched = None
    nsfw_matched = None
    if not has_automod_bypass:
        normal_matched = find_blacklisted_term(combined_content, blacklist_terms) if blacklist_terms else None
        nsfw_matched = find_blacklisted_term(combined_content, nsfw_terms) if nsfw_terms else None

    if not normal_matched and not nsfw_matched:
        await bot.process_commands(message)
        return

    message_preview = (message.content or "").strip()
    if not message_preview:
        message_preview = "[No text content]"
    message_preview = message_preview[:1024]

    # Delete the message once regardless of which list triggered.
    try:
        await message.delete()
    except (discord.Forbidden, discord.HTTPException):
        pass

    # NSFW / offensive matches take priority over the normal automod flow.
    # This prevents duplicate logs and avoids role pings/buttons for NSFW cases.
    if nsfw_matched:
        ban_user = message.author
        log_channel = message.guild.get_channel(AUTOMOD_NSFW_LOG_CHANNEL_ID) or bot.get_channel(AUTOMOD_NSFW_LOG_CHANNEL_ID)
        if isinstance(log_channel, discord.TextChannel):
            embed = discord.Embed(
                title="Offensive / NSFW Content Detected",
                color=discord.Color.blue(),
            )
            embed.add_field(name="User", value=ban_user.mention, inline=True)
            embed.add_field(name="User ID", value=str(ban_user.id), inline=True)
            embed.add_field(name="Message", value=message_preview, inline=False)
            embed.add_field(name="Blacklisted Word", value=f"||`{nsfw_matched}`||", inline=False)
            embed.add_field(name="Action", value="Auto Server Wide Ban (swban)", inline=False)
            embed.add_field(name="Server", value=message.guild.name, inline=True)
            embed.add_field(name="Channel", value=message.channel.mention, inline=True)
            embed.add_field(
                name="Date",
                value=discord.utils.format_dt(datetime.now(timezone.utc), style="F"),
                inline=False,
            )
            if message.guild.icon:
                embed.set_thumbnail(url=message.guild.icon.url)
            embed.set_footer(text="SLCRP | Salt Lake City RP Anti-Offensive/NSFW System")
            await log_channel.send(embed=embed)

        nsfw_ban_reason = "Your message has been flagged for containing offensive or NSFW content."
        for guild in bot.guilds:
            try:
                await guild.ban(
                    ban_user,
                    reason=nsfw_ban_reason,
                    delete_message_days=7,
                )
            except (discord.Forbidden, discord.HTTPException):
                continue

        return

    # Normal automod: timeout + report embed with Accept/Dismiss buttons
    if normal_matched:
        timeout_result = "Not applied"
        if isinstance(message.author, discord.Member):
            timeout_until = datetime.now(timezone.utc) + timedelta(minutes=AUTOMOD_TIMEOUT_MINUTES)
            try:
                await message.author.timeout(
                    timeout_until, reason=f"Blacklisted word detected: {normal_matched}"
                )
                timeout_result = f"Applied ({AUTOMOD_TIMEOUT_MINUTES} minutes)"
            except (discord.Forbidden, discord.HTTPException):
                timeout_result = "Failed (missing permissions or API error)"

        log_channel = message.guild.get_channel(AUTOMOD_LOG_CHANNEL_ID) or bot.get_channel(AUTOMOD_LOG_CHANNEL_ID)
        if isinstance(log_channel, discord.TextChannel):
            embed = discord.Embed(
                title="Blacklisted Word Detected",
                color=discord.Color.blue(),
            )
            embed.add_field(name="User", value=message.author.mention, inline=True)
            embed.add_field(name="User ID", value=str(message.author.id), inline=True)
            embed.add_field(name="Message", value=message_preview, inline=False)
            embed.add_field(name="Blacklisted Word", value=f"`{normal_matched}`", inline=False)
            embed.add_field(name="Timeout", value=timeout_result, inline=False)
            embed.add_field(name="Server", value=message.guild.name, inline=True)
            embed.add_field(name="Channel", value=message.channel.mention, inline=True)
            embed.add_field(
                name="Date",
                value=discord.utils.format_dt(datetime.now(timezone.utc), style="F"),
                inline=False,
            )
            if message.guild.icon:
                embed.set_thumbnail(url=message.guild.icon.url)
            embed.set_footer(text="SLCRP | Salt Lake City RP Anti-Swearing System")
            await log_channel.send(
                content=f"<@&{WARN_COMMAND_ROLE_ID}>",
                embed=embed,
                view=AutomodReportView(message.author),
                allowed_mentions=discord.AllowedMentions(roles=True),
            )

    return


@bot.command(name="help")
async def help(ctx: commands.Context) -> None:
    if ctx.guild is None or not isinstance(ctx.author, discord.Member) or not isinstance(ctx.channel, discord.TextChannel):
        await ctx.send("This command can only be used in a server text channel.")
        return

    await ctx.send(
        "Would you like to call for discord staff?",
        view=HelpRequestConfirmView(ctx.author, ctx.channel),
    )


@bot.command(name="ping")
async def ping(ctx: commands.Context) -> None:
    await ctx.send(f"Pong! `{round(bot.latency * 1000)}ms`")


@bot.command(name="myid")
async def myid(ctx: commands.Context) -> None:
    embed = discord.Embed(
        title="Your User ID",
        description=f"`{ctx.author.id}`",
        color=discord.Color.blue(),
    )
    await ctx.send(embed=embed)


@bot.command(name="id")
async def get_id(ctx: commands.Context, user: str = None) -> None:
    if user is None:
        target_user = ctx.author
    else:
        # Try to convert the input to a user
        try:
            target_user = await commands.UserConverter().convert(ctx, user)
        except commands.BadArgument:
            await ctx.send(f"Could not find user `{user}`.")
            return

    embed = discord.Embed(
        title=f"User ID for {target_user.name}",
        description=f"`{target_user.id}`",
        color=discord.Color.blue(),
    )
    embed.set_thumbnail(url=target_user.display_avatar.url)
    await ctx.send(embed=embed)


@bot.command(name="roleid")
async def roleid(ctx: commands.Context, *, role_query: str | None = None) -> None:
    if ctx.guild is None:
        await ctx.send("This command can only be used in a server.")
        return

    if not role_query:
        await ctx.send(f"Usage: `{PREFIX}roleid <role mention | role name | role id>`")
        return

    target_role: discord.Role | None = None

    if role_query.isdigit():
        target_role = ctx.guild.get_role(int(role_query))

    if target_role is None:
        try:
            target_role = await commands.RoleConverter().convert(ctx, role_query)
        except commands.BadArgument:
            lowered = role_query.lower().strip()
            for role in ctx.guild.roles:
                if role.name.lower() == lowered:
                    target_role = role
                    break

    if target_role is None:
        await ctx.send(f"Could not find role `{role_query}`.")
        return

    embed = discord.Embed(
        title=f"Role ID for {target_role.name}",
        description=f"`{target_role.id}`",
        color=discord.Color.blue(),
    )
    await ctx.send(embed=embed)


@bot.command(name="support")
async def support(ctx: commands.Context) -> None:
    settings = RUNTIME_SETTINGS if isinstance(RUNTIME_SETTINGS, dict) else {}
    support_embed = settings.get("support_embed", {}) if isinstance(settings.get("support_embed"), dict) else {}
    title = str(support_embed.get("title", "Support Channel"))
    description = str(
        support_embed.get(
            "description",
            "The support channel is right here: https://discord.com/channels/1397084580816621618/1493095132852129873",
        )
    )
    embed = discord.Embed(
        title=title,
        description=description,
        color=discord.Color.blue(),
    )
    await ctx.reply(embed=embed)


@bot.command(name="setsetting")
async def setsetting(ctx: commands.Context, key: str = "", *, value: str = "") -> None:
    if ctx.guild is None or not isinstance(ctx.author, discord.Member):
        await ctx.send("This command can only be used in a server.")
        return

    member_role_ids = {role.id for role in ctx.author.roles}
    reload_role_id = get_reload_command_role_id()
    if reload_role_id not in member_role_ids:
        await ctx.send(f"You need the **{role_name_text(reload_role_id, ctx.guild)}** role to use this command.")
        return

    raw_key = key.strip()
    raw_value = value.strip()
    if not raw_key or not raw_value:
        await ctx.send(
            f"Usage: `{PREFIX}setsetting support_title <text>` | `{PREFIX}setsetting support_description <text>` | "
            f"`{PREFIX}setsetting ticket_rule:<Rule Name> <text>`"
        )
        return

    settings = load_runtime_settings()
    support_embed = settings.setdefault("support_embed", {})
    ticket_panel = settings.setdefault("ticket_panel", {})
    ticket_rules = settings.setdefault("ticket_rules", {})

    key_normalized = raw_key.lower()
    target_label = raw_key

    if key_normalized.startswith("ticket_rule:"):
        rule_name = raw_key.split(":", 1)[1].strip()
        if not rule_name:
            await ctx.send("For ticket rules, use: `ticket_rule:<Rule Name>`")
            return
        ticket_rules[rule_name] = raw_value
        target_label = f"ticket_rule:{rule_name}"
    elif key_normalized == "support_title":
        support_embed["title"] = raw_value
    elif key_normalized == "support_description":
        support_embed["description"] = raw_value
    elif key_normalized == "ticket_rules_title":
        ticket_panel["rules_title"] = raw_value
    elif key_normalized == "ticket_rules_description":
        ticket_panel["rules_description"] = raw_value
    elif key_normalized == "ticket_select_title":
        ticket_panel["select_title"] = raw_value
    elif key_normalized == "ticket_select_description":
        ticket_panel["select_description"] = raw_value
    elif key_normalized == "ticket_footer":
        ticket_panel["footer"] = raw_value
    else:
        await ctx.send(
            "Invalid setting key. Use one of: "
            "`support_title`, `support_description`, `ticket_rules_title`, `ticket_rules_description`, "
            "`ticket_select_title`, `ticket_select_description`, `ticket_footer`, `ticket_rule:<Rule Name>`."
        )
        return

    save_runtime_settings(settings)
    refresh_runtime_settings()

    await ctx.send(f"Updated setting `{target_label}`.")


@bot.command(name="setid")
async def setid(ctx: commands.Context, key: str = "", value: str = "") -> None:
    if ctx.guild is None or not isinstance(ctx.author, discord.Member):
        await ctx.send("This command can only be used in a server.")
        return

    member_role_ids = {role.id for role in ctx.author.roles}
    reload_role_id = get_reload_command_role_id()
    if reload_role_id not in member_role_ids:
        await ctx.send(f"You need the **{role_name_text(reload_role_id, ctx.guild)}** role to use this command.")
        return

    allowed_keys = {
        "reload_command_role_id": "Reload command access role",
        "ticket_rules_channel_id": "Ticket rules panel channel",
    }

    key_text = key.strip().lower()
    value_text = value.strip()

    if key_text == "list":
        lines = [f"`{name}` - {label}" for name, label in allowed_keys.items()]
        await ctx.send("Editable runtime IDs:\n" + "\n".join(lines))
        return

    if key_text not in allowed_keys:
        await ctx.send(
            "Invalid ID key. Use: `reload_command_role_id`, "
            "`ticket_rules_channel_id` or `list`."
        )
        return

    try:
        new_id = int(value_text)
    except ValueError:
        await ctx.send("ID must be a numeric Discord ID.")
        return

    settings = load_runtime_settings()
    id_overrides = settings.setdefault("id_overrides", {})
    id_overrides[key_text] = new_id
    save_runtime_settings(settings)
    refresh_runtime_settings()

    await ctx.send(f"Updated `{key_text}` to `{new_id}`.")


@bot.command(name="ingame")
@main_server_role_required(RP_COMMAND_ROLE_ID)
async def ingame(ctx: commands.Context) -> None:
    payload, error = await _fetch_erlc_json("/server", {"Players": "true"})
    if error or not isinstance(payload, dict):
        await ctx.send(f"Could not fetch in-game players. {error or ''}".strip())
        return

    players = payload.get("Players") or []
    if not isinstance(players, list):
        players = []
    if not players:
        embed = discord.Embed(
            title="ERLC Players Currently In-Game (0)",
            description="No players are currently in-game.",
            color=discord.Color.blue(),
            timestamp=datetime.now(timezone.utc),
        )
        await ctx.send(embed=embed)
        return

    lines = [_format_erlc_player_line(player) for player in players]
    max_lines = 25
    shown = lines[:max_lines]

    embed = discord.Embed(
        title=f"ERLC Players Currently In-Game ({len(players)})",
        description="\n".join(shown),
        color=discord.Color.blue(),
        timestamp=datetime.now(timezone.utc),
    )
    if len(lines) > max_lines:
        embed.set_footer(text=f"Showing {max_lines}/{len(lines)} players")
    await ctx.send(embed=embed)


@bot.command(name="checkstaff")
@main_server_role_required(RP_COMMAND_ROLE_ID)
async def checkstaff(ctx: commands.Context) -> None:
    payload, error = await _fetch_erlc_json("/server", {"Players": "true"})
    if error or not isinstance(payload, dict):
        await ctx.send(f"Could not fetch in-game staff. {error or ''}".strip())
        return

    players = payload.get("Players") or []
    if not isinstance(players, list):
        players = []
    staff_players = [p for p in players if _is_staff_player(p)]

    if not staff_players:
        embed = discord.Embed(
            title="ERLC Staff Currently In-Game (0)",
            description="No staff members are currently in-game.",
            color=discord.Color.blue(),
            timestamp=datetime.now(timezone.utc),
        )
        await ctx.send(embed=embed)
        return

    lines = [_format_erlc_player_line(player) for player in staff_players]
    max_lines = 25
    shown = lines[:max_lines]

    embed = discord.Embed(
        title=f"ERLC Staff Currently In-Game ({len(staff_players)})",
        description="\n".join(shown),
        color=discord.Color.blue(),
        timestamp=datetime.now(timezone.utc),
    )
    if len(lines) > max_lines:
        embed.set_footer(text=f"Showing {max_lines}/{len(lines)} staff members")
    await ctx.send(embed=embed)


@bot.command(name="queue")
async def queue(ctx: commands.Context) -> None:
    payload, error = await _fetch_erlc_json("/server", {"Queue": "true"})
    if error or not isinstance(payload, dict):
        await ctx.send(f"Could not fetch server queue. {error or ''}".strip())
        return

    queue_data = payload.get("Queue", [])
    queue_count = len(queue_data) if isinstance(queue_data, list) else 0

    embed = discord.Embed(
        title="ERLC Server Queue",
        color=discord.Color.blue(),
        timestamp=datetime.now(timezone.utc),
    )
    embed.add_field(name="Players In Queue", value=f"**{queue_count}**", inline=False)
    await ctx.send(embed=embed)


async def resolve_owned_temp_vc(
    ctx: commands.Context,
) -> tuple[dict, discord.VoiceChannel, discord.TextChannel] | None:
    if ctx.guild is None or not isinstance(ctx.author, discord.Member):
        await ctx.send("This command can only be used in a server.")
        return None

    temp_vc = await get_temp_vc_channels(ctx.guild, ctx.author.id)
    if temp_vc is None:
        await ctx.send("You do not currently own a temporary VC.")
        return None

    _, voice_channel, _ = temp_vc
    if ctx.channel.id != voice_channel.id:
        await ctx.send(f"Use this command in {voice_channel.mention}.")
        return None

    return temp_vc


@bot.command(name="out")
async def out(ctx: commands.Context, member: discord.Member) -> None:
    temp_vc = await resolve_owned_temp_vc(ctx)
    if temp_vc is None:
        return

    _, voice_channel, _ = temp_vc
    if member.id == ctx.author.id:
        await ctx.send("You cannot remove yourself from your own VC.")
        return

    if member.voice is None or member.voice.channel is None or member.voice.channel.id != voice_channel.id:
        await ctx.send("That user is not in your VC.")
        return

    try:
        await member.move_to(None, reason=f"Removed from temporary VC by {ctx.author}")
    except (discord.Forbidden, discord.HTTPException):
        await ctx.send("I could not remove that user from your VC.")
        return

    await ctx.send(f"Removed {member.mention} from your VC.")


@bot.command(name="lock")
async def lock(ctx: commands.Context) -> None:
    temp_vc = await resolve_owned_temp_vc(ctx)
    if temp_vc is None:
        return

    _, voice_channel, _ = temp_vc
    bypass_role = ctx.guild.get_role(VC_LOCK_BYPASS_ROLE_ID)
    try:
        await voice_channel.set_permissions(
            ctx.guild.default_role,
            connect=False,
            reason=f"Temporary VC locked by {ctx.author}",
        )
        if bypass_role is not None:
            await voice_channel.set_permissions(
                bypass_role,
                connect=False,
                reason=f"Temporary VC restricted role blocked by {ctx.author}",
            )
    except (discord.Forbidden, discord.HTTPException):
        await ctx.send("I could not lock your VC.")
        return

    await ctx


@bot.command(name="unlock")
async def unlock(ctx: commands.Context) -> None:
    temp_vc = await resolve_owned_temp_vc(ctx)
    if temp_vc is None:
        return

    _, voice_channel, _ = temp_vc
    bypass_role = ctx.guild.get_role(VC_LOCK_BYPASS_ROLE_ID)
    try:
        await voice_channel.set_permissions(
            ctx.guild.default_role,
            connect=True,
            reason=f"Temporary VC unlocked by {ctx.author}",
        )
        if bypass_role is not None:
            await voice_channel.set_permissions(
                bypass_role,
                connect=True,
                reason=f"Temporary VC restricted role allowed by {ctx.author}",
            )
    except (discord.Forbidden, discord.HTTPException):
        await ctx.send("I could not unlock your VC.")
        return

    await ctx.send("Your VC is now unlocked.")


@bot.command(name="soundboard")
async def soundboard(ctx: commands.Context, state: str) -> None:
    temp_vc = await resolve_owned_temp_vc(ctx)
    if temp_vc is None:
        return

    if not isinstance(ctx.author, discord.Member) or ctx.author.get_role(BOOSTER_ROLE_ID) is None:
        await ctx.send(f"You must have the **{role_name_text(BOOSTER_ROLE_ID, ctx.guild)}** role to use this command.")
        return

    normalized_state = state.lower().strip()
    if normalized_state not in {"on", "off"}:
        await ctx.send(f"Use `{PREFIX}soundboard on` or `{PREFIX}soundboard off`.")
        return

    _, voice_channel, _ = temp_vc
    everyone_overwrite = voice_channel.overwrites_for(ctx.guild.default_role)
    everyone_overwrite.use_soundboard = normalized_state == "on"

    owner_overwrite = voice_channel.overwrites_for(ctx.author)
    owner_overwrite.use_soundboard = True

    try:
        await voice_channel.set_permissions(
            ctx.guild.default_role,
            overwrite=everyone_overwrite,
            reason=f"Temporary VC soundboard changed by {ctx.author}",
        )
        await voice_channel.set_permissions(
            ctx.author,
            overwrite=owner_overwrite,
            reason=f"Ensure owner keeps soundboard access in temporary VC",
        )
    except (discord.Forbidden, discord.HTTPException):
        await ctx.send("I could not update soundboard access in your VC.")
        return

    await ctx.send(f"Soundboard is now {'enabled' if normalized_state == 'on' else 'disabled'} in your VC.")


@bot.command(name="say")
@commands.has_permissions(manage_messages=True)
async def say(ctx: commands.Context, *, message: str) -> None:
    await ctx.message.delete()
    await ctx.send(message)


@bot.command(name="clear")
@commands.has_permissions(manage_messages=True)
async def purge(ctx: commands.Context, amount: int) -> None:
    if amount < 1 or amount > 100:
        await ctx.send("Please choose an amount from 1 to 100.")
        return

    deleted = await ctx.channel.purge(limit=amount + 1)
    msg = await ctx.send(f"Deleted {max(len(deleted) - 1, 0)} messages.")
    await msg.delete(delay=4)


@bot.command(name="kick")
@commands.has_permissions(kick_members=True)
async def kick(
    ctx: commands.Context,
    member: discord.Member,
    *,
    reason: str = "No reason provided",
) -> None:
    await member.kick(reason=reason)
    await ctx.send(f"Kicked {member.mention}. Reason: {reason}")


@bot.command(name="ban")
@commands.has_permissions(ban_members=True)
async def ban(
    ctx: commands.Context,
    member: discord.Member,
    *,
    reason: str = "No reason provided",
) -> None:
    await member.ban(reason=reason)
    appeal_invite_url = await get_ban_appeal_invite_url()
    main_dm_sent = await send_main_bot_ban_appeal_dm(
        member,
        "banned",
        reason,
        str(ctx.author),
        appeal_invite_url,
    )
    modmail_queued = queue_modmail_ban_appeal_dm(
        member.id,
        "banned",
        reason,
        str(ctx.author),
        appeal_invite_url,
    )

    dm_status = []
    dm_status.append("main bot DM sent" if main_dm_sent else "main bot DM failed")
    dm_status.append("modmail DM queued" if modmail_queued else "modmail DM queue failed")
    await ctx.send(f"Banned {member.mention}. Reason: {reason} ({', '.join(dm_status)})")


async def run_baninfo_lookup(ctx: commands.Context, target: str) -> None:
    user_id = parse_user_id(target)
    if user_id is None:
        await ctx.send(f"Usage: `{PREFIX}baninfo <user_id>`")
        return

    user = discord.Object(id=user_id)
    try:
        fetched_user = await bot.fetch_user(user_id)
        user = fetched_user
        user_label = f"{fetched_user.mention} ({user_id})"
    except discord.NotFound:
        user_label = f"<@{user_id}> ({user_id})"
    except discord.HTTPException:
        user_label = f"<@{user_id}> ({user_id})"

    found_reason: str | None = None
    found_guild: discord.Guild | None = None

    for guild in get_all_server_ban_guilds(include_ban_appeal=True):
        try:
            ban_entry = await guild.fetch_ban(user)
            found_reason = ban_entry.reason or "No reason provided"
            found_guild = guild
            break
        except discord.NotFound:
            continue
        except discord.Forbidden:
            continue
        except discord.HTTPException:
            continue

    if found_reason is None:
        await ctx.send(f"No ban record found for {user_label} in the configured servers.")
        return

    embed = discord.Embed(
        title="Ban Info",
        color=discord.Color.orange(),
        timestamp=datetime.now(timezone.utc),
    )
    embed.add_field(name="Target", value=user_label, inline=False)
    embed.add_field(name="Server", value=found_guild.name if found_guild else "Unknown", inline=False)
    embed.add_field(name="Reason", value=found_reason, inline=False)
    await ctx.send(embed=embed)


@bot.command(name="baninfo")
@commands.has_permissions(ban_members=True)
async def baninfo(ctx: commands.Context, target: str) -> None:
    await run_baninfo_lookup(ctx, target)


@bot.command(name="swban")
@main_server_role_required(ALL_SERVER_BAN_COMMAND_ROLE_ID)
async def swban(ctx: commands.Context, target: str, *, reason: str) -> None:
    user_id = parse_user_id(target)
    if user_id is None:
        await ctx.send("Use a user mention or numeric user ID.")
        return

    try:
        user = await bot.fetch_user(user_id)
    except discord.NotFound:
        await ctx.send("User was not found.")
        return
    except discord.HTTPException:
        await ctx.send("I could not fetch that user right now.")
        return

    banned_count = 0
    failed_count = 0
    deleted_messages_count = 0
    target_guilds = get_all_server_ban_guilds()
    for guild in target_guilds:
        try:
            await guild.ban(user, reason=f"Server-wide ban by {ctx.author}: {reason}", delete_message_days=0)
            banned_count += 1

            # After banning, remove recent messages from this user in the guild.
            deleted_messages_count += await delete_recent_user_messages(guild, user.id, days=7)
        except (discord.Forbidden, discord.HTTPException):
            failed_count += 1

    appeal_invite_url = await get_ban_appeal_invite_url()
    main_dm_sent = False
    modmail_queued = False
    if banned_count > 0:
        main_dm_sent = await send_main_bot_ban_appeal_dm(
            user,
            "banned across SLCRP servers",
            reason,
            str(ctx.author),
            appeal_invite_url,
        )
        modmail_queued = queue_modmail_ban_appeal_dm(
            user.id,
            "banned across SLCRP servers",
            reason,
            str(ctx.author),
            appeal_invite_url,
        )

    status_embed = discord.Embed(
        title="SLCRP | Salt Lake City RP | Server Wide Ban System",
        description=(
            f"Successfully server-wide banned user: {user.mention}.\n\n"
            f"Reason: **{reason}**.\n\n"
            f"Banned in: **{banned_count}** server(s)."
        ),
        color=discord.Color.orange(),
    )
    if failed_count > 0:
        status_embed.add_field(name="Failed Servers", value=str(failed_count), inline=False)
    status_embed.set_footer(
        text=(
            "SLCRP | Salt Lake City RP | Server Wide Ban System | "
            f"{datetime.now().strftime('%Y-%m-%d, %H:%M:%S')}"
        )
    )
    await ctx.send(embed=status_embed)


@bot.command(name="swunban")
@main_server_role_required(ALL_SERVER_BAN_COMMAND_ROLE_ID)
async def swunban(ctx: commands.Context, target: str, *, reason: str = "No reason provided") -> None:
    user_id = parse_user_id(target)
    if user_id is None:
        await ctx.send("Use a user mention or numeric user ID.")
        return

    user: discord.abc.User | discord.Object = discord.Object(id=user_id)
    user_mention = f"<@{user_id}>"
    try:
        fetched_user = await bot.fetch_user(user_id)
        user = fetched_user
        user_mention = fetched_user.mention
    except discord.NotFound:
        pass
    except discord.HTTPException:
        pass

    unbanned_count = 0
    failed_count = 0
    for guild in bot.guilds:
        try:
            await guild.unban(user, reason=f"Server-wide unban by {ctx.author}: {reason}")
            unbanned_count += 1
        except discord.NotFound:
            # User was not banned in this guild.
            continue
        except (discord.Forbidden, discord.HTTPException):
            failed_count += 1

    status_embed = discord.Embed(
        title="SLCRP | Salt Lake City RP | Server Wide Unban System",
        description=(
            f"[SUCCESS] Successfully server-wide unbanned user: {user_mention}.\n\n"
            f"Reason: {reason}\n\n"
            f"Unbanned in: **{unbanned_count}** server(s)."
        ),
        color=discord.Color.blue(),
    )
    if failed_count > 0:
        status_embed.add_field(name="Failed Servers", value=str(failed_count), inline=False)
    status_embed.set_footer(
        text=(
            "SLCRP | Salt Lake City RP | Server Wide Unban System | "
            f"{datetime.now().strftime('%Y-%m-%d, %H:%M:%S')}"
        )
    )
    await ctx.send(embed=status_embed)


@bot.command(name="unban")
@commands.has_permissions(ban_members=True)
async def unban(
    ctx: commands.Context,
    user_id: int,
    *,
    reason: str = "No reason provided",
) -> None:
    user = await bot.fetch_user(user_id)
    await ctx.guild.unban(user, reason=reason)
    await ctx.send(f"Unbanned {user}. Reason: {reason}")


@bot.command(name="setstatus")
@commands.has_permissions(administrator=True)
async def setstatus(ctx: commands.Context, *, text: str) -> None:
    await bot.change_presence(activity=discord.Game(name=text))
    await ctx.send(f"Status updated to: `{text}`")


def format_elapsed(elapsed: timedelta) -> str:
    total_seconds = int(elapsed.total_seconds())
    days, remainder = divmod(total_seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)

    parts: list[str] = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
    if seconds > 0 or not parts:
        parts.append(f"{seconds}s")
    return " ".join(parts)


def format_rp_options_text() -> str:
    return "\n".join([f"{key}. {value}" for key, value in RP_CHANNEL_OPTIONS.items()])


def resolve_rp_option(option_input: str) -> str | None:
    cleaned = option_input.strip()
    if cleaned in RP_CHANNEL_OPTIONS:
        return RP_CHANNEL_OPTIONS[cleaned]

    lowered = cleaned.lower()
    for value in RP_CHANNEL_OPTIONS.values():
        if lowered == value.lower():
            return value
    return None


def resolve_rp_channel(guild: discord.Guild) -> discord.TextChannel | None:
    configured_channel = guild.get_channel(get_rp_channel_id())
    if isinstance(configured_channel, discord.TextChannel):
        return configured_channel

    valid_names = {name.lower() for name in RP_CHANNEL_OPTIONS.values()}
    for channel in guild.text_channels:
        if channel.name.lower() in valid_names:
            return channel

    return None


async def change_rp_channel(guild: discord.Guild, actor_name: str, actor_id: int, option_input: str) -> str:
    now = datetime.now(timezone.utc)

    if actor_id in RP_CHANNEL_COOLDOWN:
        cooldown_expiry = RP_CHANNEL_COOLDOWN[actor_id]
        if now < cooldown_expiry:
            remaining = int((cooldown_expiry - now).total_seconds())
            return f"❌ You can change RP again in {remaining} seconds."

    channel = resolve_rp_channel(guild)
    if not isinstance(channel, discord.TextChannel):
        rp_channel_id = get_rp_channel_id()
        return (
            f"❌ RP channel with ID `{rp_channel_id}` not found. "
            f"Update `id_overrides.rp_channel_id` in `{RUNTIME_SETTINGS_PATH}` and run `{PREFIX}reload settings`."
        )

    new_name = resolve_rp_option(option_input)
    if new_name is None:
        return (
            "❌ Invalid RP option.\n"
            f"Use `{PREFIX}rp change` and choose from buttons."
        )

    try:
        await channel.edit(name=new_name, reason=f"RP channel changed by {actor_name}")
    except discord.Forbidden:
        return "❌ I do not have permission to rename that channel."
    except discord.HTTPException as error:
        return f"❌ Failed to rename the RP channel: {error}"

    global RP_CURRENT_NAME, RP_CURRENT_SINCE
    RP_CURRENT_NAME = new_name
    RP_CURRENT_SINCE = now
    RP_CHANGE_HISTORY.append((new_name, now))
    RP_CHANNEL_COOLDOWN[actor_id] = now + timedelta(seconds=RP_COOLDOWN_SECONDS)
    return f"✅ RP has been changed to {new_name}"


class RPChannelView(discord.ui.View):
    def __init__(self) -> None:
        super().__init__(timeout=None)

    @discord.ui.button(label="1️⃣ River City RP", style=discord.ButtonStyle.blurple, custom_id="rp_river_city")
    async def river_city(self, button: discord.ui.Button, interaction: discord.Interaction) -> None:
        await self._change_rp(interaction, "1")

    @discord.ui.button(label="2️⃣ Highway RP", style=discord.ButtonStyle.blurple, custom_id="rp_highway")
    async def highway(self, button: discord.ui.Button, interaction: discord.Interaction) -> None:
        await self._change_rp(interaction, "2")

    @discord.ui.button(label="3️⃣ High Rock RP", style=discord.ButtonStyle.blurple, custom_id="rp_high_rock")
    async def high_rock(self, button: discord.ui.Button, interaction: discord.Interaction) -> None:
        await self._change_rp(interaction, "3")

    @discord.ui.button(label="4️⃣ River City County", style=discord.ButtonStyle.blurple, custom_id="rp_river_county")
    async def river_county(self, button: discord.ui.Button, interaction: discord.Interaction) -> None:
        await self._change_rp(interaction, "4")

    @discord.ui.button(label="5️⃣ Springfield County", style=discord.ButtonStyle.blurple, custom_id="rp_springfield_county")
    async def springfield_county(self, button: discord.ui.Button, interaction: discord.Interaction) -> None:
        await self._change_rp(interaction, "5")

    @discord.ui.button(label="6️⃣ Springfield RP", style=discord.ButtonStyle.blurple, custom_id="rp_springfield")
    async def springfield(self, button: discord.ui.Button, interaction: discord.Interaction) -> None:
        await self._change_rp(interaction, "6")

    @discord.ui.button(label="7️⃣ Full Map", style=discord.ButtonStyle.blurple, custom_id="rp_full_map")
    async def full_map(self, button: discord.ui.Button, interaction: discord.Interaction) -> None:
        await self._change_rp(interaction, "7")

    @discord.ui.button(label="8️⃣ In-Game Event", style=discord.ButtonStyle.blurple, custom_id="rp_event")
    async def event(self, button: discord.ui.Button, interaction: discord.Interaction) -> None:
        await self._change_rp(interaction, "8")

    @discord.ui.button(label="9️⃣ Server Shut Down", style=discord.ButtonStyle.blurple, custom_id="rp_shutdown")
    async def shutdown(self, button: discord.ui.Button, interaction: discord.Interaction) -> None:
        await self._change_rp(interaction, "9")

    @discord.ui.button(label="🔟 Server Restart", style=discord.ButtonStyle.blurple, custom_id="rp_restart")
    async def restart(self, button: discord.ui.Button, interaction: discord.Interaction) -> None:
        await self._change_rp(interaction, "10")

    async def _change_rp(self, interaction: discord.Interaction, option: str) -> None:
        if interaction.guild is None:
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return

        result = await change_rp_channel(
            interaction.guild,
            str(interaction.user),
            interaction.user.id,
            option,
        )
        await interaction.response.send_message(result, ephemeral=True)


async def finish_giveaway_after_delay(
    *,
    guild_id: int,
    channel_id: int,
    message_id: int,
    prize: str,
    duration_seconds: int,
) -> None:
    await asyncio.sleep(max(duration_seconds, 1))

    guild = bot.get_guild(guild_id)
    if guild is None:
        return

    channel = guild.get_channel(channel_id) or bot.get_channel(channel_id)
    if not isinstance(channel, discord.TextChannel):
        return

    try:
        giveaway_message = await channel.fetch_message(message_id)
    except (discord.NotFound, discord.Forbidden, discord.HTTPException):
        return

    entrants: list[discord.abc.User] = []
    for reaction in giveaway_message.reactions:
        if str(reaction.emoji) != GIVEAWAY_ENTRY_EMOJI:
            continue
        try:
            async for user in reaction.users():
                if not user.bot:
                    entrants.append(user)
        except (discord.Forbidden, discord.HTTPException):
            continue
        break

    winner = random.choice(entrants) if entrants else None

    end_embed = discord.Embed(
        title="Giveaway Ended",
        color=discord.Color.gold(),
        timestamp=datetime.now(timezone.utc),
    )
    end_embed.add_field(name="Prize", value=prize, inline=False)
    end_embed.add_field(name="Entries", value=str(len(entrants)), inline=True)
    if winner is None:
        end_embed.add_field(name="Winner", value="No valid entries.", inline=True)
        await channel.send(embed=end_embed)
        return

    end_embed.add_field(name="Winner", value=winner.mention, inline=True)
    await channel.send(content=f"Congratulations {winner.mention}! You won **{prize}**.", embed=end_embed)


async def post_reaction_roles_panel(target_channel: discord.TextChannel) -> discord.Message:
    description = (
        "This system allows members to customize their experience within the community by selecting roles through reactions. "
        "By reacting to the designated messages, you can gain access to departments, notifications, pings, platform roles, colors, "
        "and special community features without needing staff assistance.\n\n"
        "Reaction roles help keep Salt Lake City Roleplay organized, efficient, and easy for everyone to navigate while giving members "
        "full control over the roles they want. Be sure to select the roles that match your interests to stay updated with important "
        "announcements, events, and department information throughout the community.\n\n"
        "🎥 **Media Ping**\n"
        "React to this role to receive notifications whenever Salt Lake City Roleplay uploads new media content, including screenshots, trailers, patrol highlights, event recordings, announcements, and community showcases. Stay updated with the latest photos, videos, and promotional content from around the community.\n\n"
        "📊 **Poll Ping**\n"
        "React to this role to receive notifications whenever new polls, community votes, feedback forms, or important decisions are posted within Salt Lake City Roleplay. Your opinion helps shape the future of the community, so stay informed and make your voice heard.\n\n"
        "🎮 **Session Ping**\n"
        "Session Ping is a server notification role used to alert members when an official session, training, meeting, or in-game event is starting. When this role is pinged, it means staff or leadership are actively hosting a structured session that requires player participation or attendance.\n\n"
        "🥳 **Giveaway Ping**\n"
        "Giveaway Ping is a notification role used to alert members whenever a giveaway is announced or going live within the server. When this role is pinged, it means there is an active opportunity to participate in a prize event such as in-game rewards, special roles, currency, or exclusive perks.\n\n"
        "🎪 **Event Ping**\n"
        "Event Ping is a notification role used to alert members about upcoming or live server events. This includes special roleplay scenarios, community activities, competitions, or seasonal events hosted by staff. When this role is pinged, it means an official event is starting or about to begin, and members are encouraged to join in and participate.\n\n"
        "👥 **Partnership Ping**\n"
        "Partnership Ping is a notification role used to announce updates, events, or important information from partnered servers or organizations. When this role is pinged, it means one of our official partners is hosting something or sharing an opportunity with the community."
    )

    embed = discord.Embed(
        title="Welcome to Salt Lake City Roleplay Reaction Roles!",
        description=description,
        color=discord.Color.blue(),
        timestamp=datetime.now(timezone.utc),
    )
    embed.add_field(
        name="Reactions",
        value=(
            "📸 - Media Ping\n"
            "📊 - Poll Ping\n"
            "🎮 - Session Ping\n"
            "🥳 - Giveaway Ping\n"
            "🎪 - Event Ping\n"
            "👥 - Partnership Ping"
        ),
        inline=False,
    )

    panel_message = await target_channel.send(embed=embed)
    for emoji in REACTION_ROLE_EMOJI_TO_ROLE_ID:
        await panel_message.add_reaction(emoji)

    RUNTIME_REACTION_ROLE_MESSAGE_IDS.add(panel_message.id)
    save_reaction_role_message_ids(RUNTIME_REACTION_ROLE_MESSAGE_IDS)
    return panel_message


@bot.tree.command(name="giveaway", description="Create a giveaway")
@app_commands.checks.has_permissions(manage_guild=True)
@app_commands.describe(
    prize="Prize for the giveaway",
    description="Description for the giveaway",
    time_1s_1m_1h_1d="Duration (examples: 30s, 10m, 2h, 1d)",
    channel="Channel where giveaway will be posted",
)
async def giveaway_slash(
    interaction: discord.Interaction,
    prize: str,
    description: str,
    time_1s_1m_1h_1d: str,
    channel: discord.TextChannel,
) -> None:
    if interaction.guild is None:
        await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
        return

    duration_seconds = parse_duration_token(time_1s_1m_1h_1d)
    if duration_seconds is None:
        await interaction.response.send_message("Invalid time format. Use values like `30s`, `10m`, `2h`, or `1d`.", ephemeral=True)
        return

    if len(prize.strip()) == 0 or len(description.strip()) == 0:
        await interaction.response.send_message("Prize and description cannot be empty.", ephemeral=True)
        return

    end_time = datetime.now(timezone.utc) + timedelta(seconds=duration_seconds)
    giveaway_embed = discord.Embed(
        title="Giveaway",
        description=description.strip(),
        color=discord.Color.gold(),
        timestamp=datetime.now(timezone.utc),
    )
    giveaway_embed.add_field(name="Prize", value=prize.strip(), inline=False)
    giveaway_embed.add_field(name="Ends", value=discord.utils.format_dt(end_time, style="R"), inline=True)
    giveaway_embed.add_field(name="Hosted By", value=interaction.user.mention, inline=True)
    giveaway_embed.set_footer(text=f"React with {GIVEAWAY_ENTRY_EMOJI} to enter")

    try:
        giveaway_message = await channel.send(
            content=f"<@&{REACTION_ROLE_EMOJI_TO_ROLE_ID['🥳']}>",
            embed=giveaway_embed,
            allowed_mentions=discord.AllowedMentions(roles=True),
        )
        await giveaway_message.add_reaction(GIVEAWAY_ENTRY_EMOJI)
    except (discord.Forbidden, discord.HTTPException) as send_error:
        await interaction.response.send_message(f"Failed to post giveaway: {send_error}", ephemeral=True)
        return

    asyncio.create_task(
        finish_giveaway_after_delay(
            guild_id=interaction.guild.id,
            channel_id=channel.id,
            message_id=giveaway_message.id,
            prize=prize.strip(),
            duration_seconds=duration_seconds,
        )
    )

    await interaction.response.send_message(
        f"Giveaway posted in {channel.mention}. It ends {discord.utils.format_dt(end_time, style='R')}.",
        ephemeral=True,
    )


@bot.tree.command(name="reactionroles", description="Post the reaction roles panel")
@app_commands.checks.has_permissions(manage_guild=True)
@app_commands.describe(channel="Channel where the reaction roles panel should be posted")
async def reactionroles_slash(interaction: discord.Interaction, channel: discord.TextChannel) -> None:
    if interaction.guild is None:
        await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)
    try:
        panel_message = await post_reaction_roles_panel(channel)
    except (discord.Forbidden, discord.HTTPException) as panel_error:
        await interaction.followup.send(f"Failed to post reaction roles panel: {panel_error}", ephemeral=True)
        return

    await interaction.followup.send(
        f"Reaction roles panel posted in {channel.mention}.\nMessage ID: `{panel_message.id}`",
        ephemeral=True,
    )


@bot.command(name="rp")
@main_server_role_required(RP_COMMAND_ROLE_ID)
async def rp(ctx: commands.Context, action: str | None = None, *, option: str | None = None) -> None:
    if ctx.guild is None:
        await ctx.send("This command can only be used in a server.")
        return

    global RP_CURRENT_NAME, RP_CURRENT_SINCE
    action_lower = (action or "").lower().strip()
    now = datetime.now(timezone.utc)

    if action_lower == "info":
        if RP_CURRENT_NAME is None:
            channel = resolve_rp_channel(ctx.guild)
            if isinstance(channel, discord.TextChannel):
                RP_CURRENT_NAME = channel.name

        current_name = RP_CURRENT_NAME or "Not set yet"
        if RP_CURRENT_SINCE is None:
            await ctx.send(
                f"Current RP: **{current_name}**\n"
                f"Duration: **Unknown (tracking starts after first {PREFIX}rp change)**"
            )
            return

        duration = format_elapsed(now - RP_CURRENT_SINCE)
        await ctx.send(f"Current RP: **{current_name}**\nDuration: **{duration}**")
        return

    if action_lower == "history":
        if not RP_CHANGE_HISTORY:
            await ctx.send("No RP history yet. Change RP at least once to start tracking.")
            return

        lines: list[str] = []
        for index, (name, changed_at) in enumerate(reversed(list(RP_CHANGE_HISTORY)), start=1):
            age = format_elapsed(now - changed_at)
            lines.append(f"{index}. {name} ({age} ago)")

        history_embed = discord.Embed(
            title="RP History",
            description="\n".join(lines),
            color=discord.Color.blurple(),
            timestamp=now,
        )
        history_embed.set_footer(text=f"Showing last {len(lines)} RP change(s)")
        await ctx.send(embed=history_embed)
        return

    if action_lower == "change":
        if option:
            result = await change_rp_channel(ctx.guild, str(ctx.author), ctx.author.id, option)
            await ctx.send(result)
            return

        await ctx.send("Select an RP mode:", view=RPChannelView())
        return

    await ctx.send(f"Usage: `{PREFIX}rp change`, `{PREFIX}rp info`, or `{PREFIX}rp history`.")


@bot.command(name="warn")
@main_server_role_required(WARN_COMMAND_ROLE_ID)
async def warn(ctx: commands.Context, target: str, *, reason: str) -> None:
    if ctx.guild is None:
        await ctx.send("This command can only be used in a server.")
        return

    user_id = parse_user_id(target)
    if user_id is None:
        await ctx.send("Use a user mention or numeric user ID.")
        return

    member = ctx.guild.get_member(user_id)
    target_user: discord.abc.User | None = member
    if target_user is None:
        try:
            target_user = await bot.fetch_user(user_id)
        except discord.NotFound:
            await ctx.send("User was not found.")
            return
        except discord.HTTPException:
            await ctx.send("I could not fetch that user right now.")
            return

    warning_data = load_warning_data()
    case_id = int(warning_data.get("next_case_id", 1))
    warning_data["next_case_id"] = case_id + 1

    now = datetime.now(timezone.utc)
    expires = now + timedelta(days=WARN_DURATION_DAYS)
    warning_data["warnings"].append(
        {
            "case_id": case_id,
            "guild_id": ctx.guild.id,
            "user_id": user_id,
            "moderator_id": ctx.author.id,
            "reason": reason,
            "issued_at": now.isoformat(),
            "expires_at": expires.isoformat(),
            "voided": False,
        }
    )
    save_warning_data(warning_data)

    active_warning_count = count_active_warnings(warning_data, ctx.guild.id, user_id, now)

    remaining_warnings = max(WARN_MAX_COUNT - active_warning_count, 0)

    mention_text = member.mention if member else f"<@{user_id}>"

    # DM a warning notification on every warn action.
    warn_notice_embed = discord.Embed(
        title="SLCRP | Salt Lake City RP | Notification",
        description=f"Hey, {mention_text}! You have been warned for: **{reason}**",
        color=discord.Color.blue(),
    )
    warn_notice_embed.add_field(name="Case ID", value=str(case_id), inline=False)
    warn_notice_embed.add_field(
        name="Warnings",
        value=f"You have **{active_warning_count}** warning(s)",
        inline=False,
    )
    warn_notice_embed.add_field(
        name="Expires",
        value=discord.utils.format_dt(expires, style="F"),
        inline=False,
    )
    warn_notice_embed.set_footer(
        text=(
            "Sent from SLCRP | Salt Lake City RP - "
            f"{datetime.now().strftime('%m/%d/%Y %I:%M %p')}"
        )
    )

    try:
        await target_user.send(embed=warn_notice_embed)
    except (discord.Forbidden, discord.HTTPException):
        pass

    escalation_action = "No immediate action."
    action_error = None

    if active_warning_count >= 5:
        try:
            await ctx.guild.ban(target_user, reason=f"5/5 warnings | {reason}", delete_message_days=0)
            escalation_action = "Permanent ban applied (5/5 warnings)."
        except (discord.Forbidden, discord.HTTPException):
            action_error = "I could not apply the permanent ban due to permissions or API error."
    elif active_warning_count == 4:
        unban_at = now + timedelta(days=7)
        try:
            await ctx.guild.ban(target_user, reason=f"4/5 warnings | 7-day ban | {reason}", delete_message_days=0)
            add_temp_ban_record(ctx.guild.id, user_id, case_id, unban_at, reason)
            escalation_action = "7-day ban applied (4/5 warnings)."
        except (discord.Forbidden, discord.HTTPException):
            action_error = "I could not apply the 7-day ban due to permissions or API error."
    elif active_warning_count == 3:
        unban_at = now + timedelta(days=1)
        try:
            await ctx.guild.ban(target_user, reason=f"3/5 warnings | 1-day ban | {reason}", delete_message_days=0)
            add_temp_ban_record(ctx.guild.id, user_id, case_id, unban_at, reason)
            escalation_action = "1-day ban applied (3/5 warnings)."
        except (discord.Forbidden, discord.HTTPException):
            action_error = "I could not apply the 1-day ban due to permissions or API error."
    elif active_warning_count == 2:
        if member is None:
            action_error = "User is not currently in the server, so I could not kick them."
        else:
            try:
                await member.kick(reason=f"2/5 warnings | {reason}")
                escalation_action = "Kick applied (2/5 warnings)."
            except (discord.Forbidden, discord.HTTPException):
                action_error = "I could not kick the user due to permissions or API error."

    warning_ladder_embed = discord.Embed(
        title="SLCRP | Salt Lake City RP | Warning Ladder",
        description=(
            "**1 Warning:** No immediate action.\n"
            "**2 Warnings:** Kick from Discord.\n"
            "**3 Warnings:** 1 day ban.\n"
            "**4 Warnings:** 7 days ban.\n"
            "**5 Warnings:** Permanent ban."
        ),
        color=discord.Color.blue(),
    )
    warning_ladder_embed.add_field(
        name="Current Warning Count",
        value=f"{active_warning_count}/{WARN_MAX_COUNT}",
        inline=False,
    )
    warning_ladder_embed.set_footer(text="Sent from SLCRP | Salt Lake City RP")
    try:
        await target_user.send(embed=warning_ladder_embed)
    except (discord.Forbidden, discord.HTTPException):
        pass

    mod_mention = ctx.author.mention if isinstance(ctx.author, discord.Member) else str(ctx.author)
    warn_embed = discord.Embed(
        title="SLCRP | Warn Log System",
        color=discord.Color.blue(),
    )
    warn_embed.add_field(name="User", value=mention_text, inline=True)
    warn_embed.add_field(name="Moderator", value=mod_mention, inline=True)
    warn_embed.add_field(name="Reason", value=reason[:1024], inline=True)
    warn_embed.add_field(name="User ID", value=str(user_id), inline=True)
    warn_embed.add_field(name="Moderator ID", value=str(ctx.author.id), inline=True)
    warn_embed.add_field(name="Case ID", value=str(case_id), inline=True)
    warn_embed.add_field(name="Expires", value=discord.utils.format_dt(expires, style="F"), inline=False)
    warn_embed.set_footer(text="SLCRP | Salt Lake City RP | Warn System")

    log_channel = ctx.guild.get_channel(WARN_LOG_CHANNEL_ID) or bot.get_channel(WARN_LOG_CHANNEL_ID)
    if isinstance(log_channel, discord.TextChannel):
        await log_channel.send(embed=warn_embed)
        confirm_embed = discord.Embed(
            title="SLCRP | Salt Lake City RP | Warning System",
            description=(
                f"[SUCCESS] Successfully warned user: {mention_text}.\n\n"
                f"Reason: {reason}\n\n"
                f"They have **{active_warning_count}/{WARN_MAX_COUNT}** warning(s).\n"
                f"They can receive **{remaining_warnings}** more warning(s).\n\n"
                f"Action: {escalation_action}\n\n"
                f"Case ID: {case_id}"
            ),
            color=discord.Color.blue(),
        )
        if action_error:
            confirm_embed.add_field(name="Action Error", value=action_error, inline=False)
        confirm_embed.set_footer(text="SLCRP | Salt Lake City RP | Warn System")
        await ctx.send(embed=confirm_embed)
        return

    await ctx.send("Warn saved, but I could not access the configured log channel.")


@bot.command(name="unwarn")
@main_server_role_required(WARN_COMMAND_ROLE_ID)
async def unwarn(ctx: commands.Context, case_id: int, *, reason: str) -> None:
    if ctx.guild is None:
        await ctx.send("This command can only be used in a server.")
        return

    warning_data = load_warning_data()
    target_warning = None
    for entry in warning_data.get("warnings", []):
        if int(entry.get("guild_id", 0)) != ctx.guild.id:
            continue
        if int(entry.get("case_id", 0)) == case_id:
            target_warning = entry
            break

    if target_warning is None:
        await ctx.send("That case ID was not found in this server.")
        return

    if target_warning.get("voided", False):
        await ctx.send("That case is already unwarned.")
        return

    now = datetime.now(timezone.utc)
    target_warning["voided"] = True
    target_warning["voided_reason"] = reason
    target_warning["voided_by"] = ctx.author.id
    target_warning["voided_at"] = now.isoformat()
    save_warning_data(warning_data)

    user_id = int(target_warning.get("user_id", 0))
    original_reason = str(target_warning.get("reason", "No reason stored."))
    member = ctx.guild.get_member(user_id)
    mention_text = member.mention if member else f"<@{user_id}>"

    active_warning_count = count_active_warnings(warning_data, ctx.guild.id, user_id, now)
    remaining_warnings = max(WARN_MAX_COUNT - active_warning_count, 0)

    mod_mention = ctx.author.mention if isinstance(ctx.author, discord.Member) else str(ctx.author)
    unwarn_embed = discord.Embed(
        title="SLCRP | Unwarn Log System",
        color=discord.Color.blue(),
    )
    unwarn_embed.add_field(name="User", value=mention_text, inline=True)
    unwarn_embed.add_field(name="Moderator", value=mod_mention, inline=True)
    unwarn_embed.add_field(name="Unwarn Reason", value=reason[:1024], inline=True)
    unwarn_embed.add_field(name="User ID", value=str(user_id), inline=True)
    unwarn_embed.add_field(name="Moderator ID", value=str(ctx.author.id), inline=True)
    unwarn_embed.add_field(name="Case ID", value=str(case_id), inline=True)
    unwarn_embed.add_field(name="Original Warn Reason", value=original_reason[:1024], inline=False)
    unwarn_embed.set_footer(text="SLCRP | Salt Lake City RP | Unwarn System")

    log_channel = ctx.guild.get_channel(WARN_LOG_CHANNEL_ID) or bot.get_channel(WARN_LOG_CHANNEL_ID)
    if isinstance(log_channel, discord.TextChannel):
        await log_channel.send(embed=unwarn_embed)
        confirm_embed = discord.Embed(
            title="SLCRP | Salt Lake City RP | Unwarn System",
            description=(
                f"[SUCCESS] Successfully unwarned user: {mention_text}.\n\n"
                f"Reason: {reason}\n\n"
                f"They have **{active_warning_count}/{WARN_MAX_COUNT}** warning(s).\n"
                f"They can receive **{remaining_warnings}** more warning(s).\n\n"
                f"Case ID: {case_id}"
            ),
            color=discord.Color.blue(),
        )
        confirm_embed.set_footer(text="SLCRP | Salt Lake City RP | Unwarn System")
        await ctx.send(embed=confirm_embed)
        return


# Ticket System Emojis
TICKET_EMOJIS = {
    "Valid Reason": "<:slcrpproperreason:1494794953098788984>",
    "Swearing": "<:slcrpnoswearing:1494798750399467560>",
    "Pinging": "<:slcrpnopinging:1494799027231784970>",
    "Patience": "<:slcrpwaitforstaff:1494795354758057984>",
    "One Ticket Rule": "<:slcrponeticket:1494799464286781481>",
    "NSFW Content": "<:slcrpnoNSFW:1494799860673810443>",
    "Respect Staff": "<:slcrprespectstaff:1494795914685055037>",
    "Proper Formatting": "<:slcrpfilloutformat:1494794592183128215>",
    "Time Limit": "<:slcrptimelimit:1494796181157449861>",
    "Language": "<:slcrpLanguage:1494796566911783112>",
    "Honesty": "<:slcrphonesty:1494797445308354661>",
    "Remain Calm": "<:slcrpremaincalm:1494797865032351945>",
}

TICKET_RULES_REWORDED = {
    "Valid Reason": "Open tickets only for real issues and include enough context so staff can help quickly.",
    "Swearing": "Keep language clean and professional. Abusive wording can lead to closure and moderation action.",
    "Pinging": "Avoid unnecessary staff or role pings in tickets. Use clear details instead of repeated mentions.",
    "One Ticket Rule": "Please keep one open ticket per issue. Duplicate or multi-topic tickets may be closed.",
    "NSFW Content": "NSFW material is not allowed in tickets under any circumstance and can result in a ban.",
    "Patience": "Allow staff reasonable time to respond. Repeated bumping slows handling and may cause closure.",
    "Respect Staff": "Treat everyone respectfully during review. Harassment or hostility may end support.",
    "Proper Formatting": "Provide readable, complete information so your case can be reviewed without delays.",
    "Time Limit": "If a ticket is inactive for 12+ hours, it may be closed until you are ready to continue.",
    "Language": "Use English in tickets so all available staff can accurately review and respond.",
    "Honesty": "Share accurate details and evidence. False or misleading claims can lead to warnings.",
    "Remain Calm": "Stay calm while your case is reviewed. Aggressive behavior can result in closure.",
}


class TicketInfoModal(discord.ui.Modal):
    """Modal shown when a ticket type is selected."""

    def __init__(self, ticket_type: str) -> None:
        super().__init__(title="Ticket Information")
        self.ticket_type = ticket_type
        self.topic = discord.ui.TextInput(
            label="Topic",
            placeholder="Brief description...",
            style=discord.InputTextStyle.short,
            required=True,
            max_length=200,
        )
        self.details = discord.ui.TextInput(
            label="Details",
            placeholder="Describe in detail...",
            style=discord.InputTextStyle.long,
            required=True,
            min_length=10,
            max_length=2000,
        )
        self.add_item(self.topic)
        self.add_item(self.details)

    async def callback(self, interaction: discord.Interaction) -> None:
        await self.on_submit(interaction)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        guild = interaction.guild
        user = interaction.user
        if not guild:
            await interaction.response.send_message("This can only be used inside a server.", ephemeral=True)
            return

        if not isinstance(user, discord.Member):
            await interaction.response.send_message("Could not resolve your member data in this server.", ephemeral=True)
            return

        routing = TICKET_TYPE_ROUTING.get(self.ticket_type)
        if routing is None:
            await interaction.response.send_message("This ticket type is not configured yet.", ephemeral=True)
            return

        category_id = int(routing["category_id"])
        ping_template = str(routing["ping_text"])
        target_category = guild.get_channel(category_id)
        if not isinstance(target_category, discord.CategoryChannel):
            await interaction.response.send_message("Ticket category is missing or invalid. Contact staff.", ephemeral=True)
            return

        existing_ticket = find_open_ticket_for_user(guild, user.id)
        if existing_ticket is not None:
            await interaction.response.send_message(
                f"You already have an open ticket: {existing_ticket.mention}",
                ephemeral=True,
            )
            return

        now = datetime.now(timezone.utc)
        timestamp_str = now.strftime("%Y-%m-%d, %H:%M:%S")

        embed = discord.Embed(
            title=f"{self.ticket_type} Ticket Opened",
            description=(
                f"Hello, {user.mention}!\n\n"
                "Your ticket has been opened, thank you for reaching out.\n"
                "Someone from our team will be in touch with you shortly.\n\n"
                "⚠️ **Note: all messages will be recorded and saved to our ticket "
                "transcript, do not share any sensitive information.**"
            ),
            color=discord.Color.blue(),
        )
        topic_text = (self.topic.value or "").strip()
        details_text = (self.details.value or "").strip()
        embed.add_field(name="📋 Topic", value=topic_text[:1024] if topic_text else "No topic provided.", inline=False)
        embed.add_field(name="📋 Details", value=details_text[:1024] if details_text else "No details provided.", inline=False)
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        embed.set_footer(text=f"Ticket Opened By: {user.display_name} • {timestamp_str}")

        try:
            safe_name = re.sub(r"[^a-z0-9-]", "-", user.display_name.lower())
            safe_name = re.sub(r"-+", "-", safe_name).strip("-") or "user"
            channel_name = f"ticket-{safe_name[:80]}"

            ticket_channel = await guild.create_text_channel(
                name=channel_name[:95],
                category=target_category,
                reason=f"Support ticket ({self.ticket_type}) opened by {user}",
                topic=f"ticket_owner_id={user.id};ticket_type={self.ticket_type}",
            )

            # Ensure requester can always access their own ticket channel.
            await ticket_channel.set_permissions(
                user,
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                reason="Grant requester access to ticket channel",
            )

            ping_text = ping_template.format(user_mention=user.mention)
            await ticket_channel.send(
                content=ping_text,
                embed=embed,
                allowed_mentions=discord.AllowedMentions(roles=True, users=True, everyone=True),
            )
            await interaction.response.send_message(
                f"Your ticket has been created: {ticket_channel.mention}",
                ephemeral=True,
            )
        except (discord.Forbidden, discord.HTTPException) as e:
            await interaction.response.send_message(
                f"Could not create ticket: {e}",
                ephemeral=True,
            )


class TicketRequestView(discord.ui.View):
    """Legacy view kept for persistence compatibility."""

    def __init__(self):
        super().__init__(timeout=None)


class CloseRequestDenyReasonModal(discord.ui.Modal):
    def __init__(self, parent_view: "CloseRequestView") -> None:
        super().__init__(title="Deny Ticket Close Request")
        self.parent_view = parent_view
        self.reason = discord.ui.TextInput(
            label="Reason",
            placeholder="Enter reason for denying the ticket close request...",
            required=True,
            max_length=500,
            style=discord.InputTextStyle.long,
        )
        self.add_item(self.reason)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if self.parent_view.handled:
            await interaction.response.send_message("This close request is already handled.", ephemeral=True)
            return

        guild = interaction.guild
        channel = interaction.channel
        if guild is None or not isinstance(channel, discord.TextChannel):
            await interaction.response.send_message("This action can only be used in a server text channel.", ephemeral=True)
            return

        if interaction.user.id != self.parent_view.ticket_owner_id:
            await interaction.response.send_message("Only the ticket owner can deny this close request.", ephemeral=True)
            return

        self.parent_view.handled = True
        self.parent_view.disable_all_items()

        denial_reason = str(self.reason).strip()
        updated_embed = discord.Embed(
            title="Ticket Close Requested - Denied",
            description=(
                f"Hello {self.parent_view.ticket_owner_mention}!\n"
                f"{self.parent_view.requested_by_mention} requested ticket closure, but the request was denied."
            ),
            color=discord.Color.blue(),
            timestamp=datetime.now(timezone.utc),
        )
        updated_embed.add_field(name="Denied Reason", value=denial_reason[:1024], inline=False)

        await interaction.response.defer(ephemeral=True)
        request_message: discord.Message | None = None
        if self.parent_view.request_message_id is not None:
            try:
                request_message = await channel.fetch_message(self.parent_view.request_message_id)
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                request_message = None

        if request_message is not None:
            try:
                await request_message.edit(embed=updated_embed, view=self.parent_view)
            except (discord.Forbidden, discord.HTTPException):
                pass

        await channel.send(
            content=f"{self.parent_view.requested_by_mention}",
            allowed_mentions=discord.AllowedMentions(users=True),
        )
        await interaction.followup.send("Close request denied and staff was notified.", ephemeral=True)


class CloseRequestView(discord.ui.View):
    def __init__(
        self,
        *,
        requested_by_id: int,
        requested_by_mention: str,
        ticket_owner_id: int,
        ticket_owner_mention: str,
    ) -> None:
        super().__init__(timeout=None)
        self.requested_by_id = requested_by_id
        self.requested_by_mention = requested_by_mention
        self.ticket_owner_id = ticket_owner_id
        self.ticket_owner_mention = ticket_owner_mention
        self.request_message_id: int | None = None
        self.handled = False

    def disable_all_items(self) -> None:
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True

    @discord.ui.button(label="Accept", style=discord.ButtonStyle.green, custom_id="ticket_close_request_accept")
    async def accept(self, button: discord.ui.Button, interaction: discord.Interaction) -> None:
        if self.handled:
            await interaction.response.send_message("This close request is already handled.", ephemeral=True)
            return

        if interaction.user.id != self.ticket_owner_id:
            await interaction.response.send_message("Only the ticket owner can accept this close request.", ephemeral=True)
            return

        if not isinstance(interaction.channel, discord.TextChannel) or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("This action can only be used in a server text channel.", ephemeral=True)
            return

        self.handled = True
        self.disable_all_items()
        await interaction.response.edit_message(view=self)
        try:
            await close_ticket_channel(interaction.channel, interaction.user, "Close request Accepted")
        except (discord.Forbidden, discord.HTTPException):
            self.handled = False
            await interaction.followup.send("I could not close this ticket due to missing permissions.", ephemeral=True)

    @discord.ui.button(label="Deny", style=discord.ButtonStyle.red, custom_id="ticket_close_request_deny")
    async def deny(self, button: discord.ui.Button, interaction: discord.Interaction) -> None:
        if self.handled:
            await interaction.response.send_message("This close request is already handled.", ephemeral=True)
            return

        if interaction.user.id != self.ticket_owner_id:
            await interaction.response.send_message("Only the ticket owner can deny this close request.", ephemeral=True)
            return

        await interaction.response.send_modal(CloseRequestDenyReasonModal(self))


@bot.command(name="closeticket")
@main_server_role_required(TICKET_COMMAND_ROLE_ID)
async def closeticket(ctx: commands.Context) -> None:
    if ctx.guild is None or not isinstance(ctx.channel, discord.TextChannel) or not isinstance(ctx.author, discord.Member):
        await ctx.send("This command can only be used in a server text channel.")
        return

    if not is_ticket_channel(ctx.channel):
        await ctx.send("This command can only be used in a ticket channel.")
        return

    prompt = await ctx.send("The next message you send will be used as the ticket close reason.")

    def reason_check(message: discord.Message) -> bool:
        return (
            message.author.id == ctx.author.id
            and message.channel.id == ctx.channel.id
            and not message.author.bot
        )

    try:
        reason_msg = await bot.wait_for("message", check=reason_check, timeout=180)
        reason = reason_msg.content.strip() or "No reason provided."
    except asyncio.TimeoutError:
        await ctx.send("Timed out waiting for a close reason.")
        return

    try:
        await prompt.delete()
    except (discord.Forbidden, discord.HTTPException):
        pass

    try:
        await close_ticket_channel(ctx.channel, ctx.author, reason)
    except (discord.Forbidden, discord.HTTPException):
        await ctx.send("I could not close this ticket due to missing permissions.")


@bot.command(name="moveticket")
@main_server_role_required(TICKET_COMMAND_ROLE_ID)
async def moveticket(ctx: commands.Context, *, ticket_type: str) -> None:
    if ctx.guild is None or not isinstance(ctx.channel, discord.TextChannel):
        await ctx.send("This command can only be used in a server text channel.")
        return

    if not is_ticket_channel(ctx.channel):
        await ctx.send("This command can only be used in a ticket channel.")
        return

    # Find ticket type (case-insensitive)
    target_type: str | None = None
    search_lower = ticket_type.lower().strip()
    for ticket_type_key in TICKET_TYPE_ROUTING.keys():
        if ticket_type_key.lower() == search_lower:
            target_type = ticket_type_key
            break

    if target_type is None:
        available = ", ".join(TICKET_TYPE_ROUTING.keys())
        await ctx.send(f"Ticket type not found. Available types: {available}")
        return

    routing = TICKET_TYPE_ROUTING[target_type]
    category_id = routing.get("category_id")
    if not isinstance(category_id, int):
        await ctx.send("Invalid category ID in routing config.")
        return

    target_category = ctx.guild.get_channel(category_id)
    if not isinstance(target_category, discord.CategoryChannel):
        await ctx.send("Target category not found in this server.")
        return

    try:
        await ctx.channel.edit(category=target_category, reason=f"Ticket moved by {ctx.author}")
        await ctx.send(f"Moved ticket to **{target_type}** category.")
    except (discord.Forbidden, discord.HTTPException):
        await ctx.send("I could not move this ticket due to missing permissions.")


@bot.command(name="transcript")
@commands.has_permissions(manage_channels=True)
async def transcript(ctx: commands.Context, ticket_id: str) -> None:
    if ctx.guild is None:
        await ctx.send("This command can only be used in a server.")
        return

    if not ticket_id.isdigit():
        await ctx.send("Usage: `?transcript <ticket ID>`")
        return

    parsed_ticket_id = int(ticket_id)
    filename = find_saved_transcript_filename(parsed_ticket_id)
    if filename is None:
        await ctx.send("No saved transcript was found for that ticket ID.")
        return

    transcript_path = os.path.join(TICKET_TRANSCRIPTS_DIR, filename)
    if not os.path.isfile(transcript_path):
        await ctx.send("Transcript file is missing on disk.")
        return

    try:
        await ctx.send(file=discord.File(transcript_path, filename=filename))
    except (discord.Forbidden, discord.HTTPException):
        await ctx.send("I could not send that transcript file.")


@bot.command(name="closerequest")
@main_server_role_required(TICKET_COMMAND_ROLE_ID)
async def closerequest(ctx: commands.Context) -> None:
    if ctx.guild is None or not isinstance(ctx.channel, discord.TextChannel):
        await ctx.send("This command can only be used in a server text channel.")
        return

    if not is_ticket_channel(ctx.channel):
        await ctx.send("This command can only be used in a ticket channel.")
        return

    owner_id, _ = parse_ticket_topic_metadata(ctx.channel.topic)
    ticket_owner = ctx.guild.get_member(owner_id) if owner_id else None
    if ticket_owner is None:
        await ctx.send("I could not find the ticket owner for this ticket.")
        return

    close_request_embed = discord.Embed(
        title="Ticket Close requested",
        description=(
            f"Hello {ticket_owner.mention} {ctx.author.mention} has requested you to close the ticket. "
            "You may click deny and enter the reason and I will notify staff!"
        ),
        color=discord.Color.blue(),
        timestamp=datetime.now(timezone.utc),
    )

    request_view = CloseRequestView(
        requested_by_id=ctx.author.id,
        requested_by_mention=ctx.author.mention,
        ticket_owner_id=ticket_owner.id,
        ticket_owner_mention=ticket_owner.mention,
    )

    request_message = await ctx.send(
        content=ticket_owner.mention,
        embed=close_request_embed,
        view=request_view,
        allowed_mentions=discord.AllowedMentions(users=True),
    )
    request_view.request_message_id = request_message.id





@bot.command(name="ssu")
@commands.has_permissions(manage_guild=True)
async def ssu(ctx: commands.Context) -> None:
    embed = discord.Embed(
        title="Salt Lake City RP Server Startup",
        description=(
            "We're excited to announce that the Salt lake city RP server is now online and ready for you to join! "
            "Get ready for a Great RP in SLCR! Have a great time with our community members! "
            "And our Great staff team!\n\n"
            "**Steps to Join:**\n"
            "1. Join ER:LC\n"
            "2. Go to Menu > Servers > Join by Code\n"
            "3. Enter SLCRPS and start playing!"
        ),
        color=discord.Color.blue(),
    )
    embed.set_footer(text=f"Sent by {ctx.author}")
    await ctx.send(content="<@&1495572658199462018>", embed=embed, allowed_mentions=discord.AllowedMentions(roles=True))


@bot.command(name="ssd")
@commands.has_permissions(manage_guild=True)
async def ssd(ctx: commands.Context) -> None:
    embed = discord.Embed(
        title="Salt Lake City RP Server Shutdown",
        description=(
            "Unfortunately, the server has shut down temporarily. "
            "Please give us a bit to get the server back up and running thanks!"
        ),
        color=discord.Color.blue(),
    )
    embed.set_footer(text=f"Sent by {ctx.author}")
    await ctx.send(content="<@&1495572658199462018>", embed=embed, allowed_mentions=discord.AllowedMentions(roles=True))


@bot.command(name="nrs")
@main_server_role_required(ROLE_MANAGER_COMMAND_ROLE_ID)
async def nrs(ctx: commands.Context, member: discord.Member) -> None:
    if not isinstance(ctx.author, discord.Member) or ctx.guild is None:
        await ctx.send("This command can only be used in a server.")
        return

    staff_board_role = ctx.guild.get_role(BASE_ROLE_ID)
    if staff_board_role is None:
        await ctx.send(f"Staff Board role `{BASE_ROLE_ID}` was not found in this server.")
        return

    roles_to_save = [
        role.id
        for role in member.roles
        if role != ctx.guild.default_role and role.position >= staff_board_role.position
    ]
    if not roles_to_save:
        await ctx.send("That user has no roles equal to or above the Staff Board role.")
        return

    data = load_saved_roles()
    guild_data = data.setdefault(str(ctx.guild.id), {})
    guild_data[str(member.id)] = roles_to_save
    save_saved_roles(data)

    bot_member = ctx.guild.get_member(bot.user.id) if bot.user else None
    if bot_member is None:
        await ctx.send("I could not verify my server role hierarchy.")
        return

    removable_roles = [
        role
        for role in member.roles
        if role != ctx.guild.default_role
        and not role.managed
        and role.position >= staff_board_role.position
        and role < bot_member.top_role
    ]

    if not removable_roles:
        await ctx.send("Roles were saved, but I could not remove any due to role hierarchy.")
        return

    await member.remove_roles(*removable_roles, reason=f"nrs used by {ctx.author}", atomic=False)
    result_embed = discord.Embed(
        title="NRS Complete",
        description=(
            f"Saved **{len(roles_to_save)}** role(s) equal to or above **{staff_board_role.name}**\n"
            f"Removed **{len(removable_roles)}** role(s) from {member.mention}"
        ),
        color=discord.Color.blue(),
    )
    result_embed.set_footer(text=f"Requested by {ctx.author}")
    await ctx.send(embed=result_embed)


@bot.command(name="sr")
async def sr(ctx: commands.Context, member: discord.Member | None = None) -> None:
    if ctx.guild is None or not isinstance(ctx.author, discord.Member):
        await ctx.send("This command can only be used in a server.")
        return

    target_member = member or ctx.author
    member_role_ids = {role.id for role in ctx.author.roles}
    if target_member.id != ctx.author.id and ROLE_MANAGER_COMMAND_ROLE_ID not in member_role_ids:
        await ctx.send(f"You need the **{role_name_text(ROLE_MANAGER_COMMAND_ROLE_ID, ctx.guild)}** role to save another member's roles.")
        return

    staff_board_role = ctx.guild.get_role(BASE_ROLE_ID)
    if staff_board_role is None:
        await ctx.send(f"Staff Board role `{BASE_ROLE_ID}` was not found in this server.")
        return

    roles_to_save = [
        role.id
        for role in target_member.roles
        if role != ctx.guild.default_role and role.position >= staff_board_role.position
    ]
    if not roles_to_save:
        await ctx.send("No roles equal to or above the Staff Board role were found to save.")
        return

    data = load_saved_roles()
    guild_data = data.setdefault(str(ctx.guild.id), {})
    guild_data[str(target_member.id)] = roles_to_save
    save_saved_roles(data)

    await ctx.send(
        f"Saved **{len(roles_to_save)}** role(s) for {target_member.mention}. Use `{PREFIX}gar {target_member.mention}` to restore them after unban/rejoin."
    )


@bot.command(name="gar")
@main_server_role_required(ROLE_MANAGER_COMMAND_ROLE_ID)
async def gar(ctx: commands.Context, member: discord.Member) -> None:
    if ctx.guild is None:
        await ctx.send("This command can only be used in a server.")
        return

    data = load_saved_roles()
    guild_data = data.get(str(ctx.guild.id), {})
    saved_role_ids = guild_data.get(str(member.id), [])
    if not saved_role_ids:
        await ctx.send("No saved roles were found for that user.")
        return

    bot_member = ctx.guild.get_member(bot.user.id) if bot.user else None
    if bot_member is None:
        await ctx.send("I could not verify my server role hierarchy.")
        return

    addable_roles = []
    for role_id in saved_role_ids:
        role = ctx.guild.get_role(role_id)
        if role is None:
            continue
        if role.managed:
            continue
        if role >= bot_member.top_role:
            continue
        if role in member.roles:
            continue
        addable_roles.append(role)

    if not addable_roles:
        await ctx.send("I could not add any saved roles (missing roles or role hierarchy issue).")
        return

    await member.add_roles(*addable_roles, reason=f"gar used by {ctx.author}", atomic=False)
    result_embed = discord.Embed(
        title="GAR Complete",
        description=f"Restored **{len(addable_roles)}** saved role(s) to {member.mention}.",
        color=discord.Color.blue(),
    )
    result_embed.set_footer(text=f"Requested by {ctx.author}")
    await ctx.send(embed=result_embed)


@bot.command(name="lockdown")
@main_server_role_required(WARN_COMMAND_ROLE_ID)
@commands.bot_has_permissions(manage_channels=True)
async def lockdown(ctx: commands.Context, target: str) -> None:
    if ctx.guild is None:
        await ctx.send("This command can only be used in a server.")
        return

    everyone = ctx.guild.default_role

    async def lock_one(channel: discord.abc.GuildChannel) -> bool:
        try:
            if isinstance(channel, (discord.TextChannel, discord.ForumChannel)):
                await channel.set_permissions(
                    everyone,
                    send_messages=False,
                    reason=f"Lockdown by {ctx.author}",
                )
                return True
            if isinstance(channel, (discord.VoiceChannel, discord.StageChannel)):
                await channel.set_permissions(
                    everyone,
                    connect=False,
                    reason=f"Lockdown by {ctx.author}",
                )
                return True
        except (discord.Forbidden, discord.HTTPException):
            return False
        return False

    if target.lower().strip() == "all":
        changed = 0
        failed = 0
        for channel in ctx.guild.channels:
            locked = await lock_one(channel)
            if locked:
                changed += 1
            else:
                failed += 1

        await ctx.send(
            f"Lockdown complete. Locked **{changed}** channel(s)."
            + (f" Failed on **{failed}** channel(s)." if failed else "")
        )
        return

    if not target.isdigit():
        await ctx.send(f"Usage: `{PREFIX}lockdown <channel_id>` or `{PREFIX}lockdown all`.")
        return

    channel = ctx.guild.get_channel(int(target))
    if channel is None:
        await ctx.send("Channel ID not found in this server.")
        return

    if await lock_one(channel):
        await ctx.send(f"Locked {channel.mention}.")
    else:
        await ctx.send("I could not lock that channel (permissions or channel type).")


@bot.command(name="swkick")
@main_server_role_required(ALL_SERVER_BAN_COMMAND_ROLE_ID)
async def swkick(ctx: commands.Context, target: str, *, reason: str = "No reason provided") -> None:
    user_id = parse_user_id(target)
    if user_id is None:
        await ctx.send("Use a user mention or numeric user ID.")
        return

    kicked_count = 0
    failed_count = 0
    not_in_count = 0
    for guild in bot.guilds:
        member = guild.get_member(user_id)
        if member is None:
            not_in_count += 1
            continue

        try:
            await member.kick(reason=f"All-server kick by {ctx.author}: {reason}")
            kicked_count += 1
        except (discord.Forbidden, discord.HTTPException):
            failed_count += 1

    summary = discord.Embed(
        title="SLCRP | Salt Lake City RP | All Server Kick System",
        color=discord.Color.blue(),
        description=(
            f"[SUCCESS] Processed all-server kick for <@{user_id}>.\n\n"
            f"Reason: {reason}\n\n"
            f"Kicked in: **{kicked_count}** server(s).\n"
            f"Not in server: **{not_in_count}** server(s)."
        ),
    )
    if failed_count:
        summary.add_field(name="Failed Servers", value=str(failed_count), inline=False)
    summary.set_footer(text=f"Requested by {ctx.author}")
    await ctx.send(embed=summary)


@bot.command(name="warnings")
@main_server_role_required(WARN_COMMAND_ROLE_ID)
async def warnings(ctx: commands.Context, target: str) -> None:
    if ctx.guild is None:
        await ctx.send("This command can only be used in a server.")
        return

    user_id = parse_user_id(target)
    if user_id is None:
        await ctx.send("Use a user mention or numeric user ID.")
        return

    warning_data = load_warning_data()
    now = datetime.now(timezone.utc)

    server_warnings = [
        entry
        for entry in warning_data.get("warnings", [])
        if int(entry.get("guild_id", 0)) == ctx.guild.id and int(entry.get("user_id", 0)) == user_id
    ]

    if not server_warnings:
        await ctx.send("No warnings found for that user in this server.")
        return

    active_count = count_active_warnings(warning_data, ctx.guild.id, user_id, now)
    lines: list[str] = []
    for entry in sorted(server_warnings, key=lambda item: int(item.get("case_id", 0)), reverse=True)[:10]:
        case_id = int(entry.get("case_id", 0))
        reason = str(entry.get("reason", "No reason stored."))
        reason = reason if len(reason) <= 120 else reason[:117] + "..."
        voided = bool(entry.get("voided", False))
        expires_raw = entry.get("expires_at")
        try:
            expires_at = datetime.fromisoformat(expires_raw) if expires_raw else now
        except ValueError:
            expires_at = now
        status = "Voided" if voided else ("Active" if expires_at > now else "Expired")
        lines.append(f"Case `{case_id}` - {status} - {reason}")

    embed = discord.Embed(
        title="Warning Lookup",
        color=discord.Color.blue(),
        description=f"User: <@{user_id}>\nActive warnings: **{active_count}/{WARN_MAX_COUNT}**",
    )
    embed.add_field(name="Recent Cases", value="\n".join(lines), inline=False)
    if len(server_warnings) > 10:
        embed.set_footer(text=f"Showing latest 10 of {len(server_warnings)} total cases")
    await ctx.send(embed=embed)


@bot.command(name="softban")
@main_server_role_required(WARN_COMMAND_ROLE_ID)
@commands.bot_has_permissions(ban_members=True)
async def softban(
    ctx: commands.Context,
    member: discord.Member,
    *,
    reason: str = "No reason provided",
) -> None:
    if ctx.guild is None:
        await ctx.send("This command can only be used in a server.")
        return

    try:
        await member.ban(reason=f"Softban by {ctx.author}: {reason}", delete_message_days=7)
        await ctx.guild.unban(member, reason=f"Softban unban by {ctx.author}")
    except (discord.Forbidden, discord.HTTPException):
        await ctx.send("I could not softban that user (permissions or API error).")
        return

    await ctx.send(f"Softbanned {member.mention}. Deleted up to 7 days of recent messages.")


@bot.command(name="timeout")
@main_server_role_required(WARN_COMMAND_ROLE_ID)
@commands.bot_has_permissions(moderate_members=True)
async def timeout_command(
    ctx: commands.Context,
    member: discord.Member,
    minutes: int,
    *,
    reason: str = "No reason provided",
) -> None:
    if minutes < 1:
        await ctx.send("Timeout minutes must be at least 1.")
        return

    timeout_until = datetime.now(timezone.utc) + timedelta(minutes=minutes)
    try:
        await member.timeout(timeout_until, reason=f"Timeout by {ctx.author}: {reason}")
    except (discord.Forbidden, discord.HTTPException):
        await ctx.send("I could not timeout that user (permissions or API error).")
        return

    await ctx.send(f"Timed out {member.mention} for **{minutes}** minute(s).")


def parse_mute_duration(duration_text: str) -> timedelta | None:
    match = re.fullmatch(r"(\d+)([mhdw])", duration_text.strip().lower())
    if not match:
        return None

    amount = int(match.group(1))
    unit = match.group(2)
    if amount < 1:
        return None

    if unit == "m":
        return timedelta(minutes=amount)
    if unit == "h":
        return timedelta(hours=amount)
    if unit == "d":
        return timedelta(days=amount)
    if unit == "w":
        return timedelta(weeks=amount)
    return None


@bot.command(name="mute")
@main_server_role_required(WARN_COMMAND_ROLE_ID)
@commands.bot_has_permissions(moderate_members=True)
async def mute_command(
    ctx: commands.Context,
    member: discord.Member,
    duration: str,
    *,
    reason: str = "No reason provided",
) -> None:
    delta = parse_mute_duration(duration)
    if delta is None:
        await ctx.send("Invalid duration. Use formats like `1m`, `1h`, `1d`, `1w`.")
        return

    timeout_until = datetime.now(timezone.utc) + delta
    max_timeout_until = datetime.now(timezone.utc) + timedelta(days=28)
    if timeout_until > max_timeout_until:
        await ctx.send("Mute duration cannot be longer than 28 days (Discord limit).")
        return

    try:
        await member.timeout(timeout_until, reason=f"Mute by {ctx.author}: {reason}")
    except (discord.Forbidden, discord.HTTPException):
        await ctx.send("I could not mute that user (permissions or API error).")
        return

    await ctx.send(f"Muted {member.mention} for **{duration.lower()}**.")


@bot.command(name="unmute")
@main_server_role_required(WARN_COMMAND_ROLE_ID)
@commands.bot_has_permissions(moderate_members=True)
async def unmute_command(
    ctx: commands.Context,
    member: discord.Member,
    *,
    reason: str = "No reason provided",
) -> None:
    try:
        await member.timeout(None, reason=f"Unmute by {ctx.author}: {reason}")
    except (discord.Forbidden, discord.HTTPException):
        await ctx.send("I could not unmute that user (permissions or API error).")
        return

    await ctx.send(f"Unmuted {member.mention}.")


@bot.command(name="setnickname")
@main_server_role_required(WARN_COMMAND_ROLE_ID)
@commands.bot_has_permissions(manage_nicknames=True)
async def setnickname(
    ctx: commands.Context,
    member: discord.Member,
    *,
    nickname: str,
) -> None:
    trimmed = nickname.strip()
    if not trimmed:
        await ctx.send("Nickname cannot be empty.")
        return

    if len(trimmed) > 32:
        await ctx.send("Nickname must be 32 characters or less.")
        return

    try:
        await member.edit(nick=trimmed, reason=f"Nickname changed by {ctx.author}")
    except (discord.Forbidden, discord.HTTPException):
        await ctx.send("I could not change that nickname (permissions or role hierarchy).")
        return

    await ctx.send(f"Set nickname for {member.mention} to `{trimmed}`.")


@bot.command(name="claim")
@main_server_role_required(TICKET_COMMAND_ROLE_ID)
async def claim(ctx: commands.Context) -> None:
    if ctx.guild is None or not isinstance(ctx.author, discord.Member):
        await ctx.send("This command can only be used in a server.")
        return

    has_booster = ctx.author.get_role(BOOSTER_ROLE_ID) is not None
    cooldown = timedelta(hours=12 if has_booster else 24)
    xp_min = 500 if has_booster else 200
    xp_max = 5000 if has_booster else 1000
    bonus_chance = 0.60 if has_booster else 0.20

    levels_data = load_levels_data()
    record = get_levels_user_record(levels_data, ctx.author.id)

    now = datetime.now(timezone.utc)
    last_claim = parse_iso_datetime(record.get("last_claim"))
    if last_claim is not None:
        next_claim_at = last_claim + cooldown
        if next_claim_at > now:
            remaining = next_claim_at - now
            await ctx.send(
                f"{ctx.author.mention} You can claim again in {format_duration_short(remaining)} "
                f"(next claim {discord.utils.format_dt(next_claim_at, style='R')})."
            )
            return

    gained_xp = random.randint(xp_min, xp_max)
    levelups_from_xp = apply_xp_to_level_record(record, gained_xp)

    bonus_levels = 0
    if random.random() < bonus_chance:
        bonus_levels = random.randint(1, 5)
        record["level"] = int(record.get("level", 0)) + bonus_levels

    record["last_claim"] = now.isoformat()
    save_levels_data(levels_data)

    total_levels_gained = levelups_from_xp + bonus_levels
    message = f"🥳{ctx.author.mention} You claimed {gained_xp} XP"
    if total_levels_gained > 0:
        message += f" And got {total_levels_gained} levels"
    await ctx.send(message)


@bot.command(name="levels")
async def levels(ctx: commands.Context, member: discord.Member | None = None) -> None:
    target = member or (ctx.author if isinstance(ctx.author, discord.Member) else None)
    if target is None:
        await ctx.send("Could not resolve user.")
        return

    levels_data = load_levels_data()
    record = get_levels_user_record(levels_data, target.id)
    level = int(record.get("level", 0))
    xp = int(record.get("xp", 0))
    xp_needed = xp_needed_for_next_level(level)

    all_entries = get_sorted_level_entries(levels_data)
    main_guild = bot.get_guild(MAIN_SERVER_GUILD_ID)
    sorted_entries = filter_entries_to_main_server_members(all_entries, main_guild)
    rank = None
    for index, (user_id, _entry_level, _entry_xp) in enumerate(sorted_entries, start=1):
        if user_id == target.id:
            rank = index
            break

    top_role_text = "No role"
    if isinstance(target, discord.Member):
        non_default_roles = [role for role in target.roles if role != target.guild.default_role]
        if non_default_roles:
            top_role_text = non_default_roles[-1].mention

    embed = discord.Embed(
        title=f"Levels of {target.display_name}",
        color=discord.Color.blue(),
    )
    embed.add_field(name="Role", value=top_role_text, inline=False)
    embed.add_field(name="Level", value=str(level), inline=False)
    embed.add_field(name="XP", value=f"{xp} / {xp_needed}", inline=False)
    embed.add_field(name="Level Leaderboard Rank", value=f"#{rank}" if rank else "Unranked", inline=False)
    if target.display_avatar:
        embed.set_thumbnail(url=target.display_avatar.url)
    await ctx.send(embed=embed)


@bot.command(name="lledaderboard", aliases=["levelsleaderboard", "lleaderboard"])
async def lledaderboard(ctx: commands.Context) -> None:
    levels_data = load_levels_data()
    all_entries = get_sorted_level_entries(levels_data)
    main_guild = bot.get_guild(MAIN_SERVER_GUILD_ID)
    entries = filter_entries_to_main_server_members(all_entries, main_guild)

    if main_guild is None:
        await ctx.send("Main server is not available right now. Try again in a moment.")
        return

    embed = build_levels_leaderboard_embed(entries=entries, page_index=0, page_size=20)

    if len(entries) <= 20:
        await ctx.send(embed=embed)
        return

    view = LevelsLeaderboardView(ctx.author.id, entries)
    await ctx.send(embed=embed, view=view)


@bot.command(name="reload")
async def reload_category(ctx: commands.Context, category: str = "") -> None:
    if ctx.guild is None or not isinstance(ctx.author, discord.Member):
        await ctx.send("This command can only be used in a server.")
        return

    member_role_ids = {role.id for role in ctx.author.roles}
    reload_role_id = get_reload_command_role_id()
    if reload_role_id not in member_role_ids:
        await ctx.send(f"You need the **{role_name_text(reload_role_id, ctx.guild)}** role to use this command.")
        return

    ALL_CATEGORIES = ["all", "settings", "xpsystem", "spam", "automod", "nsfwautomod", "invitesystem", "botsystem", "ticketsystam"]

    async def perform_full_runtime_reload() -> list[str]:
        results: list[str] = []
        ensure_levels_file()
        levels_data = load_levels_data()
        save_levels_data(levels_data)
        results.append(f"xpsystem: **{len(levels_data.get('users', {}))}** users")

        SPAM_AUTOMOD_STATE.clear()
        SPAM_AUTOMOD_RECENT_ACTION.clear()
        results.append("spam: cache cleared")

        normal_term_count = refresh_runtime_automod_terms()
        results.append(f"automod: **{normal_term_count}** normal terms")

        nsfw_term_count = refresh_runtime_nsfw_terms()
        results.append(f"nsfwautomod: **{nsfw_term_count}** nsfw terms")

        invite_count = refresh_runtime_approved_invites()
        results.append(f"invitesystem: **{invite_count}** invites")

        bot_count = refresh_runtime_approved_bots()
        results.append(f"botsystem: **{bot_count}** bots")

        settings_count = refresh_runtime_settings()
        results.append(f"settings: **{settings_count}** ticket rules")
        return results

    async def restart_process_for_code_reload() -> None:
        await ctx.send("Reloading bot process to apply latest code changes...")

        async def _restart_later() -> None:
            await asyncio.sleep(1.5)
            try:
                os.execv(sys.executable, [sys.executable, *sys.argv])
            except Exception as restart_error:
                print(f"Process restart via execv failed: {restart_error}. Falling back to clean exit.")
                os._exit(0)

        bot.loop.create_task(_restart_later())

    if not category.strip():
        await restart_process_for_code_reload()
        return

    normalized = category.strip().lower().lstrip(">")
    normalized = normalized.replace(" ", "").replace("-", "").replace("_", "")
    aliases = {
        "all": "all",
        "data": "all",
        "runtime": "all",
        "systems": "all",
        "settings": "settings",
        "config": "settings",
        "xpsystem": "xpsystem",
        "xp": "xpsystem",
        "spam": "spam",
        "automod": "automod",
        "nsfwautomod": "nsfwautomod",
        "nsfw": "nsfwautomod",
        "invitesystem": "invitesystem",
        "invite": "invitesystem",
        "invites": "invitesystem",
        "botsystem": "botsystem",
        "bot": "botsystem",
        "bots": "botsystem",
        "ticketsystam": "ticketsystam",
        "ticketsystem": "ticketsystam",
        "tickets": "ticketsystam",
    }
    normalized = aliases.get(normalized, normalized)
    started_at = time.perf_counter()
    details = ""

    try:
        if normalized == "all":
            results = await perform_full_runtime_reload()
            elapsed = time.perf_counter() - started_at
            embed = discord.Embed(
                title="All Systems Reloaded",
                description="\n".join(results),
                color=discord.Color.green(),
            )
            embed.add_field(name="Elapsed Time", value=f"{elapsed:.4f}s", inline=False)
            embed.set_footer(text="Cog Manager • Success")
            await ctx.send(embed=embed)
            return
        if normalized == "settings":
            settings_count = refresh_runtime_settings()
            details = f"Loaded runtime settings. Ticket rules: **{settings_count}**"
        elif normalized == "xpsystem":
            ensure_levels_file()
            levels_data = load_levels_data()
            save_levels_data(levels_data)
            details = f"Users tracked: **{len(levels_data.get('users', {}))}**"
        elif normalized == "spam":
            SPAM_AUTOMOD_STATE.clear()
            SPAM_AUTOMOD_RECENT_ACTION.clear()
            details = "Spam state cache cleared."
        elif normalized == "automod":
            normal_term_count = refresh_runtime_automod_terms()
            nsfw_term_count = refresh_runtime_nsfw_terms()
            raw_lines, ignored_lines = get_blacklist_file_stats(AUTOMOD_BLACKLIST_PATH)
            nsfw_raw_lines, nsfw_ignored_lines = get_blacklist_file_stats(AUTOMOD_NSFW_BLACKLIST_PATH)
            normal_path = os.path.realpath(AUTOMOD_BLACKLIST_PATH)
            nsfw_path = os.path.realpath(AUTOMOD_NSFW_BLACKLIST_PATH)
            normal_mtime = "unknown"
            nsfw_mtime = "unknown"
            if os.path.exists(AUTOMOD_BLACKLIST_PATH):
                normal_mtime = datetime.fromtimestamp(
                    os.path.getmtime(AUTOMOD_BLACKLIST_PATH),
                    tz=timezone.utc,
                ).strftime("%Y-%m-%d %H:%M:%S UTC")
            if os.path.exists(AUTOMOD_NSFW_BLACKLIST_PATH):
                nsfw_mtime = datetime.fromtimestamp(
                    os.path.getmtime(AUTOMOD_NSFW_BLACKLIST_PATH),
                    tz=timezone.utc,
                ).strftime("%Y-%m-%d %H:%M:%S UTC")

            normal_last_term = RUNTIME_AUTOMOD_TERMS[-1] if RUNTIME_AUTOMOD_TERMS else "none"
            nsfw_last_term = RUNTIME_NSFW_TERMS[-1] if RUNTIME_NSFW_TERMS else "none"
            details = (
                f"Normal raw lines: **{raw_lines}**\n"
                f"Normal ignored lines: **{ignored_lines}**\n"
                f"Normal loaded terms: **{normal_term_count}**\n"
                f"Normal file: `{normal_path}`\n"
                f"Normal modified: **{normal_mtime}**\n"
                f"Normal last term: `{normal_last_term}`\n"
                f"NSFW raw lines: **{nsfw_raw_lines}**\n"
                f"NSFW ignored lines: **{nsfw_ignored_lines}**\n"
                f"NSFW loaded terms: **{nsfw_term_count}**\n"
                f"NSFW file: `{nsfw_path}`\n"
                f"NSFW modified: **{nsfw_mtime}**\n"
                f"NSFW last term: `{nsfw_last_term}`"
            )
        elif normalized == "invitesystem":
            invite_count = refresh_runtime_approved_invites()
            details = f"Loaded **{invite_count}** approved invite codes into runtime cache."
        elif normalized == "botsystem":
            bot_count = refresh_runtime_approved_bots()
            ids_text = ", ".join(f"`{bid}`" for bid in sorted(RUNTIME_APPROVED_BOT_IDS)) if RUNTIME_APPROVED_BOT_IDS else "none"
            details = f"Loaded **{bot_count}** approved bot IDs:\n{ids_text}"
        elif normalized == "ticketsystam":
            await post_ticket_panel()
            details = "Ticket panel re-posted."
        else:
            await ctx.send(
                f"Invalid category. Use one of: `{'`, `'.join(ALL_CATEGORIES)}`."
            )
            return
    except Exception as reload_error:
        await ctx.send(f"Reload failed for `{normalized}`: `{reload_error}`")
        return

    elapsed = time.perf_counter() - started_at
    embed = discord.Embed(
        title="Cog Reloaded",
        description=f"`{normalized}` reloaded successfully.",
        color=discord.Color.blue(),
    )
    if details:
        embed.add_field(name="Details", value=details, inline=False)
    embed.add_field(name="Elapsed Time", value=f"{elapsed:.4f}s", inline=False)
    embed.set_footer(text="Cog Manager • Success")
    await ctx.send(embed=embed)


@bot.command(name="addbotid")
async def addbotid(ctx: commands.Context, bot_id: str = "") -> None:
    if ctx.guild is None or not isinstance(ctx.author, discord.Member):
        await ctx.send("This command can only be used in a server.")
        return

    member_role_ids = {role.id for role in ctx.author.roles}
    reload_role_id = get_reload_command_role_id()
    if reload_role_id not in member_role_ids:
        await ctx.send(f"You need the **{role_name_text(reload_role_id, ctx.guild)}** role to use this command.")
        return

    if not bot_id.strip():
        await ctx.send("Usage: `?addbotid <bot_id>`")
        return

    try:
        new_id = int(bot_id.strip())
    except ValueError:
        await ctx.send("Invalid bot ID. Must be a numeric Discord user ID.")
        return

    ensure_approved_bots_file()
    try:
        with open(APPROVED_BOTS_PATH, "r", encoding="utf-8") as f:
            file_data = json.load(f)
    except (OSError, json.JSONDecodeError):
        file_data = {"bot_ids": []}

    if not isinstance(file_data, dict):
        file_data = {"bot_ids": []}

    existing = file_data.get("bot_ids", [])
    if new_id in existing:
        await ctx.send(f"Bot ID `{new_id}` is already in the approved list.")
        return

    existing.append(new_id)
    file_data["bot_ids"] = existing
    with open(APPROVED_BOTS_PATH, "w", encoding="utf-8") as f:
        json.dump(file_data, f, indent=2)

    count = refresh_runtime_approved_bots()
    await ctx.send(f"Added `{new_id}` to approved bots. Runtime cache now has **{count}** bot IDs.")


@bot.command(name="removebotid")
async def removebotid(ctx: commands.Context, bot_id: str = "") -> None:
    if ctx.guild is None or not isinstance(ctx.author, discord.Member):
        await ctx.send("This command can only be used in a server.")
        return

    member_role_ids = {role.id for role in ctx.author.roles}
    reload_role_id = get_reload_command_role_id()
    if reload_role_id not in member_role_ids:
        await ctx.send(f"You need the **{role_name_text(reload_role_id, ctx.guild)}** role to use this command.")
        return

    if not bot_id.strip():
        await ctx.send("Usage: `?removebotid <bot_id>`")
        return

    try:
        target_id = int(bot_id.strip())
    except ValueError:
        await ctx.send("Invalid bot ID. Must be a numeric Discord user ID.")
        return

    ensure_approved_bots_file()
    try:
        with open(APPROVED_BOTS_PATH, "r", encoding="utf-8") as f:
            file_data = json.load(f)
    except (OSError, json.JSONDecodeError):
        file_data = {"bot_ids": []}

    if not isinstance(file_data, dict):
        file_data = {"bot_ids": []}

    existing = file_data.get("bot_ids", [])
    if target_id not in existing:
        await ctx.send(f"Bot ID `{target_id}` is not in the approved list.")
        return

    existing.remove(target_id)
    file_data["bot_ids"] = existing
    with open(APPROVED_BOTS_PATH, "w", encoding="utf-8") as f:
        json.dump(file_data, f, indent=2)

    count = refresh_runtime_approved_bots()
    await ctx.send(f"Removed `{target_id}` from approved bots. Runtime cache now has **{count}** bot IDs.")


@bot.command(name="syncslash")
async def syncslash(ctx: commands.Context) -> None:
    if ctx.guild is None or not isinstance(ctx.author, discord.Member):
        await ctx.send("This command can only be used in a server.")
        return

    member_role_ids = {role.id for role in ctx.author.roles}
    reload_role_id = get_reload_command_role_id()
    if reload_role_id not in member_role_ids:
        await ctx.send(f"You need the **{role_name_text(reload_role_id, ctx.guild)}** role to use this command.")
        return

    await ctx.send("Syncing slash commands now...")
    guild_synced_count, global_synced_count, sync_error = await sync_slash_commands_now()
    if sync_error is not None:
        app_id = bot.user.id if bot.user else 0
        invite_url = (
            "https://discord.com/oauth2/authorize"
            f"?client_id={app_id}&scope=bot%20applications.commands&permissions=8"
        )
        await ctx.send(
            "Slash sync failed.\n"
            f"Error: `{sync_error}`\n"
            f"Re-authorize URL: {invite_url}"
        )
        return

    await ctx.send(
        "Slash sync complete. "
        f"Guild commands: **{guild_synced_count}**, Global commands: **{global_synced_count}**."
    )


@bot.command(name="give_role")
async def give_role(ctx: commands.Context, guild_id: str, role_id: str, user_id: str) -> None:
    if ctx.guild is None or not isinstance(ctx.author, discord.Member):
        await ctx.send("This command can only be used in a server.")
        return
    
    main_member = await get_main_server_member(ctx.author.id)
    if main_member is None or not member_has_any_named_role(main_member, MAIN_SERVER_ANY_ROLE_NAMES):
        await ctx.send("You need one of the approved staff board or bot permission roles in the main server to use this command.")
        return

    try:
        target_guild_id = int(guild_id)
        target_role_id = int(role_id)
        target_user_id = int(user_id)
    except ValueError:
        await ctx.send("All IDs must be numeric.")
        return

    target_guild = bot.get_guild(target_guild_id)
    if target_guild is None:
        await ctx.send(f"I am not in a server with ID `{target_guild_id}`.")
        return

    try:
        member = await target_guild.fetch_member(target_user_id)
    except discord.NotFound:
        await ctx.send(f"User `{target_user_id}` is not in that server.")
        return
    except discord.HTTPException as e:
        await ctx.send(f"Failed to fetch member: {e}")
        return

    role = target_guild.get_role(target_role_id)
    if role is None:
        await ctx.send(f"Role `{target_role_id}` does not exist in that server.")
        return

    try:
        await member.add_roles(role, reason=f"Given by {ctx.author} via give_role command.")
        await ctx.send(f"Gave **{role.name}** to <@{member.id}> in **{target_guild.name}**.")
    except discord.Forbidden:
        await ctx.send("I do not have permission to assign that role in that server.")
    except discord.HTTPException as e:
        await ctx.send(f"Failed to assign role: {e}")


@bot.event
async def on_command_error(ctx: commands.Context, error: Exception) -> None:
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("Missing required argument. Use the help command for usage.")
        return

    if isinstance(error, commands.BadArgument):
        await ctx.send("Invalid argument type.")
        return

    if isinstance(error, commands.MissingPermissions):
        await ctx.send("You do not have permission to use that command.")
        return

    if isinstance(error, commands.MissingRole):
        missing_role_id = error.missing_role if isinstance(error.missing_role, int) else None
        if missing_role_id is not None:
            role_text = role_name_text(missing_role_id, ctx.guild)
            await ctx.send(f"You need the **{role_text}** role to use this command.")
        else:
            await ctx.send("You do not have the required role to use that command.")
        return

    if isinstance(error, commands.BotMissingPermissions):
        await ctx.send("I am missing permissions required for that command.")
        return

    if isinstance(error, commands.CommandNotFound):
        raw_parts = (ctx.message.content or "").strip().split(maxsplit=1)
        typed_command = raw_parts[0].lower() if raw_parts else ""
        if typed_command in {f"{PREFIX}baninfo", "!baninfo"}:
            if not ctx.author.guild_permissions.ban_members:
                await ctx.send("You do not have permission to use that command.")
                return
            if len(raw_parts) < 2:
                await ctx.send(f"Usage: `{PREFIX}baninfo <user_id>`")
                return
            await run_baninfo_lookup(ctx, raw_parts[1].strip())
            return
        await ctx.send(f"Command not found: `{ctx.message.content.split()[0]}`")
        return

    if isinstance(error, commands.CheckFailure):
        message = str(error).strip() or "You do not meet the requirements to use that command."
        await ctx.send(message)
        return

    await ctx.send("Something went wrong while running that command.")
    original_error = getattr(error, "original", error)
    print(f"Command error in {getattr(ctx.command, 'qualified_name', 'unknown')}: {original_error!r}")
    traceback.print_exception(type(original_error), original_error, original_error.__traceback__)



@bot.command(name="maskick")
@main_server_role_required(ALL_SERVER_BAN_COMMAND_ROLE_ID)
async def maskick(ctx: commands.Context, *targets: str) -> None:
    if not targets:
        await ctx.send(f"Usage: `{PREFIX}maskick <user_id1> <user_id2> ...`")
        return

    user_ids: list[int] = []
    invalid: list[str] = []
    for t in targets:
        uid = parse_user_id(t)
        if uid is None:
            invalid.append(t)
        else:
            user_ids.append(uid)

    if invalid:
        await ctx.send(f"Could not parse the following as user IDs: {', '.join(invalid)}")
        if not user_ids:
            return

    results: list[str] = []
    for user_id in user_ids:
        kicked_count = 0
        failed_count = 0
        not_in_count = 0
        for guild in bot.guilds:
            member = guild.get_member(user_id)
            if member is None:
                not_in_count += 1
                continue
            try:
                await member.kick(reason=f"Mass all-server kick by {ctx.author}")
                kicked_count += 1
            except (discord.Forbidden, discord.HTTPException):
                failed_count += 1
        results.append(
            f"<@{user_id}> — kicked: **{kicked_count}**, not in: **{not_in_count}**, failed: **{failed_count}**"
        )

    embed = discord.Embed(
        title="SLCRP | Mass All-Server Kick",
        description="\n".join(results),
        color=discord.Color.blue(),
        timestamp=datetime.now(timezone.utc),
    )
    embed.set_footer(text=f"Requested by {ctx.author}")
    await ctx.send(embed=embed)


@bot.command(name="mswban")
@main_server_role_required(ALL_SERVER_BAN_COMMAND_ROLE_ID)
async def mswban(ctx: commands.Context, *targets: str) -> None:
    if not targets:
        await ctx.send(f"Usage: `{PREFIX}mswban <user_id1> <user_id2> ...`")
        return

    user_ids: list[int] = []
    invalid: list[str] = []
    for t in targets:
        uid = parse_user_id(t)
        if uid is None:
            invalid.append(t)
        else:
            user_ids.append(uid)

    if invalid:
        await ctx.send(f"Could not parse the following as user IDs: {', '.join(invalid)}")
        if not user_ids:
            return

    target_guilds = get_all_server_ban_guilds(include_ban_appeal=True)
    processed_count = 0
    total_bans_count = 0
    target_log_channel_ids = [MSWBAN_AUDIT_LOG_CHANNEL_ID]

    for user_id in user_ids:
        try:
            user = await bot.fetch_user(user_id)
        except discord.NotFound:
            print(f"mswban: {user_id} not found")
            continue
        except discord.HTTPException:
            print(f"mswban: could not fetch user {user_id}")
            continue

        try:
            banned_count = 0
            failed_count = 0
            deleted_count = 0
            for guild in target_guilds:
                try:
                    try:
                        await guild.ban(
                            user,
                            reason=f"Mass server-wide ban by {ctx.author}",
                            delete_message_seconds=0,
                        )
                    except TypeError:
                        await guild.ban(
                            user,
                            reason=f"Mass server-wide ban by {ctx.author}",
                            delete_message_days=0,
                        )
                    banned_count += 1
                    try:
                        deleted_count += await delete_recent_user_messages(guild, user.id, days=7)
                    except Exception:
                        pass
                except discord.Forbidden as ban_error:
                    print(f"mswban forbidden in guild {guild.id} for {user_id}: {ban_error}")
                    failed_count += 1
                except discord.HTTPException as ban_error:
                    print(f"mswban http error in guild {guild.id} for {user_id}: {ban_error}")
                    failed_count += 1
                except Exception as ban_error:
                    print(f"mswban unexpected ban error in guild {guild.id} for {user_id}: {ban_error}")
                    failed_count += 1
                await asyncio.sleep(0.1)

            appeal_invite_url = await get_ban_appeal_invite_url()
            if banned_count > 0:
                try:
                    await send_main_bot_ban_appeal_dm(
                        user,
                        "banned across SLCRP servers",
                        "Mass server-wide ban",
                        str(ctx.author),
                        appeal_invite_url,
                    )
                except Exception:
                    pass
                try:
                    queue_modmail_ban_appeal_dm(
                        user.id,
                        "banned across SLCRP servers",
                        "Mass server-wide ban",
                        str(ctx.author),
                        appeal_invite_url,
                    )
                except Exception:
                    pass

            user_embed = discord.Embed(
                title="Mswban",
                color=discord.Color.blue(),
                timestamp=datetime.now(timezone.utc),
            )
            user_embed.add_field(
                name="Moderator",
                value=f"{ctx.author.mention} ({ctx.author.id})",
                inline=False
            )
            user_embed.add_field(
                name="Target",
                value=f"{user.mention} ({user_id})",
                inline=False
            )
            user_embed.add_field(
                name="Banned",
                value=f"{banned_count}/{len(target_guilds)}",
                inline=True
            )
            user_embed.add_field(
                name="Failed",
                value=str(failed_count),
                inline=True
            )
            user_embed.add_field(
                name="Messages Deleted",
                value=str(deleted_count),
                inline=True
            )
            user_embed.add_field(
                name="Reason",
                value="Mass server wide ban executed.",
                inline=False
            )
            user_embed.set_footer(text=f"Requested by {ctx.author}")

            for channel_id in dict.fromkeys(target_log_channel_ids):
                log_channel = None
                if ctx.guild is not None:
                    log_channel = ctx.guild.get_channel(channel_id)
                if log_channel is None:
                    log_channel = bot.get_channel(channel_id)

                if isinstance(log_channel, discord.TextChannel):
                    try:
                        await log_channel.send(embed=user_embed)
                    except discord.HTTPException as log_error:
                        print(f"mswban log send failed for {channel_id}: {log_error}")

            processed_count += 1
            total_bans_count += banned_count
            await asyncio.sleep(0.2)
        except Exception as user_error:
            print(f"mswban user processing error for {user_id}: {user_error}")

    await ctx.send(
        f"Mass server-wide ban executed on **{processed_count}** user(s) across **{total_bans_count}** total server ban(s). "
        f"Check the audit logs for individual ban details."
    )


@bot.command(name="cmds")
async def cmds(ctx: commands.Context) -> None:
    """Commands for the WARN/automod staff role."""
    automod_role_commands = [
        f"{PREFIX}warn",
        f"{PREFIX}unwarn",
        f"{PREFIX}warnings",
        f"{PREFIX}lockdown",
        f"{PREFIX}softban",
        f"{PREFIX}timeout",
        f"{PREFIX}setnickname",
    ]
    embed = discord.Embed(
        title="Automod Role Commands",
        description="\n".join(f"- `{name}`" for name in automod_role_commands),
        color=discord.Color.blue(),
    )
    embed.set_footer(text=f"Role required: {WARN_COMMAND_ROLE_ID}")
    try:
        await ctx.author.send(embed=embed)
        if ctx.guild is not None:
            await ctx.send("I sent your command list in DMs.")
    except (discord.Forbidden, discord.HTTPException):
        await ctx.send("I could not DM you. Please enable DMs and try again.")


@bot.command(name="funcmds")
async def funcmds(ctx: commands.Context) -> None:
    """Commands that everyone can use (no staff-only commands)."""
    public_commands = [
        f"{PREFIX}help",
        f"{PREFIX}ping",
        f"{PREFIX}myid",
        f"{PREFIX}id",
        f"{PREFIX}support",
        f"{PREFIX}ingame",
        f"{PREFIX}checkstaff",
        f"{PREFIX}queue",
        f"{PREFIX}out",
        f"{PREFIX}lock",
        f"{PREFIX}unlock",
        f"{PREFIX}soundboard",
        f"{PREFIX}closerequest",
        f"{PREFIX}claim",
        f"{PREFIX}rp change",
        f"{PREFIX}rp info",
        f"{PREFIX}rp history",
        f"{PREFIX}levels",
        f"{PREFIX}lledaderboard",
        f"{PREFIX}funcmds",
        f"{PREFIX}cmds",
        f"{PREFIX}owcmds",
    ]
    embed = discord.Embed(
        title="Public Commands (No Staff Commands)",
        description="\n".join(f"- `{name}`" for name in public_commands),
        color=discord.Color.blue(),
    )
    try:
        await ctx.author.send(embed=embed)
        if ctx.guild is not None:
            await ctx.send("I sent your command list in DMs.")
    except (discord.Forbidden, discord.HTTPException):
        await ctx.send("I could not DM you. Please enable DMs and try again.")


@bot.command(name="owcmds")
async def owcmds(ctx: commands.Context) -> None:
    """High-privilege controller/staff command list."""
    controller_commands = [
        f"{PREFIX}reload",
        f"{PREFIX}give_role",
        f"{PREFIX}nrs",
        f"{PREFIX}gar",
        f"{PREFIX}swban",
        f"{PREFIX}swunban",
        f"{PREFIX}askick",
        f"{PREFIX}maskick",
        f"{PREFIX}masban",
        f"{PREFIX}setstatus",
        f"{PREFIX}ssu",
        f"{PREFIX}ssd",
        f"{PREFIX}say",
        f"{PREFIX}clear",
        f"{PREFIX}kick",
        f"{PREFIX}ban",
        f"{PREFIX}unban",
        f"{PREFIX}closeticket",
        f"{PREFIX}moveticket",
        f"{PREFIX}transcript",
    ]
    embed = discord.Embed(
        title="Bot Controller Commands",
        description="\n".join(f"- `{name}`" for name in controller_commands),
        color=discord.Color.blue(),
    )
    embed.set_footer(text="Some commands also require specific roles/permissions.")
    try:
        await ctx.author.send(embed=embed)
        if ctx.guild is not None:
            await ctx.send("I sent your command list in DMs.")
    except (discord.Forbidden, discord.HTTPException):
        await ctx.send("I could not DM you. Please enable DMs and try again.")


bot.run(TOKEN)

