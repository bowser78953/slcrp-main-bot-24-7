from __future__ import annotations

import asyncio
import io
import json
import os
import random
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

import discord
from discord import app_commands
from dotenv import load_dotenv

from .handlers import MessageHandler
from .json_store import JsonStore


class ConfigError(Exception):
    pass


BOT_CONTROL_OWNER_ID = 1332458947067773072


class GuardedCommandTree(app_commands.CommandTree):
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        denial = self.client._command_access_denial(interaction.user.id)
        if denial:
            await interaction.response.send_message(denial)
            return False
        return True


GLOBAL_BAN_AUDIT_CHANNEL_ID = 1554592675116744786
ROLE_THRESHOLD_ROLE_ID = 1554533334955069632
CHANNEL_LOCK_ROLE_ID = 1554697553461903400
AUTOMOD_AUDIT_CHANNEL_ID = 1554592774626484404
AUTOMOD_CC_ROLE_ID = 1554635863739080764
AUTOMOD_EXEMPT_ROLE_ID = 1556404763887800370


def resolve_token(settings: dict[str, Any]) -> str:
    env_token = os.getenv("DISCORD_BOT_TOKEN", "").strip()
    if env_token and env_token != "PUT_YOUR_DISCORD_BOT_TOKEN_HERE":
        return env_token

    file_token = str(settings.get("token", "")).strip()
    if file_token and file_token != "PUT_YOUR_DISCORD_BOT_TOKEN_HERE":
        return file_token

    raise ConfigError("Set DISCORD_BOT_TOKEN in the environment or in discord_bot/.env before running.")


def _load_command_files(commands_dir: Path) -> tuple[dict[str, Any], dict[str, str]]:
    commands: dict[str, Any] = {}
    responses: dict[str, str] = {}

    if not commands_dir.exists():
        return commands, responses

    for command_file in sorted(commands_dir.glob("*.json")):
        with command_file.open("r", encoding="utf-8") as f:
            raw_data = json.load(f)

        if not isinstance(raw_data, dict):
            raise ConfigError(f"Command file must be a JSON object: {command_file}")

        command_name = str(raw_data.get("name") or command_file.stem).strip().lower()
        if not command_name:
            raise ConfigError(f"Command file has invalid name: {command_file}")

        aliases = [str(alias).strip() for alias in raw_data.get("aliases", []) if str(alias).strip()]
        description = str(raw_data.get("description", "No description"))

        response_key = str(raw_data.get("response_key") or f"{command_name}_text")
        commands[command_name] = {
            "description": description,
            "response_key": response_key,
            "aliases": aliases,
        }

        if "response" in raw_data:
            responses[response_key] = str(raw_data.get("response", ""))

    return commands, responses


def _load_categories(path: Path) -> dict[str, list[str]]:
    if not path.exists():
        return {}

    store = JsonStore(path)
    raw_data = store.load()
    if not isinstance(raw_data, dict):
        raise ConfigError(f"Category file must be a JSON object: {path}")

    categories: dict[str, list[str]] = {}
    for category_name, files in raw_data.items():
        if isinstance(files, list):
            categories[str(category_name).strip().lower()] = [str(file_name).strip() for file_name in files if str(file_name).strip()]
    return categories


def _load_automod_words(path: Path) -> list[str]:
    try:
        raw_data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigError(f"Could not load automod word list {path}: {exc}") from exc

    if not isinstance(raw_data, dict) or not isinstance(raw_data.get("words"), list):
        raise ConfigError(f"Automod config must contain a words array: {path}")
    if any(not isinstance(word, str) for word in raw_data["words"]):
        raise ConfigError(f"Automod words must all be strings: {path}")

    return list(dict.fromkeys(word.strip() for word in raw_data["words"] if word.strip()))


def _compile_automod_words(words: list[str]) -> re.Pattern[str] | None:
    if not words:
        return None
    alternatives = "|".join(re.escape(word) for word in sorted(words, key=len, reverse=True))
    return re.compile(rf"\b(?:{alternatives})\b", re.IGNORECASE)


def load_all_config(base_path: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, str], dict[str, list[str]]]:
    load_dotenv(base_path / ".env")

    settings_store = JsonStore(base_path / "config" / "settings.json")
    commands_store = JsonStore(base_path / "config" / "commands.json")
    responses_store = JsonStore(base_path / "data" / "responses.json")
    categories_path = base_path / "config" / "catagorys.json"
    commands_dir = base_path / "commands"

    settings = settings_store.load()
    commands: dict[str, Any] = commands_store.load() if commands_store.path.exists() else {}
    responses: dict[str, str] = responses_store.load() if responses_store.path.exists() else {}
    categories = _load_categories(categories_path)

    file_commands, file_responses = _load_command_files(commands_dir)
    commands.update(file_commands)
    responses.update(file_responses)

    settings["token"] = resolve_token(settings)

    return settings, commands, responses, categories


class ConfigReloader:
    def __init__(self, base_path: Path):
        self.base_path = base_path
        self.settings_path = base_path / "config" / "settings.json"
        self.commands_path = base_path / "config" / "commands.json"
        self.responses_path = base_path / "data" / "responses.json"
        self.categories_path = base_path / "config" / "catagorys.json"
        self.automod_path = base_path / "config" / "automod.json"
        self.commands_dir = base_path / "commands"

        self.settings: dict[str, Any] = {}
        self.commands: dict[str, Any] = {}
        self.responses: dict[str, str] = {}
        self.categories: dict[str, list[str]] = {}
        self.automod_words: list[str] = []
        self.automod_pattern: re.Pattern[str] | None = None
        self._file_mtimes: dict[Path, int] = {}

    def load_initial(self) -> None:
        settings, commands, responses, categories = load_all_config(self.base_path)
        self.settings = settings
        self.commands = commands
        self.responses = responses
        self.categories = categories
        self.automod_words = _load_automod_words(self.automod_path)
        self.automod_pattern = _compile_automod_words(self.automod_words)
        self._refresh_mtimes()

    def _tracked_files(self) -> list[Path]:
        tracked = [self.settings_path, self.commands_path, self.responses_path, self.categories_path, self.automod_path]
        if self.commands_dir.exists():
            tracked.extend(sorted(self.commands_dir.glob("*.json")))
        return [path for path in tracked if path.exists()]

    def _refresh_mtimes(self) -> None:
        self._file_mtimes = {path: path.stat().st_mtime_ns for path in self._tracked_files()}

    def _files_changed(self) -> bool:
        current_files = self._tracked_files()
        if set(current_files) != set(self._file_mtimes.keys()):
            return True

        for path in current_files:
            old_mtime = self._file_mtimes.get(path)
            if old_mtime is None:
                return True
            if path.stat().st_mtime_ns != old_mtime:
                return True
        return False

    def reload_if_changed(self) -> tuple[bool, bool]:
        if not self._file_mtimes:
            return False, False

        if not self._files_changed():
            return False, False

        old_commands = self.commands

        settings, commands, responses, categories = load_all_config(self.base_path)
        automod_words = _load_automod_words(self.automod_path)

        settings["token"] = resolve_token(settings)

        command_schema_changed = old_commands != commands

        self.settings = settings
        self.commands = commands
        self.responses = responses
        self.categories = categories
        self.automod_words = automod_words
        self.automod_pattern = _compile_automod_words(automod_words)
        self._refresh_mtimes()
        return True, command_schema_changed


