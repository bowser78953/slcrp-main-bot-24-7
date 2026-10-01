from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import discord
from discord import app_commands
from discord.ext import commands

from shift_types import load_command_levels, load_shift_log_channels, load_shift_types


DATA_DIR = Path(os.getenv("VORTEX_DATA_DIR", str(Path(__file__).resolve().parent))).expanduser()
SHIFT_SESSIONS_PATH = DATA_DIR / "shift_sessions.json"
SHIFT_TOTALS_PATH = DATA_DIR / "shift_totals.json"


def load_shift_sessions() -> dict[str, dict[str, Any]]:
    if not SHIFT_SESSIONS_PATH.exists():
        return {}

    with SHIFT_SESSIONS_PATH.open("r", encoding="utf-8") as data_file:
        data: Any = json.load(data_file)
    if not isinstance(data, dict):
        raise ValueError("shift_sessions.json must contain an object keyed by guild and user.")
    return data


def save_shift_sessions(data: dict[str, dict[str, Any]]) -> None:
    with SHIFT_SESSIONS_PATH.open("w", encoding="utf-8") as data_file:
        json.dump(data, data_file, indent=2)
        data_file.write("\n")


def load_shift_totals() -> dict[str, dict[str, int]]:
    if not SHIFT_TOTALS_PATH.exists():
        return {}

    with SHIFT_TOTALS_PATH.open("r", encoding="utf-8") as data_file:
        data: Any = json.load(data_file)
    if not isinstance(data, dict):
        raise ValueError("shift_totals.json must contain an object keyed by server and user.")
    return data


def save_shift_totals(data: dict[str, dict[str, int]]) -> None:
    with SHIFT_TOTALS_PATH.open("w", encoding="utf-8") as data_file:
        json.dump(data, data_file, indent=2)
        data_file.write("\n")


def record_completed_shift(guild_id: int, user_id: int, seconds: int) -> int:
    totals = load_shift_totals()
    guild_totals = totals.setdefault(str(guild_id), {})
    user_key = str(user_id)
    guild_totals[user_key] = int(guild_totals.get(user_key, 0)) + max(0, int(seconds))
    save_shift_totals(totals)
    return guild_totals[user_key]


def has_shift_manage_access(member: discord.Member) -> bool:
    if getattr(member.guild_permissions, "administrator", False):
        return True

    guild = getattr(member, "guild", None)
    if guild is None:
        return False

    configured = load_command_levels().get(str(guild.id), {})
    allowed_role_ids: set[int] = set()
    for key in ("level_1_role_id", "level_2_role_id"):
        try:
            role_id = int(configured.get(key, ""))
        except (TypeError, ValueError):
            continue
        allowed_role_ids.add(role_id)

    return any(role.id in allowed_role_ids for role in member.roles)


def _session_key(guild_id: int, user_id: int) -> str:
    return f"{guild_id}:{user_id}"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _discord_time(value: str, style: str) -> str:
    timestamp = int(_parse_time(value).timestamp())
    return f"<t:{timestamp}:{style}>"


def _format_duration(seconds: int) -> str:
    hours, remainder = divmod(max(0, seconds), 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours}h {minutes}m {seconds}s"
    if minutes:
        return f"{minutes}m {seconds}s"
    return f"{seconds}s"


def _active_seconds(session: dict[str, Any], now: datetime) -> int:
    started_at = _parse_time(session["started_at"])
    break_seconds = int(session.get("break_seconds", 0))
    break_started_at = session.get("break_started_at")
    if break_started_at:
        break_seconds += int((now - _parse_time(break_started_at)).total_seconds())
    elapsed = int((now - started_at).total_seconds())
    return max(0, elapsed - break_seconds)


def _new_session(shift_type: str) -> dict[str, Any]:
    return {
        "shift_type": shift_type,
        "started_at": _now().isoformat(),
        "break_started_at": None,
        "break_count": 0,
        "break_seconds": 0,
    }


def get_shift_log_channel(guild: discord.Guild) -> discord.TextChannel | discord.Thread | None:
    channel_id = load_shift_log_channels().get(str(guild.id), {}).get("channel_id")
    try:
        parsed_channel_id = int(channel_id or "")
    except (TypeError, ValueError):
        return None

    channel = guild.get_channel(parsed_channel_id)
    if isinstance(channel, (discord.TextChannel, discord.Thread)):
        return channel
    return None


