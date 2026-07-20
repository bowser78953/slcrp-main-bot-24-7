from __future__ import annotations

from pathlib import Path
from typing import Any

import discord
from discord import app_commands

from .handlers import MessageHandler
from .json_store import JsonStore


class ConfigError(Exception):
    pass


def load_all_config(base_path: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, str]]:
    settings_store = JsonStore(base_path / "config" / "settings.json")
    commands_store = JsonStore(base_path / "config" / "commands.json")
    responses_store = JsonStore(base_path / "data" / "responses.json")

    settings = settings_store.load()
    commands = commands_store.load()
    responses = responses_store.load()

    token = settings.get("token", "")
    if not token or token == "PUT_YOUR_DISCORD_BOT_TOKEN_HERE":
        raise ConfigError("Set your bot token in config/settings.json before running.")

    return settings, commands, responses


class ConfigReloader:
    def __init__(self, base_path: Path):
        self.settings_path = base_path / "config" / "settings.json"
        self.commands_path = base_path / "config" / "commands.json"
        self.responses_path = base_path / "data" / "responses.json"

        self.settings_store = JsonStore(self.settings_path)
        self.commands_store = JsonStore(self.commands_path)
        self.responses_store = JsonStore(self.responses_path)

        self.settings: dict[str, Any] = {}
        self.commands: dict[str, Any] = {}
        self.responses: dict[str, str] = {}
        self._file_mtimes: dict[Path, int] = {}

    def load_initial(self) -> None:
        settings, commands, responses = load_all_config(self.settings_path.parent.parent)
        self.settings = settings
        self.commands = commands
        self.responses = responses
        self._refresh_mtimes()

    def _refresh_mtimes(self) -> None:
        self._file_mtimes = {
            self.settings_path: self.settings_path.stat().st_mtime_ns,
            self.commands_path: self.commands_path.stat().st_mtime_ns,
            self.responses_path: self.responses_path.stat().st_mtime_ns,
        }

    def _files_changed(self) -> bool:
        for path, old_mtime in self._file_mtimes.items():
            if path.stat().st_mtime_ns != old_mtime:
                return True
        return False

    def reload_if_changed(self) -> tuple[bool, bool]:
        if not self._file_mtimes:
            return False, False

        if not self._files_changed():
            return False, False

        old_commands = self.commands

        settings = self.settings_store.load()
        commands = self.commands_store.load()
        responses = self.responses_store.load()

        token = settings.get("token", "")
        if not token or token == "PUT_YOUR_DISCORD_BOT_TOKEN_HERE":
            raise ConfigError("Set your bot token in config/settings.json before running.")

        command_schema_changed = old_commands != commands

        self.settings = settings
        self.commands = commands
        self.responses = responses
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

        self.settings = settings
        self.handler = MessageHandler(settings=settings, commands=commands, responses=responses)

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

    async def reload_json_if_needed(self) -> None:
        try:
            changed, command_schema_changed = self.config_reloader.reload_if_changed()
        except ConfigError as exc:
            print(f"Config reload failed: {exc}")
            return

        if not changed:
            return

        self.settings = self.config_reloader.settings
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
        await self.handler.handle_message(message)
