from __future__ import annotations

import asyncio
import json
import os
import random
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

import discord
from discord import app_commands

from .handlers import MessageHandler
from .json_store import JsonStore


class ConfigError(Exception):
    pass


def resolve_token(settings: dict[str, Any]) -> str:
    env_token = os.getenv("DISCORD_BOT_TOKEN", "").strip()
    if env_token:
        return env_token

    file_token = str(settings.get("token", "")).strip()
    if file_token and file_token != "PUT_YOUR_DISCORD_BOT_TOKEN_HERE":
        return file_token

    raise ConfigError("Set DISCORD_BOT_TOKEN in the environment or put your bot token in config/settings.json before running.")


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


def load_all_config(base_path: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, str], dict[str, list[str]]]:
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
        self.commands_dir = base_path / "commands"

        self.settings: dict[str, Any] = {}
        self.commands: dict[str, Any] = {}
        self.responses: dict[str, str] = {}
        self.categories: dict[str, list[str]] = {}
        self._file_mtimes: dict[Path, int] = {}

    def load_initial(self) -> None:
        settings, commands, responses, categories = load_all_config(self.base_path)
        self.settings = settings
        self.commands = commands
        self.responses = responses
        self.categories = categories
        self._refresh_mtimes()

    def _tracked_files(self) -> list[Path]:
        tracked = [self.settings_path, self.commands_path, self.responses_path, self.categories_path]
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

        settings["token"] = resolve_token(settings)

        command_schema_changed = old_commands != commands

        self.settings = settings
        self.commands = commands
        self.responses = responses
        self.categories = categories
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

        self.tree = app_commands.CommandTree(self)
        self.settings = settings
        self.handler = MessageHandler(settings=settings, commands=commands, responses=responses)
        self.categories = self.config_reloader.categories
        self.giveaways: dict[int, dict[str, Any]] = {}
        self.giveaway_ping_roles: dict[int, int] = {}

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
        if not giveaway or giveaway.get("ended"):
            return

        wait_for = max(0, int(giveaway.get("end_ts", 0) or 0) - int(datetime.now(timezone.utc).timestamp()))
        await asyncio.sleep(wait_for)

        giveaway = self.giveaways.get(giveaway_id)
        if not giveaway or giveaway.get("ended"):
            return

        giveaway["ended"] = True
        guild = self.get_guild(int(giveaway.get("guild_id", 0) or 0)) if self.get_guild(int(giveaway.get("guild_id", 0) or 0)) else None
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

        entries = list(giveaway.get("entries", set()))
        if not entries:
            await channel.send(f"🎉 Giveaway ended for **{giveaway.get('prize', 'Giveaway')}** with no entries.")
            return

        winner_count = min(int(giveaway.get("winner_count", 1) or 1), len(entries))
        winners = random.sample(entries, k=winner_count)
        winner_mentions = ", ".join(f"<@{winner_id}>" for winner_id in winners)
        await channel.send(f"<:Tada:1529950839479865394> {winner_mentions} has won **{giveaway.get('prize', 'Giveaway')}**!")

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
            "channel_id": getattr(channel, "id", None),
            "message_id": None,
            "host_user_id": int(host_user_id),
            "guild_id": getattr(guild, "id", None),
            "ping_role_id": int(ping_role_id) if ping_role_id else None,
        }
        self.giveaways[giveaway_id] = giveaway
        content = f"<@&{ping_role_id}>" if ping_role_id else None
        message = await channel.send(
            content=content,
            embed=self._build_giveaway_embed(giveaway, guild),
            allowed_mentions=discord.AllowedMentions(roles=True),
        )
        giveaway["message_id"] = message.id
        asyncio.create_task(self._finish_giveaway(giveaway_id))
        return giveaway_id

    async def setup_hook(self) -> None:
        await self._register_slash_commands()
        if self.settings.get("sync_slash_on_startup", True):
            await self.tree.sync()

    @staticmethod
    def _safe_slash_name(raw_name: str) -> str:
        normalized = "".join(ch if (ch.isalnum() or ch in "-_") else "-" for ch in raw_name.lower())
        normalized = normalized.strip("-_")
        return normalized[:32]

    async def _register_slash_commands(self) -> None:
        self.tree.clear_commands(guild=None)

        used_names: set[str] = set()
        for command_name in self.handler.command_names():
            if command_name in {"giveaway", "gwlist", "forceend"}:
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
        @self.tree.command(name="giveaway", description="Create or configure a giveaway")
        @app_commands.describe(
            action="Choose ping or create",
            prize="Prize to give away",
            description="Giveaway description",
            time="Duration like 1d_1h_1m_1s",
            winners="How many winners",
            role="Role to ping for the giveaway",
        )
        @app_commands.choices(action=[
            app_commands.Choice(name="ping", value="ping"),
            app_commands.Choice(name="create", value="create"),
        ])
        async def giveaway_command(
            interaction: discord.Interaction,
            action: str = "create",
            prize: str | None = None,
            description: str | None = None,
            time: str | None = None,
            winners: int | None = None,
            role: discord.Role | None = None,
        ) -> None:
            if interaction.guild is None:
                await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
                return
            if action.lower() == "ping":
                if role is None:
                    await interaction.response.send_message("Please provide a role to ping.", ephemeral=True)
                    return
                self.giveaway_ping_roles[interaction.guild.id] = role.id
                await interaction.response.send_message(f"Giveaway ping role set to {role.mention}.", ephemeral=True)
                return

            if not prize or not description or not time or winners is None:
                await interaction.response.send_message("Usage: /giveaway create prize:... description:... time:... winners:...", ephemeral=True)
                return

            if winners <= 0:
                await interaction.response.send_message("Winners must be at least 1.", ephemeral=True)
                return

            selected_role_id = None
            if role is not None:
                selected_role_id = role.id
            else:
                selected_role_id = self.giveaway_ping_roles.get(interaction.guild.id)

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

        if command_schema_changed:
            await self._register_slash_commands()
            if self.settings.get("sync_slash_on_change", True):
                await self.tree.sync()

        print("JSON config reloaded.")

    async def force_reload(self) -> tuple[bool, bool]:
        settings, commands, responses, categories = load_all_config(self.config_reloader.base_path)
        previous_commands = self.config_reloader.commands

        self.config_reloader.settings = settings
        self.config_reloader.commands = commands
        self.config_reloader.responses = responses
        self.config_reloader.categories = categories
        self.config_reloader._refresh_mtimes()

        self.settings = settings
        self.categories = categories
        self.handler.update_data(settings=settings, commands=commands, responses=responses)

        command_schema_changed = previous_commands != commands
        if command_schema_changed:
            await self._register_slash_commands()
            if self.settings.get("sync_slash_on_change", True):
                await self.tree.sync()

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
            await self.tree.sync()

        file_list = ", ".join(category_files) if category_files else "no files listed"
        slash_text = " and slash commands synced" if command_schema_changed or requested_category.lower() in {"commands", "giveaway", "settings"} else ""
        await message.channel.send(f"Reloaded catagory `{requested_category}`: {file_list}{slash_text}")
        return True

    async def on_ready(self) -> None:
        await self.reload_json_if_needed()
        activity_text = self.settings.get("activity_text", "Type !help")
        activity_type = self.settings.get("activity_type", "playing").lower()

        activity_map = {
            "playing": discord.ActivityType.playing,
            "watching": discord.ActivityType.watching,
            "listening": discord.ActivityType.listening,
        }
        selected_activity = activity_map.get(activity_type, discord.ActivityType.playing)

        await self.change_presence(activity=discord.Activity(type=selected_activity, name=activity_text))
        print(f"Logged in as {self.user} (ID: {self.user.id})")

    async def on_message(self, message: discord.Message) -> None:
        await self.reload_json_if_needed()
        if message.author.bot:
            return
        if await self.handle_reload_command(message):
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
