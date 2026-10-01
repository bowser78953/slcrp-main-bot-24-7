from __future__ import annotations

import asyncio
import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

from shift_types import has_setup_access


DATA_DIR = Path(os.getenv("VORTEX_DATA_DIR", str(Path(__file__).resolve().parent))).expanduser()
ERLC_CONNECTIONS_PATH = DATA_DIR / "erlc_connections.json"
ERLC_API_BASE = "https://api.erlc.gg"
COMMAND_INTERVAL_SECONDS = 5.0
MAX_CONNECTIONS_PER_GUILD = 25
COMMAND_NAME_CACHE_SECONDS = 60.0
_last_command_at: dict[str, float] = {}
_command_locks: dict[str, asyncio.Lock] = {}
_invalid_server_keys: set[str] = set()
_command_name_cache: dict[str, tuple[float, list[str]]] = {}


class ERLCAPIError(Exception):
    pass


def load_all_connections() -> dict[str, dict[str, dict[str, str]]]:
    if not ERLC_CONNECTIONS_PATH.exists():
        return {}

    with ERLC_CONNECTIONS_PATH.open("r", encoding="utf-8") as data_file:
        data: Any = json.load(data_file)
    if not isinstance(data, dict):
        raise ValueError("erlc_connections.json must be an object keyed by Discord server ID.")
    return data


def save_all_connections(data: dict[str, dict[str, dict[str, str]]]) -> None:
    with ERLC_CONNECTIONS_PATH.open("w", encoding="utf-8") as data_file:
        json.dump(data, data_file, indent=2)
        data_file.write("\n")


def list_connections(guild_id: int) -> dict[str, dict[str, str]]:
    return load_all_connections().get(str(guild_id), {})


def get_connection(guild_id: int, alias: str) -> dict[str, str] | None:
    return list_connections(guild_id).get(alias.strip().casefold())


def save_connection(guild_id: int, alias: str, server_key: str, server_name: str) -> None:
    data = load_all_connections()
    guild_connections = data.setdefault(str(guild_id), {})
    normalized_alias = alias.strip().casefold()
    guild_connections[normalized_alias] = {
        "name": alias.strip(),
        "server_name": server_name.strip() or alias.strip(),
        "server_key": server_key.strip(),
    }
    _invalid_server_keys.discard(hashlib.sha256(server_key.strip().encode("utf-8")).hexdigest())
    save_all_connections(data)


def remove_connection(guild_id: int, alias: str) -> bool:
    data = load_all_connections()
    guild_connections = data.get(str(guild_id), {})
    removed = guild_connections.pop(alias, None) is not None
    if not guild_connections:
        data.pop(str(guild_id), None)
    if removed:
        save_all_connections(data)
    return removed


async def validate_server_key(server_key: str) -> str:
    key_id = hashlib.sha256(server_key.encode("utf-8")).hexdigest()
    if key_id in _invalid_server_keys:
        raise ERLCAPIError(
            "This ER:LC key was previously rejected. Use a current key before verifying again."
        )

    timeout = aiohttp.ClientTimeout(total=15)
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(
                f"{ERLC_API_BASE}/v2/server",
                headers={"server-key": server_key},
            ) as response:
                try:
                    body = await response.json(content_type=None)
                except (ValueError, aiohttp.ContentTypeError):
                    body = {}
                if response.status == 200:
                    return str(body.get("Name") or "ER:LC server")
                if response.status == 403:
                    _invalid_server_keys.add(key_id)
                    raise ERLCAPIError(
                        "ER:LC rejected this server key. Check that it is current, then try once more."
                    )
                if response.status == 429:
                    retry_after = response.headers.get("Retry-After", "a short time")
                    raise ERLCAPIError(f"ER:LC rate-limited the verification. Retry after {retry_after} seconds.")
                raise ERLCAPIError(f"ER:LC key verification failed (HTTP {response.status}).")
    except asyncio.TimeoutError as exc:
        raise ERLCAPIError("ER:LC did not respond before the verification timed out.") from exc
    except aiohttp.ClientError as exc:
        raise ERLCAPIError("Could not connect to the ER:LC API. Try again later.") from exc


