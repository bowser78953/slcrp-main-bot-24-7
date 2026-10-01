from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import discord
from discord import app_commands
from discord.ext import commands


DATA_DIR = Path(os.getenv("VORTEX_DATA_DIR", str(Path(__file__).resolve().parent))).expanduser()
SHIFT_TYPES_PATH = DATA_DIR / "shift_types.json"
UNIVERSAL_NICKNAMES_PATH = DATA_DIR / "universal_nicknames.json"
COMMAND_LEVELS_PATH = DATA_DIR / "command_levels.json"
LOA_SETTINGS_PATH = DATA_DIR / "loa_settings.json"
SHIFT_LOG_CHANNELS_PATH = DATA_DIR / "shift_log_channels.json"
MAX_SHIFT_TYPES = 25
SHIFT_TYPES_PER_PAGE = 6


def load_shift_types() -> dict[str, list[dict[str, str]]]:
    if not SHIFT_TYPES_PATH.exists():
        return {}

    with SHIFT_TYPES_PATH.open("r", encoding="utf-8") as data_file:
        data: Any = json.load(data_file)

    if not isinstance(data, dict):
        raise ValueError("shift_types.json must contain an object keyed by server ID.")
    return data


def save_shift_types(data: dict[str, list[dict[str, str]]]) -> None:
    with SHIFT_TYPES_PATH.open("w", encoding="utf-8") as data_file:
        json.dump(data, data_file, indent=2)
        data_file.write("\n")


def load_universal_nicknames() -> dict[str, dict[str, str]]:
    if not UNIVERSAL_NICKNAMES_PATH.exists():
        return {}

    with UNIVERSAL_NICKNAMES_PATH.open("r", encoding="utf-8") as data_file:
        data: Any = json.load(data_file)

    if not isinstance(data, dict):
        raise ValueError("universal_nicknames.json must contain an object keyed by server ID.")
    return data


def save_universal_nicknames(data: dict[str, dict[str, str]]) -> None:
    with UNIVERSAL_NICKNAMES_PATH.open("w", encoding="utf-8") as data_file:
        json.dump(data, data_file, indent=2)
        data_file.write("\n")


def load_command_levels() -> dict[str, dict[str, str]]:
    if not COMMAND_LEVELS_PATH.exists():
        return {}

    with COMMAND_LEVELS_PATH.open("r", encoding="utf-8") as data_file:
        data: Any = json.load(data_file)

    if not isinstance(data, dict):
        raise ValueError("command_levels.json must contain an object keyed by server ID.")
    return data


def save_command_levels(data: dict[str, dict[str, str]]) -> None:
    with COMMAND_LEVELS_PATH.open("w", encoding="utf-8") as data_file:
        json.dump(data, data_file, indent=2)
        data_file.write("\n")


def load_loa_settings() -> dict[str, dict[str, Any]]:
    if not LOA_SETTINGS_PATH.exists():
        return {}

    with LOA_SETTINGS_PATH.open("r", encoding="utf-8") as data_file:
        data: Any = json.load(data_file)

    if not isinstance(data, dict):
        raise ValueError("loa_settings.json must contain an object keyed by server ID.")
    return data


def save_loa_settings(data: dict[str, dict[str, Any]]) -> None:
    with LOA_SETTINGS_PATH.open("w", encoding="utf-8") as data_file:
        json.dump(data, data_file, indent=2)
        data_file.write("\n")


def load_shift_log_channels() -> dict[str, dict[str, str]]:
    if not SHIFT_LOG_CHANNELS_PATH.exists():
        return {}

    with SHIFT_LOG_CHANNELS_PATH.open("r", encoding="utf-8") as data_file:
        data: Any = json.load(data_file)

    if not isinstance(data, dict):
        raise ValueError("shift_log_channels.json must contain an object keyed by server ID.")
    return data


