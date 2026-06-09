import os
import json
import re
from collections import defaultdict, deque
from datetime import timedelta

import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("YCF_BOT_TOKEN", "")
PREFIX = os.getenv("YCF_BOT_PREFIX", "!")
STATUS_TEXT = os.getenv("YCF_BOT_STATUS", "Running YCF Bot")

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix=PREFIX, intents=intents, help_command=None)

SPAM_MESSAGE_COUNT = 4
SPAM_WINDOW_SECONDS = 4
SPAM_NOTIFICATION_CHANNEL_ID = 1510463018717413386
CM_NOTIFICATION_CHANNEL_ID = 1510463018717413386
INSTA_BAN_WORDS = {"cunt", "nigger", "nigga", "whore", "pussy", "cock"}
BOT_MANAGER_PANEL_CHANNEL_ID = 1514012975499837460
BOT_MANAGER_TICKET_CATEGORY_ID = 1514013394775052429
BOT_MANAGER_PING_USER_ID = 1332458947067773072
EVERYONE_PING_INVITE_URL = "https://discord.gg/D7RZWT6BSw"
AUTOMOD_BYPASS_ROLE_ID = int(os.getenv("YCF_AUTOMOD_BYPASS_ROLE_ID", "0") or "0")
EVERYONE_PING_ALLOWED_ROLE_ID = 1513996922749325464
EVERYONE_PING_OFFENSES_FILE = os.path.join(
    os.path.dirname(__file__), "..", "data", "everyone_ping_offenses.json"
)

# Track recent message times and warning count per user for anti-spam handling.
spam_message_times: dict[int, deque[float]] = defaultdict(deque)
spam_warning_counts: dict[int, int] = defaultdict(int)


def load_everyone_ping_offenses() -> dict[int, int]:
    try:
        with open(EVERYONE_PING_OFFENSES_FILE, "r", encoding="utf-8") as file:
            raw = json.load(file)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}

    if not isinstance(raw, dict):
        return {}

    offenses: dict[int, int] = {}
    for key, value in raw.items():
        if str(key).isdigit() and isinstance(value, int) and value >= 0:
            offenses[int(key)] = value
    return offenses


def save_everyone_ping_offenses(offenses: dict[int, int]) -> None:
    os.makedirs(os.path.dirname(EVERYONE_PING_OFFENSES_FILE), exist_ok=True)
    serializable = {str(user_id): count for user_id, count in offenses.items()}
    with open(EVERYONE_PING_OFFENSES_FILE, "w", encoding="utf-8") as file:
        json.dump(serializable, file, indent=2)


everyone_ping_offenses: dict[int, int] = load_everyone_ping_offenses()


def parse_duration(duration: str) -> timedelta | None:
    value = duration.strip().lower()
    if len(value) < 2:
        return None

    unit = value[-1]
    amount_text = value[:-1]
    if not amount_text.isdigit():
        return None

    amount = int(amount_text)
    if amount <= 0:
        return None

    if unit == "s":
        return timedelta(seconds=amount)
    if unit == "m":
        return timedelta(minutes=amount)
    if unit == "h":
        return timedelta(hours=amount)
    if unit == "d":
        return timedelta(days=amount)

    return None


def parse_channel_id(channel_input: str) -> int | None:
    value = channel_input.strip()

    if value.startswith("<#") and value.endswith(">"):
        value = value[2:-1]

    if value.isdigit():
        return int(value)

    if "/channels/" in value:
        parts = value.rstrip("/").split("/")
        for part in reversed(parts):
            if part.isdigit():
                return int(part)

    return None


def get_insta_ban_word(content: str) -> str | None:
    tokens = re.findall(r"[a-zA-Z]+", content.lower())
    for token in tokens:
        if token in INSTA_BAN_WORDS:
            return token
    return None


def has_automod_bypass(member: discord.Member) -> bool:
    if AUTOMOD_BYPASS_ROLE_ID and any(role.id == AUTOMOD_BYPASS_ROLE_ID for role in member.roles):
        return True

    if any(role.id == EVERYONE_PING_ALLOWED_ROLE_ID for role in member.roles):
        return True

    bypass_names = {"automod bypass", "bypass automod"}
    return any(role.name.strip().lower() in bypass_names for role in member.roles)