async def run_erlc_command(server_key: str, command_text: str) -> str:
    key_id = hashlib.sha256(server_key.encode("utf-8")).hexdigest()
    if key_id in _invalid_server_keys:
        raise ERLCAPIError(
            "This ER:LC key was previously rejected. Update and verify the connection before trying again."
        )
    lock = _command_locks.setdefault(key_id, asyncio.Lock())
    loop = asyncio.get_running_loop()
    async with lock:
        remaining = COMMAND_INTERVAL_SECONDS - (loop.time() - _last_command_at.get(key_id, 0.0))
        if remaining > 0:
            raise ERLCAPIError(
                f"This ER:LC server accepts one command every five seconds. Wait {remaining:.1f}s."
            )
        _last_command_at[key_id] = loop.time()

        timeout = aiohttp.ClientTimeout(total=15)
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    f"{ERLC_API_BASE}/v1/server/command",
                    headers={"server-key": server_key},
                    json={"command": command_text},
                ) as response:
                    try:
                        body = await response.json(content_type=None)
                    except (ValueError, aiohttp.ContentTypeError):
                        body = {}
                    if response.status == 200:
                        return str(body.get("message") or "Command sent to ER:LC.")
                    if response.status == 403:
                        _invalid_server_keys.add(key_id)
                        raise ERLCAPIError(
                            "ER:LC rejected this server key. It may have been regenerated; update the connection before retrying."
                        )
                    if response.status == 422:
                        raise ERLCAPIError(
                            "The ER:LC server is offline or has no players, so it could not run the command."
                        )
                    if response.status == 429:
                        retry_after = response.headers.get("Retry-After") or body.get("retry_after")
                        if retry_after is not None:
                            try:
                                _last_command_at[key_id] = loop.time() + max(
                                    0.0,
                                    float(retry_after) - COMMAND_INTERVAL_SECONDS,
                                )
                            except (TypeError, ValueError):
                                pass
                        raise ERLCAPIError(
                            f"ER:LC rate-limited this request. Retry after {retry_after or 'the indicated wait period'}."
                        )
                    message = body.get("message")
                    raise ERLCAPIError(
                        f"ER:LC rejected the command (HTTP {response.status})"
                        + (f": {message}" if message else ".")
                    )
        except asyncio.TimeoutError as exc:
            raise ERLCAPIError("ER:LC did not respond before the command timed out.") from exc
        except aiohttp.ClientError as exc:
            raise ERLCAPIError("Could not connect to the ER:LC API. Try again later.") from exc


async def fetch_command_names(server_key: str) -> list[str]:
    key_id = hashlib.sha256(server_key.encode("utf-8")).hexdigest()
    cached = _command_name_cache.get(key_id)
    now = time.monotonic()
    if cached and now - cached[0] < COMMAND_NAME_CACHE_SECONDS:
        return list(cached[1])
    if key_id in _invalid_server_keys:
        raise ERLCAPIError("This ER:LC key was rejected. Reconnect it before fetching command names.")

    timeout = aiohttp.ClientTimeout(total=2.5)
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(
                f"{ERLC_API_BASE}/v1/server/commandlogs",
                headers={"server-key": server_key},
            ) as response:
                try:
                    body = await response.json(content_type=None)
                except (ValueError, aiohttp.ContentTypeError):
                    body = []
                if response.status == 403:
                    _invalid_server_keys.add(key_id)
                    raise ERLCAPIError("ER:LC rejected this server key. Reconnect it before retrying.")
                if response.status == 429:
                    retry_after = response.headers.get("Retry-After", "a short time")
                    raise ERLCAPIError(f"ER:LC rate-limited command suggestions. Retry after {retry_after} seconds.")
                if response.status != 200:
                    raise ERLCAPIError(f"Could not fetch ER:LC command suggestions (HTTP {response.status}).")

                names: list[str] = []
                seen: set[str] = set()
                if isinstance(body, list):
                    for entry in body:
                        raw_command = str(entry.get("Command", "")).strip() if isinstance(entry, dict) else ""
                        if not raw_command:
                            continue
                        name = raw_command.split(maxsplit=1)[0]
                        normalized = name.casefold()
                        if normalized not in seen:
                            seen.add(normalized)
                            names.append(name)
                _command_name_cache[key_id] = (time.monotonic(), names)
                return names
    except asyncio.TimeoutError as exc:
        raise ERLCAPIError("ER:LC command suggestions timed out.") from exc
    except aiohttp.ClientError as exc:
        raise ERLCAPIError("Could not connect to ER:LC for command suggestions.") from exc