def save_shift_log_channels(data: dict[str, dict[str, str]]) -> None:
    with SHIFT_LOG_CHANNELS_PATH.open("w", encoding="utf-8") as data_file:
        json.dump(data, data_file, indent=2)
        data_file.write("\n")


def has_setup_access(member: discord.Member) -> bool:
    if getattr(member.guild_permissions, "administrator", False):
        return True

    guild = getattr(member, "guild", None)
    if guild is None:
        return False

    level_two_role_id = load_command_levels().get(str(guild.id), {}).get("level_2_role_id")
    if not level_two_role_id:
        return False

    try:
        configured_role_id = int(level_two_role_id)
    except (TypeError, ValueError):
        return False

    return any(role.id == configured_role_id for role in member.roles)


class UniversalNicknamesModal(discord.ui.Modal):
    def __init__(self, guild_id: int, current: dict[str, str] | None = None):
        super().__init__(title="Universal Nicknames")
        self.guild_id = guild_id
        current = current or {}
        self.on_shift_nickname = discord.ui.TextInput(
            default=current.get("on_shift_nickname") or None,
            placeholder="For example: [ON DUTY] {user}",
            max_length=32,
        )
        self.on_break_nickname = discord.ui.TextInput(
            default=current.get("on_break_nickname") or None,
            placeholder="For example: [ON BREAK] {user}",
            max_length=32,
        )
        self.add_item(
            discord.ui.Label(
                text="On Shift Nickname",
                component=self.on_shift_nickname,
            )
        )
        self.add_item(
            discord.ui.Label(
                text="On Break Nickname",
                component=self.on_break_nickname,
            )
        )

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if interaction.guild is None or interaction.guild.id != self.guild_id:
            await interaction.response.send_message(
                "This form can only be submitted in the server where it was opened.",
                ephemeral=True,
            )
            return

        data = load_universal_nicknames()
        data[str(self.guild_id)] = {
            "on_shift_nickname": self.on_shift_nickname.value.strip(),
            "on_break_nickname": self.on_break_nickname.value.strip(),
        }
        save_universal_nicknames(data)
        await interaction.response.send_message(
            "Universal nicknames saved.",
            ephemeral=True,
        )


class CommandLevelsModal(discord.ui.Modal):
    def __init__(self, guild_id: int):
        super().__init__(title="Set Up Command Levels")
        self.guild_id = guild_id
        self.level_one_role = discord.ui.RoleSelect(
            placeholder="Select the Command Level 1 role",
            min_values=1,
            max_values=1,
            required=True,
        )
        self.level_two_role = discord.ui.RoleSelect(
            placeholder="Select the Command Level 2 role",
            min_values=1,
            max_values=1,
            required=True,
        )
        self.add_item(
            discord.ui.Label(
                text="Command Level 1",
                component=self.level_one_role,
            )
        )
        self.add_item(
            discord.ui.Label(
                text="Command Level 2",
                component=self.level_two_role,
            )
        )

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if interaction.guild is None or interaction.guild.id != self.guild_id:
            await interaction.response.send_message(
                "This form can only be submitted in the server where it was opened.",
                ephemeral=True,
            )
            return

        level_one_role = self.level_one_role.values[0]
        level_two_role = self.level_two_role.values[0]
        data = load_command_levels()
        data[str(self.guild_id)] = {
            "level_1_role": level_one_role.name,
            "level_1_role_id": str(level_one_role.id),
            "level_2_role": level_two_role.name,
            "level_2_role_id": str(level_two_role.id),
        }
        save_command_levels(data)
        await interaction.response.send_message(
            "Command level roles saved.",
            ephemeral=True,
        )