async def send_everyone_ping_dm(member: discord.Member, guild_name: str, second_offense: bool) -> None:
    title = "Second Offence" if second_offense else "First Offence"
    if second_offense:
        description = (
            f"You have been banned from **{guild_name}** For Ping @everyone for the second time. "
            "Ban Appeal server not opened yet."
        )
    else:
        description = (
            f"You have been kicked from **{guild_name}** For Pinging @everyone. "
            f"You may re-join here: {EVERYONE_PING_INVITE_URL}"
        )

    embed = discord.Embed(title=title, description=description, color=discord.Color.red())
    await member.send(member.mention, embed=embed)


def sanitize_ticket_name(name: str) -> str:
    cleaned = re.sub(r"[^a-z0-9-]", "-", name.lower())
    cleaned = re.sub(r"-+", "-", cleaned).strip("-")
    return cleaned or "user"


def build_bot_manager_panel_embed() -> discord.Embed:
    embed = discord.Embed(
        title="Bot Manager TIckets",
        description=(
            "*Opening a Bot Manager Ticket shows you have found a bug or you have a suggestion fot the bot*\n"
            f"**DO NOT ping <@{BOT_MANAGER_PING_USER_ID}> DO NOT Troll or you will be blacklisted from opening a ticket**"
        ),
        color=discord.Color.blue(),
    )
    return embed


class BotManagerTicketModal(discord.ui.Modal):
    def __init__(self) -> None:
        super().__init__(title="Open Bot Manager Ticket")

        self.discord_user = discord.ui.InputText(
            label="Discord user",
            style=discord.InputTextStyle.short,
            required=True,
            max_length=100,
        )
        self.suggestion_or_bug = discord.ui.InputText(
            label="Suggestion or Bug Fix??",
            style=discord.InputTextStyle.short,
            required=True,
            max_length=120,
        )
        self.bug_or_suggestion = discord.ui.InputText(
            label="Bug/Suggestion",
            style=discord.InputTextStyle.long,
            required=True,
            max_length=1000,
        )

        self.add_item(self.discord_user)
        self.add_item(self.suggestion_or_bug)
        self.add_item(self.bug_or_suggestion)

    async def callback(self, interaction: discord.Interaction) -> None:
        if interaction.guild is None or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("This can only be used in a server.", ephemeral=True)
            return

        guild = interaction.guild
        member = interaction.user
        category = guild.get_channel(BOT_MANAGER_TICKET_CATEGORY_ID)
        if not isinstance(category, discord.CategoryChannel):
            await interaction.response.send_message("Ticket category not found.", ephemeral=True)
            return

        base_name = f"{sanitize_ticket_name(member.name)}-bm-ticket"
        channel_name = base_name
        existing_names = {c.name for c in category.channels}
        index = 2
        while channel_name in existing_names:
            channel_name = f"{base_name}-{index}"
            index += 1

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            member: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True, read_message_history=True),
        }

        manager_user = guild.get_member(BOT_MANAGER_PING_USER_ID)
        if manager_user is not None:
            overwrites[manager_user] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
            )

        try:
            ticket_channel = await guild.create_text_channel(
                name=channel_name,
                category=category,
                overwrites=overwrites,
                reason=f"Bot Manager ticket opened by {member}",
            )
        except discord.Forbidden:
            await interaction.response.send_message("I do not have permission to create ticket channels.", ephemeral=True)
            return

        opened_embed = discord.Embed(
            title="Bot Manager Ticket Opened!",
            description=(
                f"Hello, {member.mention}\n\n"
                "Your ticket has been opened, thank you for reaching out.\n"
                "Someone from our team will be in touch with you shortly.\n\n"
                "⚠️**Note: all messages will be recorded and saved to our ticket transcript, do not share any sensitive information.**"
            ),
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow(),
        )
        opened_embed.add_field(name="Discord User", value=self.discord_user.value[:1024], inline=False)
        opened_embed.add_field(name="Suggestion or Bug Fix", value=self.suggestion_or_bug.value[:1024], inline=False)
        opened_embed.add_field(name="Bug/Suggestio", value=self.bug_or_suggestion.value[:1024], inline=False)

        await ticket_channel.send(
            f"<@{BOT_MANAGER_PING_USER_ID}>",
            embed=opened_embed,
            allowed_mentions=discord.AllowedMentions(users=True),
        )
        await interaction.response.send_message(f"Ticket created: {ticket_channel.mention}", ephemeral=True)