class ShiftLogEntryView(discord.ui.LayoutView):
    def __init__(self, title: str, details: str):
        super().__init__(timeout=300)
        self.add_item(
            discord.ui.Container(
                discord.ui.TextDisplay(f"## {title}\n{details}"),
                accent_color=discord.Color(0x242429),
            )
        )


async def send_shift_log(
    guild: discord.Guild,
    member: discord.Member,
    title: str,
    details: str,
) -> bool:
    channel = get_shift_log_channel(guild)
    if channel is None:
        return False

    try:
        await channel.send(
            view=ShiftLogEntryView(
                title,
                f"**Member:** {member.mention}\n{details}",
            ),
            allowed_mentions=discord.AllowedMentions.none(),
        )
    except discord.HTTPException:
        return False
    return True


async def warn_log_not_sent(interaction: discord.Interaction) -> None:
    await interaction.followup.send(
        "Your shift was updated, but the shift log could not be posted. Check the configured channel and Vortex's send permissions.",
        ephemeral=True,
    )


class CommandLevelRequiredView(discord.ui.LayoutView):
    def __init__(self):
        super().__init__(timeout=60)
        self.add_item(
            discord.ui.Container(
                discord.ui.TextDisplay(
                    "## Command Level 1 Needed\n"
                    "You need the configured Command Level 1 role, Command Level 2 role, "
                    "or Administrator permission to manage shifts."
                ),
                accent_color=discord.Color(0x242429),
            )
        )


class ShiftTypeSelect(discord.ui.Select):
    def __init__(self, guild_id: int, user_id: int):
        self.guild_id = guild_id
        self.user_id = user_id
        shift_types = load_shift_types().get(str(guild_id), [])
        options = [
            discord.SelectOption(
                label=shift_type["name"],
                value=shift_type["name"],
                description=f"Required shift time: {shift_type.get('required_shift_time', 'Not set')}"[:100],
            )
            for shift_type in shift_types[:25]
        ]
        super().__init__(
            placeholder="Choose a shift type",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        if interaction.guild is None or interaction.guild.id != self.guild_id:
            await interaction.response.send_message(
                "This shift picker can only be used in its original server.",
                ephemeral=True,
            )
            return
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "Only the member who opened /shift manage can use this shift picker.",
                ephemeral=True,
            )
            return

        sessions = load_shift_sessions()
        key = _session_key(self.guild_id, self.user_id)
        session = sessions.get(key)
        started_new_shift = session is None
        if session is None:
            session = _new_session(self.values[0])
            sessions[key] = session
            save_shift_sessions(sessions)

        await interaction.response.edit_message(
            view=ShiftSessionView(self.guild_id, self.user_id, session)
        )
        if started_new_shift and interaction.guild is not None:
            logged = await send_shift_log(
                interaction.guild,
                interaction.user,
                "Shift Started",
                f"**Shift Type:** {session['shift_type']}\n"
                f"**Started at:** {_discord_time(session['started_at'], 'T')} "
                f"({_discord_time(session['started_at'], 'R')})",
            )
            if not logged:
                await warn_log_not_sent(interaction)


class ShiftTypePickerView(discord.ui.LayoutView):
    def __init__(self, guild_id: int, user_id: int):
        super().__init__(timeout=86400)
        shift_types = load_shift_types().get(str(guild_id), [])
        items: list[discord.ui.Item] = [
            discord.ui.TextDisplay(
                "## Shift Manage\n*Please click a shift type to start your shift!*"
            ),
            discord.ui.Separator(),
        ]
        if shift_types:
            items.append(discord.ui.ActionRow(ShiftTypeSelect(guild_id, user_id)))
        else:
            items.append(
                discord.ui.TextDisplay("No shift types are configured. Ask an administrator to run `/setup`.")
            )
        self.add_item(
            discord.ui.Container(
                *items,
                accent_color=discord.Color(0x242429),
            )
        )