class LOARoleModal(discord.ui.Modal):
    def __init__(self, guild_id: int, setting_key: str, label: str):
        super().__init__(title=f"Set {label}")
        self.guild_id = guild_id
        self.setting_key = setting_key
        self.role = discord.ui.RoleSelect(
            placeholder=f"Select the {label}",
            min_values=1,
            max_values=1,
            required=True,
        )
        self.add_item(discord.ui.Label(text=label, component=self.role))

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if interaction.guild is None or interaction.guild.id != self.guild_id:
            await interaction.response.send_message(
                "This form can only be submitted in the server where it was opened.",
                ephemeral=True,
            )
            return

        role = self.role.values[0]
        data = load_loa_settings()
        settings = data.setdefault(str(self.guild_id), {})
        settings[self.setting_key] = {"name": role.name, "id": str(role.id)}
        settings["setup_complete"] = False
        save_loa_settings(data)
        await interaction.response.send_message(f"{self.setting_key} saved.", ephemeral=True)


class LOARequestChannelModal(discord.ui.Modal):
    def __init__(self, guild_id: int):
        super().__init__(title="Set LOA Request Channel")
        self.guild_id = guild_id
        self.channel = discord.ui.ChannelSelect(
            placeholder="Select the LOA request channel",
            channel_types=[discord.ChannelType.text, discord.ChannelType.news],
            min_values=1,
            max_values=1,
            required=True,
        )
        self.add_item(
            discord.ui.Label(
                text="LOA Request Channel",
                component=self.channel,
            )
        )

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if interaction.guild is None or interaction.guild.id != self.guild_id:
            await interaction.response.send_message(
                "This form can only be submitted in the server where it was opened.",
                ephemeral=True,
            )
            return

        channel = self.channel.values[0]
        data = load_loa_settings()
        settings = data.setdefault(str(self.guild_id), {})
        settings["request_channel"] = {"name": channel.name, "id": str(channel.id)}
        settings["setup_complete"] = False
        save_loa_settings(data)
        await interaction.response.send_message("LOA request channel saved.", ephemeral=True)


class ShiftLogChannelModal(discord.ui.Modal):
    def __init__(self, guild_id: int):
        super().__init__(title="Set Shift Log Channel")
        self.guild_id = guild_id
        self.channel = discord.ui.ChannelSelect(
            placeholder="Select the shift log channel",
            channel_types=[discord.ChannelType.text, discord.ChannelType.news],
            min_values=1,
            max_values=1,
            required=True,
        )
        self.add_item(
            discord.ui.Label(
                text="Shift Log Channel",
                component=self.channel,
            )
        )

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if interaction.guild is None or interaction.guild.id != self.guild_id:
            await interaction.response.send_message(
                "This form can only be submitted in the server where it was opened.",
                ephemeral=True,
            )
            return

        channel = self.channel.values[0]
        data = load_shift_log_channels()
        data[str(self.guild_id)] = {
            "channel_name": channel.name,
            "channel_id": str(channel.id),
        }
        save_shift_log_channels(data)
        await interaction.response.send_message("Shift log channel saved.", ephemeral=True)


class LOARoleButton(discord.ui.Button):
    def __init__(self, guild_id: int, label: str, setting_key: str):
        super().__init__(label=label, style=discord.ButtonStyle.secondary)
        self.guild_id = guild_id
        self.setting_key = setting_key

    async def callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_modal(
            LOARoleModal(self.guild_id, self.setting_key, self.label)
        )


class LOARequestChannelButton(discord.ui.Button):
    def __init__(self, guild_id: int):
        super().__init__(label="LOA Request Channel", style=discord.ButtonStyle.secondary)
        self.guild_id = guild_id

    async def callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_modal(LOARequestChannelModal(self.guild_id))