class BotManagerTicketView(discord.ui.View):
    def __init__(self) -> None:
        super().__init__(timeout=None)

    @discord.ui.button(label="Open a Ticket!", style=discord.ButtonStyle.green, custom_id="bot_manager_open_ticket")
    async def open_ticket(self, button: discord.ui.Button, interaction: discord.Interaction) -> None:
        await interaction.response.send_modal(BotManagerTicketModal())


@bot.event
async def on_ready() -> None:
    bot.add_view(BotManagerTicketView())
    activity = discord.Activity(type=discord.ActivityType.watching, name=STATUS_TEXT)
    await bot.change_presence(activity=activity)
    print(f"YCF Bot is online as {bot.user} (ID: {bot.user.id})")


@bot.event
async def on_message(message: discord.Message) -> None:
    if message.author.bot or message.guild is None:
        await bot.process_commands(message)
        return

    member = message.author
    if (
        isinstance(member, discord.Member)
        and "@everyone" in message.content
        and not has_automod_bypass(member)
    ):
        try:
            await message.delete()
        except discord.Forbidden:
            pass

        offense_count = everyone_ping_offenses.get(member.id, 0) + 1
        everyone_ping_offenses[member.id] = offense_count
        save_everyone_ping_offenses(everyone_ping_offenses)

        is_second_or_more = offense_count >= 2
        try:
            await send_everyone_ping_dm(member, message.guild.name, second_offense=is_second_or_more)
        except discord.Forbidden:
            pass

        if is_second_or_more:
            try:
                await member.ban(reason="Auto-ban for second @everyone ping offense")
                await message.channel.send(
                    f"{member.mention} was banned for a second @everyone ping offense.",
                    allowed_mentions=discord.AllowedMentions(users=True),
                )
            except discord.Forbidden:
                await message.channel.send("I do not have permission to ban that user.")
            return

        try:
            await member.kick(reason="Auto-kick for first @everyone ping offense")
            await message.channel.send(
                f"{member.mention} was kicked for pinging @everyone.",
                allowed_mentions=discord.AllowedMentions(users=True),
            )
        except discord.Forbidden:
            await message.channel.send("I do not have permission to kick that user.")
        return

    banned_word = get_insta_ban_word(message.content)
    if banned_word is not None:
        member = message.author

        try:
            await message.delete()
        except discord.Forbidden:
            pass

        try:
            await member.ban(reason=f"Auto insta-ban for prohibited language: {banned_word}")
        except discord.Forbidden:
            await message.channel.send("I do not have permission to ban that user.")
            await bot.process_commands(message)
            return

        await message.channel.send(
            f"🛑 {member.mention} was instantly banned for prohibited language.",
            allowed_mentions=discord.AllowedMentions(users=True),
        )

        notify_channel = message.guild.get_channel(CM_NOTIFICATION_CHANNEL_ID)
        if isinstance(notify_channel, discord.TextChannel):
            await notify_channel.send(
                "<@&1509212262378770612> | <@&1510670572390977649> | <@&1509212563194253432>",
                allowed_mentions=discord.AllowedMentions(roles=True),
            )
            embed = discord.Embed(
                title="Insta ban word detected",
                description=f"{member.mention} was auto-banned for prohibited language.",
                color=discord.Color.dark_red(),
            )
            embed.add_field(name="Detected word", value=banned_word, inline=False)
            embed.add_field(name="Channel", value=message.channel.mention, inline=False)
            await notify_channel.send(embed=embed)

        return

    user_id = message.author.id
    now_ts = message.created_at.timestamp()
    history = spam_message_times[user_id]

    history.append(now_ts)
    while history and (now_ts - history[0]) > SPAM_WINDOW_SECONDS:
        history.popleft()

    if len(history) >= SPAM_MESSAGE_COUNT:
        spam_warning_counts[user_id] += 1
        warning_count = spam_warning_counts[user_id]
        member = message.author

        if warning_count == 1:
            timeout_delta = timedelta(minutes=10)
            warning_text = (
                f"🛑{member.mention} No spamming in this channel please! "
                "This is you're first warning (1/5)! You will be timed out for 10 minutes. ⚠️"
            )
        elif warning_count == 2:
            timeout_delta = timedelta(hours=1)
            warning_text = (
                f"🛑{member.mention} No spamming in this channel please! "
                "This is you're second warning (2/5)! You will be timed out for 1 hour. ⚠️"
            )
        elif warning_count == 3:
            timeout_delta = timedelta(days=1)
            warning_text = (
                f"🛑{member.mention} No spamming in this channel please! "
                "This is you're third warning (3/5)! You will be timed out for 1 day. ⚠️"
            )
        elif warning_count == 4:
            timeout_delta = timedelta(days=3)
            warning_text = (
                f"🛑{member.mention} No spamming in this channel please! "
                "This is you're fourth warning (4/5)! You will be timed out for 3 days ⚠️"
            )
        else:
            timeout_delta = timedelta(days=7)
            warning_text = (
                f"🛑{member.mention} No spamming in this channel please! "
                "This is you're fourth warning (5/5)! You will be timed out for 7 days. "
                "CM+ will be notifyed of your actions"
            )

        await message.channel.send(warning_text)

        try:
            await member.timeout_for(timeout_delta, reason="Auto anti-spam enforcement")
        except discord.Forbidden:
            await message.channel.send("I do not have permission to timeout that user.")

        if warning_count >= 5:
            notify_channel = message.guild.get_channel(SPAM_NOTIFICATION_CHANNEL_ID)
            if isinstance(notify_channel, discord.TextChannel):
                await notify_channel.send(
                    "<@&1509212262378770612> | <@&1510670572390977649> | <@&1509212563194253432>",
                    allowed_mentions=discord.AllowedMentions(roles=True),
                )
                embed = discord.Embed(
                    title="Fith spam warning detected!",
                    description=(
                        f"{member.mention} Has been suspected to be a known spammer "
                        "please moderat him further."
                    ),
                    color=discord.Color.red(),
                )
                await notify_channel.send(embed=embed)

        history.clear()

    await bot.process_commands(message)