class FarmersDiscordBot(discord.Client):
    def __init__(self, base_path: Path):
        self.config_reloader = ConfigReloader(base_path)
        self.config_reloader.load_initial()

        settings = self.config_reloader.settings
        commands = self.config_reloader.commands
        responses = self.config_reloader.responses

        intents = discord.Intents.default()
        intents.message_content = bool(settings.get("message_content_intent", True))
        super().__init__(intents=intents)

        self.tree = GuardedCommandTree(self)
        self.settings = settings
        self.handler = MessageHandler(settings=settings, commands=commands, responses=responses)
        self.categories = self.config_reloader.categories
        self.giveaways: dict[int, dict[str, Any]] = {}
        self.giveaway_ping_roles: dict[int, int] = {}
        self.channel_lock_snapshots: dict[str, dict[str, Any]] = {}
        self.automod_cases: dict[str, dict[str, Any]] = {}
        self.last_moderation_cases: dict[str, str] = {}
        self.underdev_enabled = False
        self.disabled_user_ids: set[int] = set()
        self._giveaway_tasks: dict[int, asyncio.Task[None]] = {}
        self.data_path = Path(os.getenv("DISCORD_BOT_DATA_DIR", base_path / "data"))
        self.data_path.mkdir(parents=True, exist_ok=True)
        self.persistent_state_store = JsonStore(self.data_path / "bot_state.json")
        self._load_persistent_state()
        self.saved_roles_store = JsonStore(self.data_path / "saved_roles.json")
        self.saved_roles = self.saved_roles_store.load() if self.saved_roles_store.path.exists() else {}
        self.clear_transcripts_store = JsonStore(self.data_path / "clear_transcripts.json")
        self.clear_transcripts = (
            self.clear_transcripts_store.load()
            if self.clear_transcripts_store.path.exists()
            else {}
        )

    def _load_persistent_state(self) -> None:
        if not self.persistent_state_store.path.exists():
            return

        state = self.persistent_state_store.load()
        if not isinstance(state, dict):
            return

        for giveaway_id, raw_giveaway in state.get("giveaways", {}).items():
            if not isinstance(raw_giveaway, dict):
                continue
            try:
                parsed_id = int(giveaway_id)
                giveaway = dict(raw_giveaway)
                giveaway["giveaway_id"] = int(giveaway.get("giveaway_id", parsed_id))
                giveaway["entries"] = {int(user_id) for user_id in giveaway.get("entries", [])}
                giveaway["winner_ids"] = [int(user_id) for user_id in giveaway.get("winner_ids", [])]
                giveaway["ended"] = bool(giveaway.get("ended", False))
                giveaway["result_posted"] = bool(giveaway.get("result_posted", False))
                self.giveaways[parsed_id] = giveaway
            except (TypeError, ValueError):
                continue

        raw_ping_roles = state.get("giveaway_ping_roles", {})
        if isinstance(raw_ping_roles, dict):
            for guild_id, role_id in raw_ping_roles.items():
                try:
                    self.giveaway_ping_roles[int(guild_id)] = int(role_id)
                except (TypeError, ValueError):
                    continue

        raw_channel_locks = state.get("channel_lock_snapshots", {})
        if isinstance(raw_channel_locks, dict):
            self.channel_lock_snapshots = {
                str(channel_id): snapshot
                for channel_id, snapshot in raw_channel_locks.items()
                if isinstance(snapshot, dict)
            }

        raw_automod_cases = state.get("automod_cases", {})
        if isinstance(raw_automod_cases, dict):
            self.automod_cases = {
                str(case_id): case
                for case_id, case in raw_automod_cases.items()
                if isinstance(case, dict)
            }

        raw_last_cases = state.get("last_moderation_cases", {})
        if isinstance(raw_last_cases, dict):
            self.last_moderation_cases = {
                str(case_key): str(case_name)
                for case_key, case_name in raw_last_cases.items()
                if str(case_name) in {"Ban", "Kick", "Warning", "N/A"}
            }

        self.underdev_enabled = bool(state.get("underdev_enabled", False))
        raw_disabled_users = state.get("disabled_user_ids", [])
        if isinstance(raw_disabled_users, list):
            self.disabled_user_ids = {
                int(user_id)
                for user_id in raw_disabled_users
                if str(user_id).isdigit()
            }

    def _save_persistent_state(self) -> None:
        giveaways = {}
        for giveaway_id, giveaway in self.giveaways.items():
            saved_giveaway = dict(giveaway)
            saved_giveaway["giveaway_id"] = int(giveaway_id)
            saved_giveaway["entries"] = sorted(int(user_id) for user_id in giveaway.get("entries", set()))
            saved_giveaway["winner_ids"] = [int(user_id) for user_id in giveaway.get("winner_ids", [])]
            giveaways[str(giveaway_id)] = saved_giveaway

        self.persistent_state_store.save(
            {
                "giveaways": giveaways,
                "giveaway_ping_roles": {
                    str(guild_id): int(role_id)
                    for guild_id, role_id in self.giveaway_ping_roles.items()
                },
                "channel_lock_snapshots": self.channel_lock_snapshots,
                "automod_cases": self.automod_cases,
                "last_moderation_cases": self.last_moderation_cases,
                "underdev_enabled": bool(getattr(self, "underdev_enabled", False)),
                "disabled_user_ids": sorted(
                    int(user_id) for user_id in getattr(self, "disabled_user_ids", set())
                ),
            }
        )

    def _schedule_giveaway(self, giveaway_id: int) -> None:
        task = self._giveaway_tasks.get(giveaway_id)
        if task is not None and not task.done():
            return
        self._giveaway_tasks[giveaway_id] = asyncio.create_task(self._finish_giveaway(giveaway_id))

    def _parse_duration_to_seconds(self, duration_text: str) -> int:
        total = 0
        for part in str(duration_text or "").split("_"):
            part = part.strip().lower()
            if not part:
                continue
            match = __import__("re").fullmatch(r"(\d+)([dhms])", part)
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

    def _build_giveaway_embed(self, giveaway: dict[str, Any], guild: discord.Guild | None) -> discord.Embed:
        prize = str(giveaway.get("prize", "Giveaway"))
        description = str(giveaway.get("description", ""))
        ended = bool(giveaway.get("ended"))
        prize_display = f"{prize} - Ended" if ended else prize
        entries = list(giveaway.get("entries", set()))
        embed = discord.Embed(
            description=f"## {prize_display}\n{description}",
            color=discord.Color.red() if ended else discord.Color.green(),
        )
        embed.add_field(name="<:Winner:1529950654800334968> Winners", value=str(int(giveaway.get("winner_count", 1) or 1)), inline=True)
        embed.add_field(name="<:Entrees:1529950712677797978> Entrees", value=str(len(entries)), inline=True)
        embed.add_field(name="<:Time:1529950779203387523> Time", value=f"<t:{int(giveaway.get('end_ts', 0) or 0)}:R>", inline=True)

        host_user_id = int(giveaway.get("host_user_id", 0) or 0)
        if host_user_id > 0:
            embed.add_field(name="<:Host:1529950982056710225> Host", value=f"<@{host_user_id}>", inline=False)
        if guild and guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        embed.set_footer(text=f"ID: {int(giveaway.get('giveaway_id', 0) or 0)}")
        return embed

    def _build_winner_announcement(self, giveaway: dict[str, Any], winners: list[int]) -> str:
        winner_mentions = " ".join(f"<@{winner_id}>" for winner_id in winners)
        prize = str(giveaway.get("prize", "Giveaway"))
        return f"<:Congrats:1529950839479865394> {winner_mentions} has won {prize}! Congrats!"

    def _build_giveaway_entry_embed(self, giveaway: dict[str, Any], guild: discord.Guild | None) -> discord.Embed:
        entries = sorted(int(user_id) for user_id in giveaway.get("entries", set()))
        lines = [f"{index}. <@{user_id}>" for index, user_id in enumerate(entries[:25], start=1)]
        description = "\n".join(lines) if lines else "No entries yet."
        embed = discord.Embed(
            description=description,
            color=discord.Color.green(),
        )
        embed.set_footer(text=f"This is the entree list from {int(giveaway.get('giveaway_id', 0) or 0)}")
        if guild and guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        return embed

    async def _finish_giveaway(self, giveaway_id: int) -> None:
        giveaway = self.giveaways.get(giveaway_id)
        if not giveaway:
            return

        if not giveaway.get("ended"):
            wait_for = max(0, int(giveaway.get("end_ts", 0) or 0) - int(datetime.now(timezone.utc).timestamp()))
            await asyncio.sleep(wait_for)

            giveaway = self.giveaways.get(giveaway_id)
            if not giveaway:
                return

            if not giveaway.get("ended"):
                giveaway["ended"] = True
                entries = list(giveaway.get("entries", set()))
                winner_count = min(int(giveaway.get("winner_count", 1) or 1), len(entries))
                giveaway["winner_ids"] = random.sample(entries, k=winner_count) if winner_count else []
                giveaway["result_posted"] = False
                self._save_persistent_state()

        if giveaway.get("result_posted"):
            return

        guild_id = int(giveaway.get("guild_id", 0) or 0)
        guild = self.get_guild(guild_id)
        channel = self.get_channel(int(giveaway.get("channel_id", 0) or 0))
        if channel is None:
            try:
                channel = await self.fetch_channel(int(giveaway.get("channel_id", 0) or 0))
            except Exception:
                channel = None
        if not isinstance(channel, discord.TextChannel):
            return

        message = None
        if giveaway.get("message_id") is not None:
            try:
                message = await channel.fetch_message(int(giveaway.get("message_id", 0) or 0))
            except Exception:
                message = None
        if message is not None:
            try:
                await message.edit(embed=self._build_giveaway_embed(giveaway, guild))
            except Exception:
                pass

        winner_ids = [int(user_id) for user_id in giveaway.get("winner_ids", [])]
        if not winner_ids:
            await channel.send(f"🎉 Giveaway ended for **{giveaway.get('prize', 'Giveaway')}** with no entries.")
        else:
            await channel.send(self._build_winner_announcement(giveaway, winner_ids))
        giveaway["result_posted"] = True
        self._save_persistent_state()

    async def _create_giveaway(self, *, channel: discord.abc.Messageable, guild: discord.Guild | None, host_user_id: int, prize: str, description: str, time_text: str, winner_count: int, ping_role_id: int | None) -> int:
        duration_seconds = self._parse_duration_to_seconds(time_text)
        now_ts = int(datetime.now(timezone.utc).timestamp())
        giveaway_id = int(now_ts * 1000)
        giveaway = {
            "giveaway_id": giveaway_id,
            "prize": prize,
            "description": description,
            "end_ts": now_ts + duration_seconds,
            "winner_count": int(winner_count),
            "entries": set(),
            "ended": False,
            "winner_ids": [],
            "result_posted": False,
            "channel_id": getattr(channel, "id", None),
            "message_id": None,
            "host_user_id": int(host_user_id),
            "guild_id": getattr(guild, "id", None),
            "ping_role_id": int(ping_role_id) if ping_role_id else None,
        }
        self.giveaways[giveaway_id] = giveaway
        content = f"<@&{ping_role_id}>" if ping_role_id else None
        view = discord.ui.View()
        view.add_item(discord.ui.Button(label="🎉 Enter", style=discord.ButtonStyle.success, custom_id=f"giveaway-enter:{giveaway_id}"))
        message = await channel.send(
            content=content,
            embed=self._build_giveaway_embed(giveaway, guild),
            view=view,
            allowed_mentions=discord.AllowedMentions(roles=True),
        )
        giveaway["message_id"] = message.id
        self._save_persistent_state()
        self._schedule_giveaway(giveaway_id)
        return giveaway_id

    async def _sync_slash_commands(self) -> None:
        await self.tree.sync(guild=None)
        for guild in list(self.guilds):
            await self.tree.sync(guild=guild)

    async def setup_hook(self) -> None:
        await self._register_slash_commands()
        if self.settings.get("sync_slash_on_startup", True):
            await self._sync_slash_commands()

    async def on_interaction(self, interaction: discord.Interaction) -> None:
        if interaction.type != discord.InteractionType.component:
            return
        if not interaction.data or "custom_id" not in interaction.data:
            return
        custom_id = str(interaction.data["custom_id"])
        if custom_id.startswith("bot-disable-confirm:"):
            await self._handle_bot_control_interaction(interaction, custom_id)
            return
        if custom_id.startswith("automod-case:"):
            await self._handle_automod_case_interaction(interaction, custom_id)
            return
        if not custom_id.startswith("giveaway-enter:"):
            return

        giveaway_id = int(custom_id.split(":", 1)[1])
        giveaway = self.giveaways.get(giveaway_id)
        if not giveaway or giveaway.get("ended"):
            await interaction.response.send_message("This giveaway is already over.", ephemeral=True)
            return

        entries = set(giveaway.get("entries", set()))
        if interaction.user.id in entries:
            await interaction.response.send_message("You already entered this giveaway.", ephemeral=True)
            return

        entries.add(interaction.user.id)
        giveaway["entries"] = entries
        self._save_persistent_state()
        await interaction.response.send_message("You entered the giveaway!", ephemeral=True)

    @staticmethod
    def _safe_slash_name(raw_name: str) -> str:
        normalized = "".join(ch if (ch.isalnum() or ch in "-_") else "-" for ch in raw_name.lower())
        normalized = normalized.strip("-_")
        return normalized[:32]

    async def _register_slash_commands(self) -> None:
        self.tree.clear_commands(guild=None)
        for guild in list(self.guilds):
            self.tree.clear_commands(guild=guild)

        used_names: set[str] = set()
        for command_name in self.handler.command_names():
            if command_name in {
                "giveaway", "gwlist", "forceend", "gsban", "gsunban",
                "sr", "tar", "gar", "clear", "cleartranscript", "lockchannel", "unlock",
                "underdev", "disable", "enable",
                "underdev", "disable", "enable",
            }:
                continue
            slash_name = self._safe_slash_name(command_name)
            if not slash_name or slash_name in used_names:
                continue
            used_names.add(slash_name)

            description = self.handler.get_description_for(command_name) or "Bot command"

            async def callback(interaction: discord.Interaction, resolved_command: str = command_name) -> None:
                await self.reload_json_if_needed()
                response_text = self.handler.get_response_for(resolved_command)
                if response_text:
                    await interaction.response.send_message(response_text)
                    return
                await interaction.response.send_message("No response is configured for this command.", ephemeral=True)

            self.tree.add_command(app_commands.Command(name=slash_name, description=description, callback=callback))

        await self._register_giveaway_slash_commands()

    async def _register_giveaway_slash_commands(self) -> None:
        giveaway_group = app_commands.Group(name="giveaway", description="Create or manage giveaways")

        @giveaway_group.command(name="setup", description="Set the default ping role for giveaways")
        @app_commands.describe(role="Role to ping when a giveaway is created")
        async def giveaway_setup(
            interaction: discord.Interaction,
            role: discord.Role,
        ) -> None:
            if interaction.guild is None:
                await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
                return

            self.giveaway_ping_roles[interaction.guild.id] = role.id
            self._save_persistent_state()
            await interaction.response.send_message(f"Giveaway ping role set to {role.mention}.", ephemeral=True)

        @giveaway_group.command(name="create", description="Create a new giveaway")
        @app_commands.describe(
            prize="Prize to give away",
            description="Giveaway description",
            time="Duration like 1d_1h_1m_1s",
            winners="How many winners",
            role="Optional role to ping for this giveaway",
        )
        async def giveaway_create(
            interaction: discord.Interaction,
            prize: str,
            description: str,
            time: str,
            winners: int,
            role: discord.Role | None = None,
        ) -> None:
            if interaction.guild is None:
                await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
                return

            if winners <= 0:
                await interaction.response.send_message("Winners must be at least 1.", ephemeral=True)
                return

            selected_role_id = role.id if role is not None else self.giveaway_ping_roles.get(interaction.guild.id)

            await interaction.response.defer(ephemeral=True)
            try:
                giveaway_id = await self._create_giveaway(
                    channel=interaction.channel,
                    guild=interaction.guild,
                    host_user_id=interaction.user.id,
                    prize=prize,
                    description=description,
                    time_text=time,
                    winner_count=int(winners),
                    ping_role_id=selected_role_id,
                )
            except Exception as exc:
                await interaction.followup.send(f"Could not create giveaway: {exc}", ephemeral=True)
                return

            await interaction.followup.send(f"Giveaway created with ID `{giveaway_id}`.", ephemeral=True)

        self.tree.add_command(giveaway_group)

    def _build_global_moderation_audit_view(
        self,
        action: str,
        user_id: int,
        executor_id: int,
        reason: str,
    ) -> discord.ui.LayoutView:
        view = discord.ui.LayoutView(timeout=None)
        title = {
            "ban": "Global Server Ban",
            "unban": "Global Server Unban",
            "role sr": "Save all Roles Audit Logs",
            "role tar": "Take All Roles Audit Logs",
            "role gar": "Give all roles Audit Logs",
        }.get(action, f"Global Server {action.title()}")
        is_role_action = action.startswith("role ")
        executor_text = f"<:executer:1554605098251059280> ***Executer:*** <@{executor_id}>"
        action_details = (
            f"<:text:1554602725466181773> ***Role Results:*** {reason}"
            if is_role_action
            else f"<:text:1554602725466181773> ***Reason:*** {reason}"
        )
        view.add_item(
            discord.ui.Container(
                discord.ui.TextDisplay(f"# {title}"),
                discord.ui.Separator(),
                discord.ui.TextDisplay(
                    f"<:Person:1554596625060597911> ***User:*** <@{user_id}>\n"
                    f"<:Person_ID:1554601438980612136> ***User ID:*** {user_id}"
                ),
                discord.ui.Separator(),
                discord.ui.TextDisplay(executor_text),
                discord.ui.TextDisplay(action_details),
                discord.ui.Separator(),
                discord.ui.TextDisplay("-# Indiana State Roleplay | Audit Logs"),
                accent_color=discord.Color.dark_grey(),
            )
        )
        return view

    def _build_automod_audit_view(self, message: discord.Message, word: str, case_id: str) -> discord.ui.LayoutView:
        guild = message.guild
        user_id = message.author.id
        sentence = message.clean_content or message.content
        if len(sentence) > 1600:
            sentence = f"{sentence[:1597]}..."
        last_case = self.last_moderation_cases.get(f"{guild.id}:{user_id}", "N/A")
        channel_link = f"https://discord.com/channels/{guild.id}/{message.channel.id}"

        view = discord.ui.LayoutView(timeout=None)
        view.add_item(
            discord.ui.Container(
                discord.ui.TextDisplay("# Automod Triggered"),
                discord.ui.TextDisplay(f"***CC:*** <@&{AUTOMOD_CC_ROLE_ID}>"),
                discord.ui.Separator(),
                discord.ui.TextDisplay(
                    f"<:User:1554596625060597911> **User:** <@{user_id}>\n"
                    f"<:User_ID:1554601438980612136> **User ID:** {user_id}\n"
                    f"<:Case:1556407648125980894> **Last Case:** {last_case}"
                ),
                discord.ui.Separator(),
                discord.ui.TextDisplay(
                    f"<:text:1554602725466181773> **Blacklisted Word:** ||{word}||\n"
                    f"<:text:1554602725466181773> **Sentence Said in:** {sentence}"
                ),
                discord.ui.Separator(),
                discord.ui.TextDisplay(
                    f"<:Server:1556408987652595732> **Server:** {guild.name}\n"
                    f"<:Server:1556408987652595732> **Channel:** {channel_link}"
                ),
                discord.ui.Separator(),
                discord.ui.ActionRow(
                    discord.ui.Button(
                        label="Take Action",
                        style=discord.ButtonStyle.success,
                        custom_id=f"automod-case:take:{case_id}",
                    ),
                    discord.ui.Button(
                        label="Dismiss",
                        style=discord.ButtonStyle.danger,
                        custom_id=f"automod-case:dismiss:{case_id}",
                    ),
                ),
                discord.ui.Separator(),
                discord.ui.TextDisplay("-# Indiana State Roleplay | Audit Logs"),
                accent_color=discord.Color(0x242429),
            )
        )
        return view

    async def _handle_automod_message(self, message: discord.Message) -> bool:
        if message.guild is None or message.author.bot:
            return False
        if any(role.id == AUTOMOD_EXEMPT_ROLE_ID for role in getattr(message.author, "roles", ())):
            return False

        pattern = self.config_reloader.automod_pattern
        match = pattern.search(message.content) if pattern else None
        if match is None:
            return False

        case_id = str(message.id)
        if case_id in self.automod_cases:
            return True

        self.automod_cases[case_id] = {
            "guild_id": message.guild.id,
            "user_id": message.author.id,
            "word": match.group(0),
            "resolution": None,
            "resolved_by": None,
        }
        try:
            self._save_persistent_state()
        except OSError as exc:
            print(f"Could not persist automod case {case_id}: {exc}")

        audit_channel = self.get_channel(AUTOMOD_AUDIT_CHANNEL_ID)
        if audit_channel is None:
            try:
                audit_channel = await self.fetch_channel(AUTOMOD_AUDIT_CHANNEL_ID)
            except discord.HTTPException as exc:
                print(f"Could not fetch automod audit channel: {exc}")
                return True

        cc_role = message.guild.get_role(AUTOMOD_CC_ROLE_ID)
        try:
            audit_message = await audit_channel.send(
                view=self._build_automod_audit_view(message, match.group(0), case_id),
                allowed_mentions=discord.AllowedMentions(
                    roles=[cc_role] if cc_role else True,
                    users=False,
                    everyone=False,
                ),
            )
            self.automod_cases[case_id]["audit_message_id"] = audit_message.id
            self._save_persistent_state()
        except (discord.HTTPException, OSError) as exc:
            print(f"Could not send automod audit case {case_id}: {exc}")
        return True

    async def _handle_automod_case_interaction(
        self,
        interaction: discord.Interaction,
        custom_id: str,
    ) -> None:
        try:
            _, action, case_id = custom_id.split(":", maxsplit=2)
        except ValueError:
            await interaction.response.send_message("This automod action is invalid.", ephemeral=True)
            return

        case = self.automod_cases.get(case_id)
        if action not in {"take", "dismiss"} or case is None:
            await interaction.response.send_message("This automod case is no longer available.")
            return
        if interaction.guild is None or interaction.guild.id != int(case.get("guild_id", 0)):
            await interaction.response.send_message("This case belongs to another server.")
            return

        permissions = getattr(interaction.user, "guild_permissions", None)
        if not permissions or not (permissions.administrator or permissions.manage_messages):
            await interaction.response.send_message("You need Manage Messages permission to resolve this case.")
            return
        if case.get("resolution") is not None:
            await interaction.response.send_message("This automod case has already been resolved.")
            return

        resolution = "take" if action == "take" else "dismiss"
        case["resolution"] = resolution
        case["resolved_by"] = interaction.user.id
        try:
            self._save_persistent_state()
        except OSError as exc:
            case["resolution"] = None
            case["resolved_by"] = None
            await interaction.response.send_message(f"Could not save this case resolution: {exc}")
            return

        await interaction.response.edit_message(view=None)
        if action == "take":
            response = f"<@{interaction.user.id}> Has moderated the user."
        else:
            response = f"<@{interaction.user.id}> Has dismissed this case."
        await interaction.followup.send(
            response,
            allowed_mentions=discord.AllowedMentions(users=[interaction.user]),
        )

    def _command_access_denial(self, user_id: int) -> str | None:
        if user_id == BOT_CONTROL_OWNER_ID:
            return None
        if user_id in self.disabled_user_ids:
            return "Bot access has been disabled for your account."
        if self.underdev_enabled:
            return "The bot is under development; only the owner can use commands right now."
        return None

    def _is_command_message(self, content: str) -> bool:
        token = content.strip().split(maxsplit=1)[0] if content.strip() else ""
        if token == "?unlock":
            return True
        return any(
            token.startswith(prefix) and len(token) > len(prefix)
            for prefix in self.handler._candidate_prefixes()
        )

    async def _apply_presence(self) -> None:
        if self.underdev_enabled:
            await self.change_presence(
                status=discord.Status.idle,
                activity=discord.Game(name="⚠️ Bot Under Development"),
            )
            return

        activity_text = self.settings.get("activity_text", "Type !help")
        activity_type = self.settings.get("activity_type", "playing").lower()
        activity_map = {
            "playing": discord.ActivityType.playing,
            "watching": discord.ActivityType.watching,
            "listening": discord.ActivityType.listening,
        }
        selected_activity = activity_map.get(activity_type, discord.ActivityType.playing)
        await self.change_presence(
            status=discord.Status.online,
            activity=discord.Activity(type=selected_activity, name=activity_text),
        )

    async def _handle_bot_control_command(self, message: discord.Message) -> bool:
        parts = message.content.strip().split(maxsplit=2)
        if not parts:
            return False

        command_name = next(
            (
                parts[0][len(prefix):].lower()
                for prefix in self.handler._candidate_prefixes()
                if parts[0].startswith(prefix)
                and parts[0][len(prefix):].lower() in {"underdev", "disable", "enable"}
            ),
            None,
        )
        if command_name is None:
            return False
        if message.author.id != BOT_CONTROL_OWNER_ID:
            await message.channel.send("Only the bot owner can use this control command.")
            return True

        if command_name == "underdev":
            previous_state = self.underdev_enabled
            self.underdev_enabled = not previous_state
            try:
                self._save_persistent_state()
            except OSError as exc:
                self.underdev_enabled = previous_state
                await message.channel.send(f"Could not save under-development mode: {exc}")
                return True
            await self._apply_presence()
            state = "enabled" if self.underdev_enabled else "disabled"
            await message.channel.send(f"Under-development mode {state}.")
            return True

        if len(parts) < 3 or parts[1].lower() != "bot":
            await message.channel.send(f"Usage: {parts[0]} bot <user mention/user ID>")
            return True
        target_match = re.fullmatch(r"<@!?([0-9]+)>|([0-9]+)", parts[2])
        if target_match is None:
            await message.channel.send("Provide a user mention or numeric user ID.")
            return True

        target_id = int(target_match.group(1) or target_match.group(2))
        if target_id <= 0:
            await message.channel.send("Provide a valid user ID.")
            return True
        if target_id == BOT_CONTROL_OWNER_ID:
            await message.channel.send("The bot owner cannot be disabled.")
            return True

        if command_name == "disable":
            view = discord.ui.View(timeout=300)
            view.add_item(
                discord.ui.Button(
                    label="Disable bot",
                    style=discord.ButtonStyle.danger,
                    custom_id=f"bot-disable-confirm:{target_id}:{message.author.id}",
                )
            )
            await message.channel.send(
                f"***ARE YOU SURE YOU WANT TO DISABLE THE BOT FOR <@{target_id}>***\n"
                "-# if bowser is treating you with this BE SCARED!",
                view=view,
                allowed_mentions=discord.AllowedMentions.none(),
            )
            return True

        previous_state = target_id in self.disabled_user_ids
        self.disabled_user_ids.discard(target_id)
        try:
            self._save_persistent_state()
        except OSError as exc:
            if previous_state:
                self.disabled_user_ids.add(target_id)
            await message.channel.send(f"Could not enable bot access for <@{target_id}>: {exc}")
            return True
        await message.channel.send(
            f"Bot access enabled for <@{target_id}>.",
            allowed_mentions=discord.AllowedMentions.none(),
        )
        return True

    async def _handle_bot_control_interaction(
        self,
        interaction: discord.Interaction,
        custom_id: str,
    ) -> None:
        try:
            _, target_text, requester_text = custom_id.split(":", maxsplit=2)
            target_id = int(target_text)
            requester_id = int(requester_text)
        except (ValueError, TypeError):
            await interaction.response.send_message("This disable request is invalid.")
            return

        if interaction.user.id != BOT_CONTROL_OWNER_ID or requester_id != BOT_CONTROL_OWNER_ID:
            await interaction.response.send_message("Only the bot owner can confirm this request.")
            return
        if target_id == BOT_CONTROL_OWNER_ID:
            await interaction.response.send_message("The bot owner cannot be disabled.")
            return

        was_disabled = target_id in self.disabled_user_ids
        self.disabled_user_ids.add(target_id)
        try:
            self._save_persistent_state()
        except OSError as exc:
            if not was_disabled:
                self.disabled_user_ids.discard(target_id)
            await interaction.response.send_message(f"Could not disable bot access: {exc}")
            return

        await interaction.response.edit_message(
            content=f"Bot access disabled for <@{target_id}>.",
            view=None,
            allowed_mentions=discord.AllowedMentions.none(),
        )

    def _build_clear_audit_view(self, executor_id: int, cleared_count: int, transcript_id: str) -> discord.ui.LayoutView:
        view = discord.ui.LayoutView(timeout=None)
        view.add_item(
            discord.ui.Container(
                discord.ui.TextDisplay("# Clear Audit Log"),
                discord.ui.Separator(),
                discord.ui.TextDisplay(
                    f"<:executer:1554605098251059280> ***Executer:*** <@{executor_id}>\n"
                    f"<:Person_ID:1554601438980612136>\n***Executers ID:*** {executor_id}"
                ),
                discord.ui.Separator(),
                discord.ui.TextDisplay(
                    f"<:Clear:1554694929849122916> ***Ammount of Messages Cleared:*** {cleared_count}\n"
                    f"<:text:1554602725466181773> ***Message Transcript:*** `{transcript_id}`"
                ),
                discord.ui.Separator(),
                discord.ui.TextDisplay("-# Indiana State Roleplay | Audit Logs"),
                accent_color=discord.Color.dark_grey(),
            )
        )
        return view

    def _matches_prefix_command(self, token: str, command: str) -> bool:
        return any(
            token.startswith(prefix) and token[len(prefix):].lower() == command
            for prefix in self.handler._candidate_prefixes()
        )

    async def _handle_clear_command(self, message: discord.Message) -> bool:
        parts = message.content.strip().split(maxsplit=1)
        if not parts or not self._matches_prefix_command(parts[0], "clear"):
            return False

        if message.guild is None:
            await message.channel.send("This command can only be used in a server.")
            return True

        author_permissions = getattr(message.author, "guild_permissions", None)
        if not author_permissions or not (
            author_permissions.administrator or author_permissions.manage_messages
        ):
            await message.channel.send("You need Manage Messages permission to use this command.")
            return True

        bot_member = message.guild.me
        if bot_member is None or not message.channel.permissions_for(bot_member).manage_messages:
            await message.channel.send("The bot needs Manage Messages permission in this channel.")
            return True

        if len(parts) < 2:
            await message.channel.send("Usage: !clear <number of messages (1-1000)>")
            return True
        try:
            amount = int(parts[1])
        except ValueError:
            await message.channel.send("Message count must be a whole number from 1 to 1000.")
            return True
        if not 1 <= amount <= 1000:
            await message.channel.send("Message count must be from 1 to 1000.")
            return True

        status_message = await message.channel.send(
            f"<a:loading:1554695304152875038> Clearing **{amount}** messages..."
        )
        excluded_message_ids = {message.id, status_message.id}
        try:
            deleted_messages = await message.channel.purge(
                limit=amount + len(excluded_message_ids),
                check=lambda candidate: candidate.id != status_message.id,
                reason=f"Message clear by {message.author} ({message.author.id})",
            )
        except discord.Forbidden:
            await status_message.edit(content="The bot needs Manage Messages permission to clear this channel.")
            return True
        except discord.HTTPException as exc:
            await status_message.edit(content=f"Could not clear messages: {exc}")
            return True

        cleared_messages = [deleted for deleted in deleted_messages if deleted.id != message.id]
        transcript_id = str(message.id)
        transcript_lines = [
            f"Clear transcript {transcript_id}",
            f"Server: {message.guild.name} ({message.guild.id})",
            f"Channel: #{message.channel.name} ({message.channel.id})",
            f"Cleared by: {message.author} ({message.author.id})",
            f"Messages cleared: {len(cleared_messages)}",
            "",
        ]
        for deleted in reversed(cleared_messages):
            timestamp = deleted.created_at.astimezone(timezone.utc).isoformat()
            body = deleted.clean_content or "[no text content]"
            attachments = "\n".join(attachment.url for attachment in deleted.attachments)
            transcript_lines.append(f"[{timestamp}] {deleted.author} ({deleted.author.id}): {body}")
            if attachments:
                transcript_lines.append(f"Attachments: {attachments}")
        transcript = "\n".join(transcript_lines)
        self.clear_transcripts[transcript_id] = {
            "guild_id": message.guild.id,
            "channel_id": message.channel.id,
            "executor_id": message.author.id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "message_count": len(cleared_messages),
            "transcript": transcript,
        }
        try:
            self.clear_transcripts_store.save(self.clear_transcripts)
        except OSError as exc:
            await status_message.edit(
                content=f"Cleared **{len(cleared_messages)}** messages, but could not save the transcript: {exc}"
            )
            return True

        completion = (
            f"<:Clear:1554694929849122916> **{len(cleared_messages)}** messages have been cleared. "
            f"Transcript ID: `{transcript_id}`"
        )
        await status_message.edit(content=completion)
        audit_channel = self.get_channel(GLOBAL_BAN_AUDIT_CHANNEL_ID)
        if audit_channel is None:
            try:
                audit_channel = await self.fetch_channel(GLOBAL_BAN_AUDIT_CHANNEL_ID)
            except discord.HTTPException as exc:
                print(f"Could not fetch clear audit channel: {exc}")
                return True
        try:
            await audit_channel.send(
                view=self._build_clear_audit_view(message.author.id, len(cleared_messages), transcript_id),
                allowed_mentions=discord.AllowedMentions.none(),
            )
        except discord.HTTPException as exc:
            print(f"Could not send clear audit message: {exc}")
            await status_message.edit(content=f"{completion}\nThe clear audit log could not be sent.")
        return True

    async def _handle_clear_transcript_command(self, message: discord.Message) -> bool:
        parts = message.content.strip().split(maxsplit=1)
        if not parts or not self._matches_prefix_command(parts[0], "cleartranscript"):
            return False

        if message.guild is None:
            await message.channel.send("This command can only be used in a server.")
            return True
        if len(parts) < 2:
            await message.channel.send("Usage: !cleartranscript <transcript ID>")
            return True

        permissions = getattr(message.author, "guild_permissions", None)
        if not permissions or not (permissions.administrator or permissions.manage_messages):
            await message.channel.send("You need Manage Messages permission to retrieve clear transcripts.")
            return True

        transcript_id = parts[1].strip()
        transcript_entry = self.clear_transcripts.get(transcript_id)
        if not transcript_entry or int(transcript_entry.get("guild_id", 0)) != message.guild.id:
            await message.channel.send("No clear transcript with that ID exists for this server.")
            return True

        transcript_bytes = io.BytesIO(str(transcript_entry.get("transcript", "")).encode("utf-8"))
        await message.channel.send(
            f"Clear transcript `{transcript_id}`",
            file=discord.File(transcript_bytes, filename=f"clear-transcript-{transcript_id}.txt"),
        )
        return True

    def _build_channel_lock_embed(self, guild: discord.Guild, locked: bool) -> discord.Embed:
        state = "Locked" if locked else "Unlocked"
        action = "locked" if locked else "unlocked"
        embed = discord.Embed(
            description=(
                f"## *Channel {state}*\n"
                f"**This channel has been {action} by ISRP Ownership Team**\n"
                "-# ISRP Channel Lock/unlock System"
            ),
            color=discord.Color.dark_grey(),
        )
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        return embed

    async def _set_send_messages_overwrite(
        self,
        channel: discord.abc.GuildChannel,
        target: discord.Member | discord.Role,
        value: bool | None,
        reason: str,
    ) -> None:
        overwrite = channel.overwrites_for(target)
        overwrite.send_messages = value
        await channel.set_permissions(
            target,
            overwrite=None if overwrite.is_empty() else overwrite,
            reason=reason,
        )

    async def _handle_channel_lock_command(self, message: discord.Message) -> bool:
        parts = message.content.strip().split()
        if not parts:
            return False

        command_token = parts[0].lower()
        locked = self._matches_prefix_command(command_token, "lockchannel")
        unlocked = (
            self._matches_prefix_command(command_token, "unlock")
            or command_token in {"?unlock", "?unlockchannel"}
        )
        if not locked and not unlocked:
            return False

        if message.guild is None or not isinstance(message.channel, discord.abc.GuildChannel):
            await message.channel.send("This command can only be used in a server channel.")
            return True

        author_permissions = getattr(message.author, "guild_permissions", None)
        if not author_permissions or not (
            author_permissions.administrator or author_permissions.manage_channels
        ):
            await message.channel.send("You need Manage Channels permission to use this command.")
            return True

        guild = message.guild
        channel = message.channel
        everyone = guild.default_role
        locked_role = guild.get_role(CHANNEL_LOCK_ROLE_ID)
        bot_member = guild.me
        if locked_role is None:
            await channel.send("The configured channel-lock role is not present in this server.")
            return True
        if bot_member is None or not channel.permissions_for(bot_member).manage_channels:
            await channel.send("The bot needs Manage Channels permission in this channel.")
            return True

        channel_key = str(channel.id)
        reason = f"Channel {'lock' if locked else 'unlock'} by {message.author} ({message.author.id})"
        snapshot = self.channel_lock_snapshots.get(channel_key)

        if locked:
            if snapshot is None:
                snapshot = {
                    "guild_id": guild.id,
                    "channel_id": channel.id,
                    "overwrites": {
                        str(target.id): channel.overwrites_for(target).send_messages
                        for target in (everyone, locked_role, bot_member)
                    },
                }
                self.channel_lock_snapshots[channel_key] = snapshot
                try:
                    self._save_persistent_state()
                except OSError as exc:
                    self.channel_lock_snapshots.pop(channel_key, None)
                    await channel.send(f"Could not save channel permissions before locking: {exc}")
                    return True

            try:
                await self._set_send_messages_overwrite(channel, everyone, False, reason)
                await self._set_send_messages_overwrite(channel, locked_role, False, reason)
                await self._set_send_messages_overwrite(channel, bot_member, True, reason)
            except discord.HTTPException as exc:
                await channel.send(f"Could not lock this channel: {exc}")
                return True

            await channel.send(embed=self._build_channel_lock_embed(guild, locked))
            return True

        if snapshot is None or int(snapshot.get("guild_id", 0)) != guild.id:
            await channel.send("This channel has no saved lock state to restore.")
            return True

        original_overwrites = snapshot.get("overwrites", {})
        try:
            for target in (everyone, locked_role):
                original_value = original_overwrites.get(str(target.id))
                await self._set_send_messages_overwrite(channel, target, original_value, reason)
            await channel.send(embed=self._build_channel_lock_embed(guild, locked))
            await self._set_send_messages_overwrite(
                channel,
                bot_member,
                original_overwrites.get(str(bot_member.id)),
                reason,
            )
        except discord.HTTPException as exc:
            await channel.send(f"Could not fully unlock this channel: {exc}")
            return True

        self.channel_lock_snapshots.pop(channel_key, None)
        try:
            self._save_persistent_state()
        except OSError as exc:
            print(f"Could not clear saved channel lock state for {channel.id}: {exc}")
        return True

    def _build_global_ban_audit_view(self, user_id: int, executor_id: int, reason: str) -> discord.ui.LayoutView:
        return self._build_global_moderation_audit_view("ban", user_id, executor_id, reason)

    def _build_global_unban_audit_view(self, user_id: int, executor_id: int, reason: str) -> discord.ui.LayoutView:
        return self._build_global_moderation_audit_view("unban", user_id, executor_id, reason)

    async def _handle_global_server_ban(self, message: discord.Message) -> bool:
        return await self._handle_global_server_moderation(message, "ban")

    async def _handle_global_server_unban(self, message: discord.Message) -> bool:
        return await self._handle_global_server_moderation(message, "unban")

    async def _handle_global_server_moderation(self, message: discord.Message, action: str) -> bool:
        command_name = f"gs{action}"
        content = message.content.strip()
        parts = content.split(maxsplit=2)
        if not parts:
            return False

        command_token = parts[0]
        matched_prefix = next(
            (
                prefix
                for prefix in self.handler._candidate_prefixes()
                if command_token.startswith(prefix)
                and command_token[len(prefix):].lower() == command_name
            ),
            None,
        )
        if matched_prefix is None:
            return False

        if message.guild is None:
            await message.channel.send("This command can only be used in a server.")
            return True

        permissions = getattr(message.author, "guild_permissions", None)
        if not permissions or not permissions.administrator:
            await message.channel.send("You need Administrator permission to use this command.")
            return True

        if len(parts) < 3:
            await message.channel.send(f"Usage: {matched_prefix}gsban <user mention/user ID> <reason>")
            return True

        target_match = re.fullmatch(r"<@!?([0-9]+)>|([0-9]+)", parts[1])
        if target_match is None:
            await message.channel.send("Provide a user mention or numeric user ID.")
            return True

        user_id = int(target_match.group(1) or target_match.group(2))
        if user_id <= 0:
            await message.channel.send("Provide a valid user ID.")
            return True
        if action == "ban" and self.user is not None and user_id == self.user.id:
            await message.channel.send("The bot cannot ban itself.")
            return True

        reason = parts[2].strip()
        if not reason:
            await message.channel.send(f"Usage: {matched_prefix}gsban <user mention/user ID> <reason>")
            return True

        guilds = list(self.guilds)
        verb = "Banning" if action == "ban" else "Unbanning"
        participle = "banned" if action == "ban" else "unbanned"
        status_message = await message.channel.send(
            f"<:loading:1554612448445726741> {verb} user from **{len(guilds)}**"
        )

        audit_reason = f"Global {action} by {message.author} ({message.author.id}): {reason}"[:512]
        succeeded = 0
        succeeded_guild_ids: list[int] = []
        failed = 0
        not_banned = 0
        target = discord.Object(id=user_id)
        for guild in guilds:
            try:
                if action == "ban":
                    await guild.ban(target, reason=audit_reason)
                else:
                    await guild.unban(target, reason=audit_reason)
                succeeded += 1
                succeeded_guild_ids.append(guild.id)
            except discord.NotFound as exc:
                if action == "unban":
                    not_banned += 1
                else:
                    failed += 1
                    print(f"Global ban failed in guild {guild.id}: {exc}")
            except discord.HTTPException as exc:
                failed += 1
                print(f"Global {action} failed in guild {guild.id}: {exc}")

        if action == "ban" and succeeded_guild_ids:
            for guild_id in succeeded_guild_ids:
                self.last_moderation_cases[f"{guild_id}:{user_id}"] = "Ban"
            try:
                self._save_persistent_state()
            except OSError as exc:
                print(f"Could not persist last moderation case for user {user_id}: {exc}")

        if succeeded:
            completion = f"<:tick:1554606894889312407> User has been {participle} from **{succeeded}**."
        elif action == "unban" and guilds and not_banned == len(guilds) and not failed:
            completion = "User was not banned in any server."
        else:
            completion = f"Could not {action} the user in any server. Check the bot's permissions."

        if failed:
            completion += f"\n{verb} failed in **{failed}** server(s); check the bot's permissions there."
        if not_banned and (succeeded or failed):
            completion += f"\nUser was not banned in **{not_banned}** server(s)."
        await status_message.edit(content=completion)

        if succeeded:
            audit_channel = self.get_channel(GLOBAL_BAN_AUDIT_CHANNEL_ID)
            if audit_channel is None:
                try:
                    audit_channel = await self.fetch_channel(GLOBAL_BAN_AUDIT_CHANNEL_ID)
                except discord.HTTPException as exc:
                    print(f"Could not fetch global ban audit channel: {exc}")
                    return True

            try:
                await audit_channel.send(
                    view=self._build_global_moderation_audit_view(action, user_id, message.author.id, reason),
                    allowed_mentions=discord.AllowedMentions.none(),
                )
            except discord.HTTPException as exc:
                print(f"Could not send global {action} audit message: {exc}")
                await status_message.edit(content=f"{completion}\nThe {action}s completed, but the audit log could not be sent.")

        return True

    async def _handle_global_role_command(self, message: discord.Message) -> bool:
        parts = message.content.strip().split(maxsplit=1)
        if not parts:
            return False

        command_name = parts[0]
        action = next(
            (
                candidate
                for candidate in ("sr", "tar", "gar")
                for prefix in self.handler._candidate_prefixes()
                if command_name.startswith(prefix)
                and command_name[len(prefix):].lower() == candidate
            ),
            None,
        )
        if action is None:
            return False

        if message.guild is None:
            await message.channel.send("This command can only be used in a server.")
            return True

        permissions = getattr(message.author, "guild_permissions", None)
        if not permissions or not permissions.administrator:
            await message.channel.send("You need Administrator permission to use this command.")
            return True

        if len(parts) < 2:
            await message.channel.send(f"Usage: {command_name} <user mention/user ID>")
            return True

        target_match = re.fullmatch(r"<@!?([0-9]+)>|([0-9]+)", parts[1])
        if target_match is None:
            await message.channel.send("Provide a user mention or numeric user ID.")
            return True

        user_id = int(target_match.group(1) or target_match.group(2))
        if user_id <= 0:
            await message.channel.send("Provide a valid user ID.")
            return True
        guild = message.guild
        try:
            member = guild.get_member(user_id) or await guild.fetch_member(user_id)
        except discord.NotFound:
            await message.channel.send("That user is not a member of this server.")
            return True
        except discord.HTTPException as exc:
            await message.channel.send(f"Could not fetch that server member: {exc}")
            return True

        threshold_role = guild.get_role(ROLE_THRESHOLD_ROLE_ID)
        if threshold_role is None:
            await message.channel.send("The configured role threshold is not present in this server.")
            return True

        eligible_roles = [
            role
            for role in member.roles
            if role.position >= threshold_role.position and role.is_assignable()
        ]
        saved_for_user = self.saved_roles.get(str(user_id), {})
        guild_key = str(guild.id)
        unavailable_roles = 0

        if action == "gar":
            saved_role_ids = {int(role_id) for role_id in saved_for_user.get(guild_key, [])}
            roles_by_id = {role.id: role for role in guild.roles}
            selected_roles = [
                roles_by_id[role_id]
                for role_id in saved_role_ids
                if role_id in roles_by_id
                and roles_by_id[role_id].position >= threshold_role.position
                and roles_by_id[role_id].is_assignable()
            ]
            unavailable_roles = len(saved_role_ids) - len(selected_roles)
            current_role_ids = {role.id for role in member.roles}
            selected_roles = [role for role in selected_roles if role.id not in current_role_ids]
            if not saved_role_ids:
                await message.channel.send("No saved roles found. Run !sr for this user first.")
                return True
        else:
            selected_roles = eligible_roles

        verb = {"sr": "Saving", "tar": "Removing", "gar": "Giving"}[action]
        status_message = await message.channel.send(
            f"<a:loading:1554695304152875038> {verb} Roles to <@{user_id}> "
            f"Number of roles: **{len(selected_roles)}**"
        )

        if action in {"sr", "tar"}:
            self.saved_roles.setdefault(str(user_id), {})[guild_key] = [role.id for role in eligible_roles]
            try:
                self.saved_roles_store.save(self.saved_roles)
            except OSError as exc:
                completion = f"Could not save the role snapshot: {exc}"
                await status_message.edit(content=completion)
                return True

        changed_roles = 0
        failed_roles = 0
        try:
            if action == "tar" and selected_roles:
                await member.remove_roles(*selected_roles, reason=f"Global role removal by {message.author} ({message.author.id})")
                changed_roles = len(selected_roles)
            elif action == "gar" and selected_roles:
                await member.add_roles(*selected_roles, reason=f"Global role restore by {message.author} ({message.author.id})")
                changed_roles = len(selected_roles)
            elif action == "sr":
                changed_roles = len(eligible_roles)
        except discord.HTTPException as exc:
            failed_roles = len(selected_roles)
            print(f"Role command {action} failed in guild {guild.id}: {exc}")

        completion_verb = {"sr": "saved", "tar": "removed", "gar": "given"}[action]
        completion = f"<:tick:1554606894889312407> {completion_verb.title()} **{changed_roles}** role(s) for <@{user_id}>."
        if failed_roles:
            completion += f"\nCould not update **{failed_roles}** role(s); check the bot's role position and permissions."
        if unavailable_roles:
            completion += f"\nCould not restore **{unavailable_roles}** saved role(s) because they are missing or not manageable."
        await status_message.edit(content=completion)

        audit_details = f"Roles affected: {changed_roles}; failed: {failed_roles}; unavailable: {unavailable_roles}"
        try:
            audit_channel = self.get_channel(GLOBAL_BAN_AUDIT_CHANNEL_ID)
            if audit_channel is None:
                audit_channel = await self.fetch_channel(GLOBAL_BAN_AUDIT_CHANNEL_ID)
            await audit_channel.send(
                view=self._build_global_moderation_audit_view(
                    f"role {action}", user_id, message.author.id, audit_details
                ),
                allowed_mentions=discord.AllowedMentions.none(),
            )
        except (AttributeError, discord.HTTPException) as exc:
            print(f"Could not send global role audit message: {exc}")
            await status_message.edit(content=f"{completion}\nThe role action completed, but the audit log could not be sent.")

        return True

    async def reload_json_if_needed(self) -> None:
        try:
            changed, command_schema_changed = self.config_reloader.reload_if_changed()
        except ConfigError as exc:
            print(f"Config reload failed: {exc}")
            return

        if not changed:
            return

        self.settings = self.config_reloader.settings
        self.categories = self.config_reloader.categories
        self.handler.update_data(
            settings=self.config_reloader.settings,
            commands=self.config_reloader.commands,
            responses=self.config_reloader.responses,
        )

        if changed:
            await self._register_slash_commands()
            if self.settings.get("sync_slash_on_change", True):
                await self._sync_slash_commands()

        print("JSON config reloaded.")

    async def force_reload(self) -> tuple[bool, bool]:
        settings, commands, responses, categories = load_all_config(self.config_reloader.base_path)
        automod_words = _load_automod_words(self.config_reloader.automod_path)
        previous_commands = self.config_reloader.commands

        self.config_reloader.settings = settings
        self.config_reloader.commands = commands
        self.config_reloader.responses = responses
        self.config_reloader.categories = categories
        self.config_reloader.automod_words = automod_words
        self.config_reloader.automod_pattern = _compile_automod_words(automod_words)
        self.config_reloader._refresh_mtimes()

        self.settings = settings
        self.categories = categories
        self.handler.update_data(settings=settings, commands=commands, responses=responses)

        command_schema_changed = previous_commands != commands
        await self._register_slash_commands()
        if self.settings.get("sync_slash_on_change", True):
            await self._sync_slash_commands()

        return True, command_schema_changed

    async def handle_reload_command(self, message: discord.Message) -> bool:
        content = message.content.strip()
        normalized_content = content.lower()
        prefix = None
        for candidate_prefix in [str(self.settings.get("prefix", "!")).strip() or "!", "-"]:
            if normalized_content.startswith(f"{candidate_prefix}reload"):
                prefix = candidate_prefix
                break

        if prefix is None:
            return False

        parts = content.split(maxsplit=1)
        if len(parts) < 2:
            await message.channel.send(f"Usage: {prefix}reload <catagory>")
            return True

        requested_category = parts[1].strip().lower()
        if not requested_category:
            await message.channel.send(f"Usage: {prefix}reload <catagory>")
            return True

        await self.reload_json_if_needed()
        category_files = self.categories.get(requested_category)
        if category_files is None:
            available = ", ".join(sorted(self.categories)) or "none"
            await message.channel.send(f"Unknown catagory `{requested_category}`. Available: {available}")
            return True

        try:
            _, command_schema_changed = await self.force_reload()
        except ConfigError as exc:
            await message.channel.send(f"Reload failed: {exc}")
            return True

        await self._register_slash_commands()
        if self.settings.get("sync_slash_on_change", True):
            await self._sync_slash_commands()

        file_list = ", ".join(category_files) if category_files else "no files listed"
        slash_text = " and slash commands synced" if command_schema_changed or requested_category.lower() in {"commands", "giveaway", "settings"} else ""
        await message.channel.send(f"Reloaded catagory `{requested_category}`: {file_list}{slash_text}")
        return True

    async def on_ready(self) -> None:
        await self.reload_json_if_needed()
        for giveaway_id, giveaway in self.giveaways.items():
            if not giveaway.get("ended") or not giveaway.get("result_posted"):
                self._schedule_giveaway(giveaway_id)
        await self._apply_presence()
        print(f"Logged in as {self.user} (ID: {self.user.id})")

    async def on_message(self, message: discord.Message) -> None:
        await self.reload_json_if_needed()
        if message.author.bot:
            return
        if await self._handle_automod_message(message):
            return
        if self._is_command_message(message.content):
            denial = self._command_access_denial(message.author.id)
            if denial:
                await message.channel.send(denial)
                return
            if await self._handle_bot_control_command(message):
                return
        if await self._handle_clear_transcript_command(message):
            return
        if await self._handle_clear_command(message):
            return
        if await self._handle_channel_lock_command(message):
            return
        if await self.handle_reload_command(message):
            return
        if await self._handle_global_server_ban(message):
            return
        if await self._handle_global_server_unban(message):
            return
        if await self._handle_global_role_command(message):
            return

        content = message.content.strip()
        prefixes = {self.settings.get("prefix", "!"), "-"}
        matched_prefix = next((prefix for prefix in prefixes if content.lower().startswith(f"{prefix}gwlist")), None)
        if matched_prefix is not None:
            parts = content.split(maxsplit=1)
            if len(parts) < 2:
                await message.channel.send(f"Usage: {matched_prefix}gwlist <giveaway_id>")
                return
            try:
                giveaway_id = int(parts[1].strip())
            except ValueError:
                await message.channel.send("Giveaway ID must be a number.")
                return
            giveaway = self.giveaways.get(giveaway_id)
            if giveaway is None:
                await message.channel.send(f"Could not find a giveaway with ID `{giveaway_id}`.")
                return
            embed = self._build_giveaway_entry_embed(giveaway, message.guild)
            await message.channel.send(embed=embed)
            return

        matched_prefix = next((prefix for prefix in prefixes if content.lower().startswith(f"{prefix}forceend")), None)
        if matched_prefix is not None:
            parts = content.split(maxsplit=1)
            if len(parts) < 2:
                await message.channel.send(f"Usage: {matched_prefix}forceend <giveaway_id>")
                return
            try:
                giveaway_id = int(parts[1].strip())
            except ValueError:
                await message.channel.send("Giveaway ID must be a number.")
                return
            giveaway = self.giveaways.get(giveaway_id)
            if giveaway is None:
                await message.channel.send(f"Could not find a giveaway with ID `{giveaway_id}`.")
                return
            await self._finish_giveaway(giveaway_id)
            await message.channel.send(f"Force ended giveaway `{giveaway_id}`.")
            return

        await self.handler.handle_message(message)