class AddERLCConnectionModal(discord.ui.Modal):
    def __init__(self, guild_id: int):
        super().__init__(title="Connect an ER:LC Server")
        self.guild_id = guild_id
        self.alias = discord.ui.TextInput(
            label="Connection Name",
            placeholder="For example: Main Server",
            max_length=40,
        )
        self.server_key = discord.ui.TextInput(
            label="ER:LC Server Key",
            placeholder="Paste the key from your ER:LC private server settings",
            max_length=256,
        )
        self.add_item(self.alias)
        self.add_item(self.server_key)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if interaction.guild is None or interaction.guild.id != self.guild_id:
            await interaction.response.send_message(
                "This form can only be submitted in the server where it was opened.",
                ephemeral=True,
            )
            return

        alias = self.alias.value.strip()
        server_key = self.server_key.value.strip()
        if not alias or not server_key:
            await interaction.response.send_message(
                "Enter both a connection name and an ER:LC server key.",
                ephemeral=True,
            )
            return

        existing = list_connections(self.guild_id)
        if alias.casefold() not in existing and len(existing) >= MAX_CONNECTIONS_PER_GUILD:
            await interaction.response.send_message(
                f"A server can have up to {MAX_CONNECTIONS_PER_GUILD} named ER:LC connections.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)
        try:
            server_name = await validate_server_key(server_key)
        except ERLCAPIError as exc:
            await interaction.followup.send(str(exc), ephemeral=True)
            return

        save_connection(self.guild_id, alias, server_key, server_name)
        await interaction.followup.send(
            view=ERLCConnectionsView(
                self.guild_id,
                notice=f"Connected **{alias}** to **{server_name}**.",
            ),
            ephemeral=True,
        )


class AddERLCConnectionButton(discord.ui.Button):
    def __init__(self, guild_id: int):
        super().__init__(label="Connect ER:LC Server", style=discord.ButtonStyle.primary)
        self.guild_id = guild_id

    async def callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_modal(AddERLCConnectionModal(self.guild_id))


class RemoveERLCConnectionSelect(discord.ui.Select):
    def __init__(self, connections: dict[str, dict[str, str]]):
        self.options_by_alias = connections
        options = [
            discord.SelectOption(
                label=connection["name"],
                value=alias,
                description=connection.get("server_name", "ER:LC server")[:100],
            )
            for alias, connection in list(connections.items())[:25]
        ]
        super().__init__(
            placeholder="Select a connection to remove",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)


class RemoveERLCConnectionButton(discord.ui.Button):
    def __init__(self, guild_id: int, selector: RemoveERLCConnectionSelect):
        super().__init__(label="Remove Selected", style=discord.ButtonStyle.danger)
        self.guild_id = guild_id
        self.selector = selector

    async def callback(self, interaction: discord.Interaction) -> None:
        if not self.selector.values:
            await interaction.response.send_message(
                "Choose a connection first.",
                ephemeral=True,
            )
            return
        alias = self.selector.values[0]
        if not remove_connection(self.guild_id, alias):
            await interaction.response.send_message(
                "That connection no longer exists.",
                ephemeral=True,
            )
            return
        await interaction.response.edit_message(
            view=ERLCConnectionsView(self.guild_id, notice="ER:LC connection removed.")
        )


class ERLCConnectionsView(discord.ui.LayoutView):
    def __init__(self, guild_id: int, notice: str | None = None):
        super().__init__(timeout=900)
        connections = list_connections(guild_id)
        names = [
            f"• **{connection.get('name', alias)}** — {connection.get('server_name', 'ER:LC server')}"
            for alias, connection in connections.items()
        ]
        status = "\n".join(names) if names else "No ER:LC servers connected yet."
        if notice:
            status = f"{notice}\n\n{status}"

        items: list[discord.ui.Item] = [
            discord.ui.TextDisplay(
                "## ER:LC API Connections\n"
                "Connect multiple private servers by entering a name and server key. "
                "The key is never displayed in this panel.\n\n"
                f"{status}"
            ),
            discord.ui.Separator(),
            discord.ui.ActionRow(AddERLCConnectionButton(guild_id)),
        ]
        if connections:
            selector = RemoveERLCConnectionSelect(connections)
            items.extend(
                [
                    discord.ui.Separator(),
                    discord.ui.ActionRow(selector),
                    discord.ui.ActionRow(RemoveERLCConnectionButton(guild_id, selector)),
                ]
            )
        self.add_item(
            discord.ui.Container(
                *items,
                accent_color=discord.Color(0x242429),
            )
        )


async def _server_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> list[app_commands.Choice[str]]:
    if interaction.guild_id is None:
        return []
    connections = list_connections(interaction.guild_id)
    return [
        app_commands.Choice(name=connection["name"], value=alias)
        for alias, connection in list(connections.items())[:25]
        if current.casefold() in connection["name"].casefold()
    ]


async def _command_name_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> list[app_commands.Choice[str]]:
    guild_id = interaction.guild_id
    server_alias = getattr(interaction.namespace, "server", None)
    if guild_id is None or not server_alias:
        return []

    connection = get_connection(guild_id, server_alias)
    if connection is None:
        return []

    try:
        names = await fetch_command_names(connection["server_key"])
    except ERLCAPIError:
        return []

    filtered = [name for name in names if current.casefold() in name.casefold()]
    return [app_commands.Choice(name=name, value=name) for name in filtered[:25]]


def register_erlc_commands(bot: commands.Bot, guild_id: int) -> None:
    erlc_group = app_commands.Group(
        name="erlc",
        description="Manage linked ER:LC private servers",
    )

    @erlc_group.command(name="command", description="Run an ER:LC command in a linked server")
    @app_commands.guild_only()
    @app_commands.autocomplete(
        server=_server_autocomplete,
        command_name=_command_name_autocomplete,
    )
    @app_commands.rename(input_text="input")
    @app_commands.describe(
        server="The named ER:LC connection",
        command_name="Recent names from server command logs; custom names can be typed",
        input_text="Arguments or message text for the command (optional)",
    )
    async def run_command(
        interaction: discord.Interaction,
        server: str,
        command_name: str,
        input_text: str = "",
    ) -> None:
        if not has_setup_access(interaction.user):
            await interaction.response.send_message(
                "You need Command Level 2 or Administrator permission to run ER:LC commands.",
                ephemeral=True,
            )
            return
        if interaction.guild_id is None:
            await interaction.response.send_message(
                "ER:LC commands can only be run from a server.",
                ephemeral=True,
            )
            return

        command_parts = [command_name.strip(), input_text.strip()]
        command_text = " ".join(part for part in command_parts if part)
        if not command_name.strip() or len(command_text) > 300:
            await interaction.response.send_message(
            "Enter a command name and keep the full ER:LC command under 300 characters.",
                ephemeral=True,
            )
            return

        connection = get_connection(interaction.guild_id, server)
        if connection is None:
            await interaction.response.send_message(
                "That ER:LC connection was not found. Reopen `/setup` and connect it again.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)
        try:
            result = await run_erlc_command(connection["server_key"], command_text)
        except ERLCAPIError as exc:
            await interaction.followup.send(str(exc), ephemeral=True)
            return

        await interaction.followup.send(
            f"ER:LC accepted the command for **{connection['name']}**: `{command_text}`\n{result}",
            ephemeral=True,
            allowed_mentions=discord.AllowedMentions.none(),
        )

    bot.tree.add_command(erlc_group, guild=discord.Object(id=guild_id))