@bot.command(name="ping")
async def ping(ctx: commands.Context) -> None:
    latency_ms = round(bot.latency * 1000)
    await ctx.send(f"Pong! `{latency_ms}ms`")


@bot.command(name="help")
async def help_command(ctx: commands.Context) -> None:
    await ctx.send(
        "**YCF Bot Commands**\n"
        f"`{PREFIX}ping` - Check bot latency\n"
        f"`{PREFIX}help` - Show this command list\n"
        f"`{PREFIX}botmanagertickets` - Post Bot Manager ticket panel\n"
        f"`{PREFIX}tick` - Send friendly tick announcement\n"
        f"`{PREFIX}ticklg <time> <date> <format> <against> <cup> <reward>` - Send league game tick announcement\n"
        f"`{PREFIX}ban @user <reason>` - Ban a member\n"
        f"`{PREFIX}unban <user_id|username#discriminator> <reason>` - Unban a user\n"
        f"`{PREFIX}kick @user <reason>` - Kick a member\n"
        f"`{PREFIX}warn @user <reason>` - Warn a member\n"
        f"`{PREFIX}timeout @user <duration> <reason>` - Timeout a member (10m, 2h, 1d)\n"
        f"`{PREFIX}vcmove @user <channel_link>` - Move user to voice channel\n"
        f"`{PREFIX}closeticket <reason>` - Close the current ticket channel (staff only)\n"
        f"`{PREFIX}closerequest` - Request this ticket be closed"
    )


@bot.command(name="botmanagertickets", aliases=["bmtickets"])
async def botmanagertickets_command(ctx: commands.Context) -> None:
    if ctx.guild is None:
        await ctx.send("This command can only be used in a server.")
        return

    panel_channel = ctx.guild.get_channel(BOT_MANAGER_PANEL_CHANNEL_ID)
    if not isinstance(panel_channel, discord.TextChannel):
        await ctx.send("Bot Manager panel channel not found.")
        return

    await panel_channel.send(embed=build_bot_manager_panel_embed(), view=BotManagerTicketView())
    await ctx.send(f"Bot Manager panel posted in {panel_channel.mention}.")