class CompleteLOASetupButton(discord.ui.Button):
    def __init__(self, guild_id: int):
        super().__init__(label="Complete LOA Setup", style=discord.ButtonStyle.primary)
        self.guild_id = guild_id

    async def callback(self, interaction: discord.Interaction) -> None:
        data = load_loa_settings()
        settings = data.get(str(self.guild_id), {})
        required = {
            "LOA Role": "loa_role",
            "LOA Ping Role": "loa_ping_role",
            "LOA Request Channel": "request_channel",
        }
        missing = [label for label, key in required.items() if not settings.get(key, {}).get("id")]
        if missing:
            await interaction.response.send_message(
                "Set these before completing setup: " + ", ".join(missing) + ".",
                ephemeral=True,
            )
            return

        settings["setup_complete"] = True
        data[str(self.guild_id)] = settings
        save_loa_settings(data)
        await interaction.response.edit_message(
            view=LOASetupView(self.guild_id, notice="LOA setup is complete.")
        )


class LOASetupView(discord.ui.LayoutView):
    def __init__(self, guild_id: int, notice: str | None = None):
        super().__init__(timeout=900)
        settings = load_loa_settings().get(str(guild_id), {})
        intro = "Choose each setting, then complete setup."
        if notice:
            intro = notice
        container = discord.ui.Container(
            discord.ui.TextDisplay(
                "## Leave of Absence Set Up\n"
                f"{intro}\n\n"
                f"LOA Role: {settings.get('loa_role', {}).get('name', 'Not set')}\n"
                f"LOA Ping Role: {settings.get('loa_ping_role', {}).get('name', 'Not set')}\n"
                f"LOA Request Channel: {settings.get('request_channel', {}).get('name', 'Not set')}"
            ),
            discord.ui.Separator(),
            discord.ui.ActionRow(LOARoleButton(guild_id, "LOA Role", "loa_role")),
            discord.ui.Separator(),
            discord.ui.ActionRow(LOARoleButton(guild_id, "LOA Ping Role", "loa_ping_role")),
            discord.ui.Separator(),
            discord.ui.ActionRow(LOARequestChannelButton(guild_id)),
            discord.ui.Separator(),
            discord.ui.ActionRow(CompleteLOASetupButton(guild_id)),
            accent_color=discord.Color(0x242429),
        )
        self.add_item(container)


class AddShiftTypeModal(discord.ui.Modal):
    def __init__(self, guild_id: int):
        super().__init__(title="Add a Shift Type")
        self.guild_id = guild_id
        self.shift_name = discord.ui.TextInput(max_length=100)
        self.required_shift_time = discord.ui.TextInput(
            placeholder="For example: 30 minutes", max_length=100
        )
        self.on_shift_role = discord.ui.RoleSelect(
            placeholder="Select the on-shift role",
            min_values=1,
            max_values=1,
            required=True,
        )
        self.on_break_role = discord.ui.RoleSelect(
            placeholder="Select the on-break role",
            min_values=1,
            max_values=1,
            required=True,
        )
        self.add_item(discord.ui.Label(text="Shift Type Name", component=self.shift_name))
        self.add_item(
            discord.ui.Label(
                text="Required Shift Time",
                component=self.required_shift_time,
            )
        )
        self.add_item(
            discord.ui.Label(
                text="On Shift Role",
                component=self.on_shift_role,
            )
        )
        self.add_item(
            discord.ui.Label(
                text="On Break Role",
                component=self.on_break_role,
            )
        )

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if interaction.guild is None or interaction.guild.id != self.guild_id:
            await interaction.response.send_message(
                "This form can only be submitted in the server where it was opened.",
                ephemeral=True,
            )
            return

        shift_name = self.shift_name.value.strip()
        data = load_shift_types()
        guild_shifts = data.setdefault(str(self.guild_id), [])

        if any(item["name"].casefold() == shift_name.casefold() for item in guild_shifts):
            await interaction.response.send_message(
                f'A shift type named "{shift_name}" already exists.',
                ephemeral=True,
            )
            return

        if len(guild_shifts) >= MAX_SHIFT_TYPES:
            await interaction.response.send_message(
                f"This server has reached the limit of {MAX_SHIFT_TYPES} shift types.",
                ephemeral=True,
            )
            return

        on_shift_role = self.on_shift_role.values[0]
        on_break_role = self.on_break_role.values[0]
        guild_shifts.append(
            {
                "name": shift_name,
                "required_shift_time": self.required_shift_time.value.strip(),
                "on_shift_role": on_shift_role.name,
                "on_shift_role_id": str(on_shift_role.id),
                "on_break_role": on_break_role.name,
                "on_break_role_id": str(on_break_role.id),
            }
        )
        save_shift_types(data)
        await interaction.response.send_message(
            view=ShiftManagementView(
                self.guild_id,
                page=(len(guild_shifts) - 1) // SHIFT_TYPES_PER_PAGE,
                notice=f'Shift type "{shift_name}" added.',
            ),
            ephemeral=True,
        )