class ShiftActionButton(discord.ui.Button):
    def __init__(self, guild_id: int, user_id: int, action: str):
        labels = {
            "start_break": "Start Break",
            "end_break": "End Break",
            "end_shift": "End Shift",
        }
        style = (
            discord.ButtonStyle.danger
            if action == "end_shift"
            else discord.ButtonStyle.primary
        )
        super().__init__(label=labels[action], style=style)
        self.guild_id = guild_id
        self.user_id = user_id
        self.action = action

    async def callback(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "Only the member who started this shift can use these controls.",
                ephemeral=True,
            )
            return

        sessions = load_shift_sessions()
        key = _session_key(self.guild_id, self.user_id)
        session = sessions.get(key)
        if session is None:
            await interaction.response.send_message(
                "This shift is no longer active. Run `/shift manage` to start another.",
                ephemeral=True,
            )
            return

        now = _now()
        log_title = ""
        log_details = ""
        if self.action == "start_break":
            if session.get("break_started_at"):
                await interaction.response.send_message(
                    "Your break has already started.",
                    ephemeral=True,
                )
                return
            session["break_started_at"] = now.isoformat()
            session["break_count"] = int(session.get("break_count", 0)) + 1
            sessions[key] = session
            save_shift_sessions(sessions)
            view: discord.ui.LayoutView = ShiftSessionView(
                self.guild_id,
                self.user_id,
                session,
            )
            log_title = "Break Started"
            log_details = (
                f"**Shift Type:** {session['shift_type']}\n"
                f"**Break Started at:** {_discord_time(session['break_started_at'], 'T')}"
            )
        elif self.action == "end_break":
            break_started_at = session.get("break_started_at")
            if not break_started_at:
                await interaction.response.send_message(
                    "There is no active break to end.",
                    ephemeral=True,
                )
                return
            session["break_seconds"] = int(session.get("break_seconds", 0)) + int(
                (now - _parse_time(break_started_at)).total_seconds()
            )
            session["break_started_at"] = None
            sessions[key] = session
            save_shift_sessions(sessions)
            view = ShiftSessionView(self.guild_id, self.user_id, session)
            log_title = "Shift Re-Started"
            log_details = (
                f"**Shift Type:** {session['shift_type']}\n"
                f"**Amount of Breaks:** {session['break_count']}\n"
                f"**Shift started:** {_discord_time(session['started_at'], 'T')}"
            )
        else:
            shift_seconds = _active_seconds(session, now)
            record_completed_shift(self.guild_id, self.user_id, shift_seconds)
            sessions.pop(key, None)
            save_shift_sessions(sessions)
            view = ShiftEndedView(
                shift_type=session["shift_type"],
                break_count=int(session.get("break_count", 0)),
                shift_length=_format_duration(shift_seconds),
            )
            log_title = "Shift Ended"
            log_details = (
                f"**Shift Type:** {session['shift_type']}\n"
                f"**Amount of Breaks:** {session.get('break_count', 0)}\n"
                f"**Shift Length:** {_format_duration(shift_seconds)}"
            )

        await interaction.response.edit_message(view=view)
        if interaction.guild is not None:
            logged = await send_shift_log(
                interaction.guild,
                interaction.user,
                log_title,
                log_details,
            )
            if not logged:
                await warn_log_not_sent(interaction)


class ShiftSessionView(discord.ui.LayoutView):
    def __init__(self, guild_id: int, user_id: int, session: dict[str, Any]):
        super().__init__(timeout=86400)
        on_break = bool(session.get("break_started_at"))
        if on_break:
            title = "## Break Started"
            details = (
                f"*Break Started at:* {_discord_time(session['break_started_at'], 'T')} "
                f"({_discord_time(session['break_started_at'], 'R')})\n"
                f"*Shift Type:* {session['shift_type']}"
            )
            actions = ("end_break", "end_shift")
        elif int(session.get("break_count", 0)):
            title = "## Shift Re-Started"
            details = (
                f"*Shift Type:* {session['shift_type']}\n"
                f"*Amount of Breaks:* {session['break_count']}\n"
                f"*Shift started:* {_discord_time(session['started_at'], 'T')}"
            )
            actions = ("end_shift", "start_break")
        else:
            title = "## Shift Started!"
            details = (
                f"*Shift Type:* {session['shift_type']}\n"
                f"*Started at:* {_discord_time(session['started_at'], 'T')} "
                f"({_discord_time(session['started_at'], 'R')})"
            )
            actions = ("end_shift", "start_break")

        self.add_item(
            discord.ui.Container(
                discord.ui.TextDisplay(f"{title}\n{details}"),
                discord.ui.Separator(),
                discord.ui.ActionRow(
                    *(ShiftActionButton(guild_id, user_id, action) for action in actions)
                ),
                accent_color=discord.Color(0x242429),
            )
        )


class ShiftEndedView(discord.ui.LayoutView):
    def __init__(self, shift_type: str, break_count: int, shift_length: str):
        super().__init__(timeout=300)
        self.add_item(
            discord.ui.Container(
                discord.ui.TextDisplay(
                    "## Shift Ended\n"
                    f"*Shift Type:* {shift_type}\n"
                    f"*Amount of Breaks:* {break_count}\n"
                    f"*Shift Length:* {shift_length}"
                ),
                accent_color=discord.Color(0x242429),
            )
        )