@bot.command(name="tick")
async def tick_announcement(ctx: commands.Context) -> None:
    message = (
        "|| @everyone ||\n\n"
        "|| @here ||  || <@&1494905919740579987>     ||  ||  @here ||\n\n"
        "*TICK FOR A FRIENDLY*\n\n"
        "**4 + ticks needed**\n"
        "-----------------------\n"
        "***When we get 4 ticks***\n \n"
        "**TAKE THE FRIENDLY SERIOUS!!**\n\n"
        "-----------------------\n"
        "**this can show if u can make in the main lineups.**\n"
        "||  (If your gonna mess around don't join ) ||"
    )
    await ctx.send(
        message,
        allowed_mentions=discord.AllowedMentions(everyone=True, roles=True, users=True),
    )


@bot.command(name="ticklg")
async def tick_league_game(
    ctx: commands.Context,
    time: str,
    date: str,
    game_format: str,
    against: str,
    cup: str,
    *,
    reward: str,
) -> None:
    message = (
        "@everyone @here\n"
        "**LEAGUE GAME**\n"
        "▬▬▬▬▬▬▬▬▬▬\n"
        f"Time: {time}\n"
        f"Date: {date}\n"
        f"Format: {game_format}\n"
        f"Against: {against}\n"
        f"CUP : {cup}\n"
        f"Reward: {reward}\n"
        "▬▬▬▬▬▬▬▬▬▬▬▬\n"
        "✅\n"
        "= You Could Play\n"
        "🤷‍♂️\n"
        "= You Could Maybe Play\n"
        "❌\n"
        "= You Can't Play\n"
        "-----------------\n"
        "LOCK IN\n"
        "CONFIRMED"
    )

    await ctx.send(
        message,
        allowed_mentions=discord.AllowedMentions(everyone=True, roles=True, users=True),
    )


@bot.command(name="ban")
@commands.has_permissions(ban_members=True)
async def ban_member(ctx: commands.Context, member: discord.Member, *, reason: str) -> None:
    if member == ctx.author:
        await ctx.send("You cannot ban yourself.")
        return

    if member.top_role >= ctx.author.top_role and ctx.author != ctx.guild.owner:
        await ctx.send("You cannot ban someone with an equal or higher role.")
        return

    await member.ban(reason=reason)
    await ctx.send(f"Banned {member.mention}. Reason: {reason}")


@bot.command(name="unban")
@commands.has_permissions(ban_members=True)
async def unban_member(ctx: commands.Context, user: str, *, reason: str) -> None:
    user = user.strip()
    if user.startswith("<@") and user.endswith(">"):
        user = user.replace("<@", "").replace("!", "").replace(">", "")

    target_entry = None
    async for entry in ctx.guild.bans(limit=None):
        if user.isdigit() and entry.user.id == int(user):
            target_entry = entry
            break
        if (not user.isdigit()) and str(entry.user) == user:
            target_entry = entry
            break

    if target_entry is None:
        await ctx.send("That user is not currently banned.")
        return

    await ctx.guild.unban(target_entry.user, reason=reason)
    await ctx.send(f"Unbanned {target_entry.user}. Reason: {reason}")


@bot.command(name="kick")
@commands.has_permissions(kick_members=True)
async def kick_member(ctx: commands.Context, member: discord.Member, *, reason: str) -> None:
    if member == ctx.author:
        await ctx.send("You cannot kick yourself.")
        return

    if member.top_role >= ctx.author.top_role and ctx.author != ctx.guild.owner:
        await ctx.send("You cannot kick someone with an equal or higher role.")
        return

    await member.kick(reason=reason)
    await ctx.send(f"Kicked {member.mention}. Reason: {reason}")