class AddShiftTypeButton(discord.ui.Button):
    def __init__(self, guild_id: int):
        super().__init__(
            label="Add a Shift Type",
            style=discord.ButtonStyle.primary,
        )
        self.guild_id = guild_id

    async def callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_modal(AddShiftTypeModal(self.guild_id))


class RemoveShiftTypeButton(discord.ui.Button):
    def __init__(self, guild_id: int, shift_name: str, page: int):
        super().__init__(label="Remove", style=discord.ButtonStyle.danger)
        self.guild_id = guild_id
        self.shift_name = shift_name
        self.page = page

    async def callback(self, interaction: discord.Interaction) -> None:
        data = load_shift_types()
        guild_shifts = data.get(str(self.guild_id), [])
        remaining = [
            shift_type
            for shift_type in guild_shifts
            if shift_type["name"] != self.shift_name
        ]
        if len(remaining) == len(guild_shifts):
            await interaction.response.send_message(
                "That shift type no longer exists.",
                ephemeral=True,
            )
            return

        if remaining:
            data[str(self.guild_id)] = remaining
        else:
            data.pop(str(self.guild_id), None)
        save_shift_types(data)
        await interaction.response.edit_message(
            view=ShiftManagementView(
                self.guild_id,
                page=self.page,
                notice=f'Shift type "{self.shift_name}" removed.',
            )
        )


class ShiftPageButton(discord.ui.Button):
    def __init__(self, guild_id: int, page: int, label: str, disabled: bool):
        super().__init__(
            label=label,
            style=discord.ButtonStyle.secondary,
            disabled=disabled,
        )
        self.guild_id = guild_id
        self.page = page

    async def callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.edit_message(
            view=ShiftManagementView(self.guild_id, page=self.page)
        )