class SnapshotRefreshButton(discord.ui.Button):
    def __init__(self, guild_id: int, page: int, snapshot: str):
        super().__init__(label="Refresh", style=discord.ButtonStyle.secondary)
        self.guild_id = guild_id
        self.page = page
        self.snapshot = snapshot

    async def callback(self, interaction: discord.Interaction) -> None:
        view_type = ActiveShiftsView if self.snapshot == "active" else ShiftLeaderboardView
        await interaction.response.edit_message(
            view=view_type(self.guild_id, self.page),
            allowed_mentions=discord.AllowedMentions.none(),
        )


class ActiveShiftsPageButton(discord.ui.Button):
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
            view=ActiveShiftsView(self.guild_id, self.page),
            allowed_mentions=discord.AllowedMentions.none(),
        )


class ActiveShiftsView(discord.ui.LayoutView):
    PAGE_SIZE = 12

    def __init__(self, guild_id: int, page: int = 0):
        super().__init__(timeout=900)
        now = _now()
        entries: list[tuple[datetime, bool, int, dict[str, Any]]] = []
        guild_prefix = f"{guild_id}:"
        for key, session in load_shift_sessions().items():
            if not key.startswith(guild_prefix) or not isinstance(session, dict):
                continue
            try:
                user_id = int(key[len(guild_prefix):])
                started_at = _parse_time(session["started_at"])
                _active_seconds(session, now)
            except (KeyError, TypeError, ValueError):
                continue
            entries.append((started_at, bool(session.get("break_started_at")), user_id, session))

        entries.sort(key=lambda item: item[0])
        page_count = max(1, (len(entries) + self.PAGE_SIZE - 1) // self.PAGE_SIZE)
        page = max(0, min(page, page_count - 1))
        visible_entries = entries[page * self.PAGE_SIZE:(page + 1) * self.PAGE_SIZE]

        details: list[str] = []
        for on_break, heading in ((False, "***On Shift***"), (True, "***On Break***")):
            lines = [
                f"> <@{user_id}> - `{session.get('shift_type', 'Unknown')}` - "
                f"`{_format_duration(_active_seconds(session, now))}`"
                for _, is_on_break, user_id, session in visible_entries
                if is_on_break == on_break
            ]
            if lines:
                details.append(f"{heading}\n" + "\n".join(lines))

        if not details:
            details.append("No active shifts right now.")

        container_items: list[discord.ui.Item] = [
            discord.ui.TextDisplay(
                "## <:ActiveShifts:1555074646771109939> Active Shifts"
            ),
            discord.ui.Separator(),
            discord.ui.TextDisplay("\n\n".join(details)),
        ]
        snapshot_controls: list[discord.ui.Item] = []
        if page_count > 1:
            snapshot_controls.extend(
                [
                    ActiveShiftsPageButton(
                        guild_id,
                        page - 1,
                        "Previous",
                        disabled=page == 0,
                    ),
                    ActiveShiftsPageButton(
                        guild_id,
                        page + 1,
                        "Next",
                        disabled=page == page_count - 1,
                    ),
                ]
            )
        snapshot_controls.append(SnapshotRefreshButton(guild_id, page, "active"))
        container_items.extend(
            [
                discord.ui.Separator(),
                discord.ui.TextDisplay(f"Page {page + 1} of {page_count}"),
                discord.ui.ActionRow(*snapshot_controls),
            ]
        )

        self.add_item(
            discord.ui.Container(
                *container_items,
                accent_color=discord.Color(0x242429),
            )
        )


class ShiftLeaderboardPageButton(discord.ui.Button):
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
            view=ShiftLeaderboardView(self.guild_id, self.page),
            allowed_mentions=discord.AllowedMentions.none(),
        )