@bot.command(name="warn")
@commands.has_permissions(moderate_members=True)
async def warn_member(ctx: commands.Context, member: discord.Member, *, reason: str) -> None:
    if member == ctx.author:
        await ctx.send("You cannot warn yourself.")
        return

    try:
        await member.send(
            f"You were warned in **{ctx.guild.name}** by {ctx.author.mention}. Reason: {reason}"
        )
    except discord.Forbidden:
        pass

    await ctx.send(f"Warned {member.mention}. Reason: {reason}")


@bot.command(name="timeout")
@commands.has_permissions(moderate_members=True)
async def timeout_member(
    ctx: commands.Context, member: discord.Member, duration: str, *, reason: str
) -> None:
    if member == ctx.author:
        await ctx.send("You cannot timeout yourself.")
        return

    delta = parse_duration(duration)
    if delta is None:
        await ctx.send("Invalid duration. Use formats like 30s, 10m, 2h, 1d.")
        return

    await member.timeout_for(delta, reason=reason)
    await ctx.send(f"Timed out {member.mention} for {duration}. Reason: {reason}")


@bot.command(name="vcmove")
@commands.has_permissions(move_members=True)
async def move_voice_member(ctx: commands.Context, member: discord.Member, channel_link: str) -> None:
    channel_id = parse_channel_id(channel_link)
    if channel_id is None:
        await ctx.send("Invalid channel link. Use a voice channel mention or Discord channel URL.")
        return

    channel = ctx.guild.get_channel(channel_id)
    if channel is None or not isinstance(channel, discord.VoiceChannel):
        await ctx.send("Voice channel not found.")
        return

    if member.voice is None:
        await ctx.send(f"{member.mention} is not in a voice channel right now.")
        return

    await member.move_to(channel, reason=f"Voice move by {ctx.author}")
    await ctx.send(f"Moved {member.mention} to {channel.mention}.")


@bot.command(name="closeticket")
@commands.has_permissions(manage_channels=True)
async def close_ticket(ctx: commands.Context, *, reason: str = "No reason provided") -> None:
    """Close the current ticket channel by deleting it after a short confirmation."""
    if ctx.guild is None:
        return

    channel = ctx.channel
    if not isinstance(channel, discord.TextChannel):
        await ctx.send("This command must be used inside a text channel.")
        return

    closing_embed = discord.Embed(
        title="Ticket Closing",
        description=f"This ticket is being closed by {ctx.author.mention}.\n**Reason:** {reason}",
        color=discord.Color.orange(),
        timestamp=discord.utils.utcnow(),
    )
    await ctx.send(embed=closing_embed)
    await channel.delete(reason=f"Ticket closed by {ctx.author} — {reason}")


@bot.command(name="closerequest")
async def close_request(ctx: commands.Context) -> None:
    """Request that the current ticket channel be closed (sends a close request for staff to action)."""
    if ctx.guild is None:
        return

    channel = ctx.channel
    if not isinstance(channel, discord.TextChannel):
        await ctx.send("This command must be used inside a text channel.")
        return

    request_embed = discord.Embed(
        title="Close Request",
        description=(
            f"{ctx.author.mention} has requested this ticket be closed.\n"
            f"A staff member can use `{PREFIX}closeticket <reason>` to close it."
        ),
        color=discord.Color.yellow(),
        timestamp=discord.utils.utcnow(),
    )
    await ctx.send(embed=request_embed)


@ban_member.error
@unban_member.error
@kick_member.error
@warn_member.error
@timeout_member.error
@move_voice_member.error
@close_ticket.error
async def moderation_command_error(ctx: commands.Context, error: commands.CommandError) -> None:
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("You do not have permission to use this command.")
        return

    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"Missing argument: {error.param.name}")
        return

    if isinstance(error, commands.MemberNotFound):
        await ctx.send("Could not find that member. Mention them or use a valid member ID.")
        return

    if isinstance(error, commands.BadArgument):
        await ctx.send("Invalid argument type. Check IDs and command format.")
        return

    if isinstance(error, commands.CommandInvokeError):
        original = error.original
        if isinstance(original, discord.Forbidden):
            await ctx.send("I do not have enough permissions or role position to do that.")
            return

    raise error


def main() -> None:
    if not TOKEN:
        raise RuntimeError("Missing YCF_BOT_TOKEN in environment variables or .env file")
    bot.run(TOKEN)


if __name__ == "__main__":
    main()