class ShiftManagementView(discord.ui.LayoutView):
    def __init__(self, guild_id: int, page: int = 0, notice: str | None = None):
        super().__init__(timeout=900)
        shift_types = load_shift_types().get(str(guild_id), [])
        page_count = max(1, (len(shift_types) + SHIFT_TYPES_PER_PAGE - 1) // SHIFT_TYPES_PER_PAGE)
        page = max(0, min(page, page_count - 1))
        page_start = page * SHIFT_TYPES_PER_PAGE
        visible_shift_types = shift_types[page_start:page_start + SHIFT_TYPES_PER_PAGE]

        intro = "Add a shift type or remove one from the list."
        if notice:
            intro = f"{notice}\n{intro}"
        container_items: list[discord.ui.Item] = [
            discord.ui.TextDisplay(f"## Shift Types\n{intro}"),
            discord.ui.Separator(),
            discord.ui.ActionRow(AddShiftTypeButton(guild_id)),
        ]

        if visible_shift_types:
            for shift_type in visible_shift_types:
                details = (
                    f"**{shift_type['name']}**\n"
                    f"On Shift Role: {shift_type.get('on_shift_role', 'Not set')}\n"
                    f"On Break Role: {shift_type.get('on_break_role', 'Not set')}\n"
                    f"Required Shift Time: {shift_type.get('required_shift_time', 'Not set')}"
                )
                container_items.append(
                    discord.ui.Section(
                        discord.ui.TextDisplay(details),
                        accessory=RemoveShiftTypeButton(
                            guild_id,
                            shift_type["name"],
                            page,
                        ),
                    )
                )
        else:
            container_items.append(discord.ui.TextDisplay("No shift types have been added yet."))

        if page_count > 1:
            page_buttons: list[discord.ui.Item] = []
            if page > 0:
                page_buttons.append(ShiftPageButton(guild_id, page - 1, "Previous"))
            if page < page_count - 1:
                page_buttons.append(ShiftPageButton(guild_id, page + 1, "Next"))
            container_items.append(discord.ui.ActionRow(*page_buttons))

        self.add_item(
            discord.ui.Container(
                *container_items,
                accent_color=discord.Color(0x242429),
            )
        )


class ShiftActionSelect(discord.ui.Select):
    def __init__(self, page: int):
        if page == 0:
            options = [
                discord.SelectOption(
                    label="Add/Remove a Shift Type",
                    value="manage",
                    description="Open the shift type controls",
                ),
                discord.SelectOption(
                    label="Set Shift Log Channel",
                    value="shift_log_channel",
                    description="Choose where shift events are logged",
                ),
            ]
        elif page == 1:
            options = [
                discord.SelectOption(
                    label="Set Universal Nicknames",
                    value="universal_nicknames",
                    description="Set the server-wide on-shift and on-break nicknames",
                )
            ]
        elif page == 2:
            options = [
                discord.SelectOption(
                    label="Set Up Command Levels",
                    value="command_levels",
                    description="Choose the roles for command levels 1 and 2",
                )
            ]
        elif page == 3:
            options = [
                discord.SelectOption(
                    label="Setup LOA",
                    value="setup_loa",
                    description="Configure the LOA role, ping role, and request channel",
                )
            ]
        else:
            options = [
                discord.SelectOption(
                    label="Manage ER:LC Servers",
                    value="erlc_connections",
                    description="Connect private servers and manage API keys",
                )
            ]
        placeholders = {
            0: "Choose a Shift Types action",
            1: "Choose a Universal Nickname action",
            2: "Choose a Command Levels action",
            3: "Choose an LOA action",
            4: "Choose an ER:LC action",
        }
        super().__init__(placeholder=placeholders.get(page, "Choose an action"), options=options)
        self.page = page

    async def callback(self, interaction: discord.Interaction) -> None:
        if interaction.guild is None:
            await interaction.response.send_message(
                "This setup panel only works inside a server.",
                ephemeral=True,
            )
            return

        if not has_setup_access(interaction.user):
            await interaction.response.send_message(
                "You need Command Level 2 or Administrator permission to configure setup.",
                ephemeral=True,
            )
            return

        if self.values[0] == "universal_nicknames":
            saved = load_universal_nicknames().get(str(interaction.guild.id), {})
            await interaction.response.send_modal(
                UniversalNicknamesModal(interaction.guild.id, saved)
            )
            return

        if self.values[0] == "shift_log_channel":
            await interaction.response.send_modal(
                ShiftLogChannelModal(interaction.guild.id)
            )
            return

        if self.values[0] == "command_levels":
            await interaction.response.send_modal(
                CommandLevelsModal(interaction.guild.id)
            )
            return

        if self.values[0] == "setup_loa":
            await interaction.response.send_message(
                view=LOASetupView(interaction.guild.id),
                ephemeral=True,
            )
            return

        if self.values[0] == "erlc_connections":
            from erlc_integration import ERLCConnectionsView

            await interaction.response.send_message(
                view=ERLCConnectionsView(interaction.guild.id),
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            view=ShiftManagementView(interaction.guild.id),
            ephemeral=True,
        )


class ShiftSetupPageButton(discord.ui.Button):
    def __init__(self, guild_id: int, page: int, label: str, disabled: bool):
        super().__init__(label=label, style=discord.ButtonStyle.secondary, disabled=disabled)
        self.guild_id = guild_id
        self.page = page

    async def callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.edit_message(
            view=ShiftSetupPanel(self.guild_id, self.page)
        )


class ShiftSetupPanel(discord.ui.LayoutView):
    def __init__(self, guild_id: int, page: int = 0):
        super().__init__(timeout=900)
        page = max(0, min(page, 4))
        if page == 0:
            shift_log_channel = load_shift_log_channels().get(str(guild_id), {})
            page_text = (
                "## Shift Types\n"
                "Shift types organize staff duty into categories such as moderation "
                "or administration. Assign a required duration and nickname presets "
                "to track how staff time is spent.\n"
                f"Shift Log Channel: {shift_log_channel.get('channel_name') or 'Not set'}"
            )
        elif page == 1:
            nicknames = load_universal_nicknames().get(str(guild_id), {})
            page_text = "## Universal Nicknames\n"
            page_text += (
                f"On Shift Nickname: {nicknames.get('on_shift_nickname') or 'Not set'}\n"
                f"On Break Nickname: {nicknames.get('on_break_nickname') or 'Not set'}\n"
                "Use the action menu to set or update these server-wide nicknames."
            )
        elif page == 2:
            command_levels = load_command_levels().get(str(guild_id), {})
            page_text = (
                "# Command Levels\n"
                "Command levels allow users to use Vortex commands.\n"
                "Command Level 1 - Shift Manage, Shift Leaderboard, LOA request and more\n"
                "Command Level 2 - All commands\n\n"
                f"Command Level 1 Role: {command_levels.get('level_1_role') or 'Not set'}\n"
                f"Command Level 2 Role: {command_levels.get('level_2_role') or 'Not set'}"
            )
        elif page == 3:
            page_text = (
                "# Leave of Absence\n"
                "LOA, or Leave of Absence, is a temporary period when a staff member "
                "is allowed to take time away from their staff duties without being "
                "expected to complete their normal shift requirements. An LOA can be "
                "requested for personal reasons, vacations, school, work, or other "
                "situations where the staff member needs time away. While on LOA, the "
                "staff member remains part of the staff team but is temporarily excused "
                "from their normal activity requirements until their approved LOA ends."
            )
        else:
            from erlc_integration import list_connections

            connections = list_connections(guild_id)
            connected_names = ", ".join(
                connection.get("name", alias)
                for alias, connection in connections.items()
            ) or "None linked"
            page_text = (
                "## ER:LC API\n"
                "Link one or more ER:LC private servers and run in-game commands. "
                "Command Name suggestions come from recent server command logs; "
                "custom command names can also be typed.\n"
                f"Connected servers: {connected_names}\n"
                "The API key is verified on connection and kept out of the public panel."
            )
        container = discord.ui.Container(
            discord.ui.TextDisplay(page_text),
            discord.ui.Separator(),
            discord.ui.ActionRow(ShiftActionSelect(page)),
            discord.ui.Separator(),
            discord.ui.TextDisplay(f"Page {page + 1} of 5"),
            discord.ui.ActionRow(
                ShiftSetupPageButton(guild_id, page - 1, "←", disabled=page == 0),
                ShiftSetupPageButton(guild_id, page + 1, "→", disabled=page == 4),
            ),
            accent_color=discord.Color(0x242429),
        )
        self.add_item(container)


def register_shift_setup(bot: commands.Bot) -> None:
    @app_commands.command(
        name="setup",
        description="Post the Shift Types setup panel",
    )
    @app_commands.guild_only()
    async def setup(interaction: discord.Interaction) -> None:
        if not has_setup_access(interaction.user):
            await interaction.response.send_message(
                "You need the configured Command Level 2 role or Administrator permission to use /setup.",
                ephemeral=True,
            )
            return

        await interaction.response.defer()
        if interaction.guild is not None:
            await interaction.followup.send(view=ShiftSetupPanel(interaction.guild.id))

    bot.tree.add_command(setup)