class ShiftLeaderboardView(discord.ui.LayoutView):
    PAGE_SIZE = 10
    TOP_THREE_EMOJI = "<:Untitled_design__17_removebgprev:1555077081581224071>"

    def __init__(self, guild_id: int, page: int = 0):
        super().__init__(timeout=900)
        totals: dict[int, int] = {}
        for user_id, seconds in load_shift_totals().get(str(guild_id), {}).items():
            try:
                parsed_user_id = int(user_id)
                totals[parsed_user_id] = max(0, int(seconds))
            except (TypeError, ValueError):
                continue

        now = _now()
        guild_prefix = f"{guild_id}:"
        for key, session in load_shift_sessions().items():
            if not key.startswith(guild_prefix) or not isinstance(session, dict):
                continue
            try:
                user_id = int(key[len(guild_prefix):])
                totals[user_id] = totals.get(user_id, 0) + _active_seconds(session, now)
            except (KeyError, TypeError, ValueError):
                continue

        entries = sorted(
            ((user_id, seconds) for user_id, seconds in totals.items() if seconds > 0),
            key=lambda entry: (-entry[1], entry[0]),
        )
        page_count = max(1, (len(entries) + self.PAGE_SIZE - 1) // self.PAGE_SIZE)
        page = max(0, min(page, page_count - 1))
        page_start = page * self.PAGE_SIZE
        visible_entries = entries[page_start:page_start + self.PAGE_SIZE]

        lines: list[str] = []
        for offset, (user_id, seconds) in enumerate(visible_entries):
            rank = page_start + offset
            medal = f"{self.TOP_THREE_EMOJI} " if rank < 3 else ""
            lines.append(
                f"> {medal}<@{user_id}> - `{_format_duration(seconds)}`"
            )
        leaderboard_text = "\n".join(lines) if lines else "No completed shift time yet."

        container_items: list[discord.ui.Item] = [
            discord.ui.TextDisplay(
                "## <:ShiftLeaderboard:1555074991278657606> Shift Leaderboard"
            ),
            discord.ui.Separator(),
            discord.ui.TextDisplay(f"**Shift Leaderboard**\n{leaderboard_text}"),
        ]
        if page_count > 1:
            container_items.extend(
                [
                    discord.ui.Separator(),
                    discord.ui.ActionRow(
                        ShiftLeaderboardPageButton(
                            guild_id,
                            page - 1,
                            "Previous",
                            disabled=page == 0,
                        ),
                        ShiftLeaderboardPageButton(
                            guild_id,
                            page + 1,
                            "Next",
                            disabled=page == page_count - 1,
                        ),
                    ),
                ]
            )

        self.add_item(
            discord.ui.Container(
                *container_items,
                accent_color=discord.Color(0x242429),
            )
        )


def register_shift_commands(bot: commands.Bot) -> None:
    shift_group = app_commands.Group(
        name="shift",
        description="Staff shift commands",
    )

    @shift_group.command(name="manage", description="Start, break, or end your shift")
    @app_commands.guild_only()
    async def manage(interaction: discord.Interaction) -> None:
        if not has_shift_manage_access(interaction.user):
            await interaction.response.send_message(
                view=CommandLevelRequiredView(),
                ephemeral=True,
            )
            return

        guild_id = interaction.guild_id
        guild = interaction.guild
        if guild_id is None or guild is None:
            await interaction.response.send_message(
                "Shift management can only be used in a server.",
                ephemeral=True,
            )
            return

        if get_shift_log_channel(guild) is None:
            await interaction.response.send_message(
                "Set a valid Shift Log Channel from the Shift Types page in `/setup` before starting a shift.",
                ephemeral=True,
            )
            return

        key = _session_key(guild_id, interaction.user.id)
        session = load_shift_sessions().get(key)
        if session:
            view: discord.ui.LayoutView = ShiftSessionView(
                guild_id,
                interaction.user.id,
                session,
            )
        else:
            view = ShiftTypePickerView(guild_id, interaction.user.id)
        await interaction.response.send_message(view=view)

    @shift_group.command(name="leaderboard", description="Show total shift time rankings")
    @app_commands.guild_only()
    async def leaderboard(interaction: discord.Interaction) -> None:
        if not has_shift_manage_access(interaction.user):
            await interaction.response.send_message(
                view=CommandLevelRequiredView(),
                ephemeral=True,
            )
            return

        if interaction.guild_id is None:
            await interaction.response.send_message(
                "The shift leaderboard can only be viewed in a server.",
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            view=ShiftLeaderboardView(interaction.guild_id),
            allowed_mentions=discord.AllowedMentions.none(),
        )

    bot.tree.add_command(shift_group)


def register_active_shift_commands(bot: commands.Bot) -> None:
    active_group = app_commands.Group(
        name="active",
        description="Staff activity commands",
    )

    @active_group.command(name="shifts", description="Show current server shifts")
    @app_commands.guild_only()
    async def shifts(interaction: discord.Interaction) -> None:
        if interaction.guild_id is None:
            await interaction.response.send_message(
                "Active shifts can only be viewed in a server.",
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            view=ActiveShiftsView(interaction.guild_id),
            allowed_mentions=discord.AllowedMentions.none(),
        )

    bot.tree.add_command(active_group)
