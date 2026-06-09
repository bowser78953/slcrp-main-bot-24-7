import os
import re
from collections import defaultdict, deque
from datetime import datetime, timezone
from datetime import timedelta
from typing import Deque

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
SPAM_LOG_CHANNEL_ID = 1513995796151013486
CM_NOTIFICATION_CHANNEL_ID = 1510463018717413386
INSTA_BAN_WORDS = {"cunt", "nigger", "nigga", "whore", "pussy", "cock"}

# Track recent message times and warning count per user for anti-spam handling.
spam_message_times: dict[int, Deque[tuple[float, str]]] = defaultdict(deque)
spam_warning_counts: dict[int, int] = defaultdict(int)


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


@bot.event
async def on_ready() -> None:
    activity = discord.Activity(type=discord.ActivityType.watching, name=STATUS_TEXT)
    await bot.change_presence(activity=activity)
    print(f"YCF Bot is online as {bot.user} (ID: {bot.user.id})")


@bot.event
async def on_message(message: discord.Message) -> None:
    if message.author.bot or message.guild is None:
        await bot.process_commands(message)
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
    preview = (message.content or "").strip()
    if not preview:
        preview = "[Attachment message]" if message.attachments else "[No text content]"
    preview = preview.replace("`", "'")
    if len(preview) > 140:
        preview = preview[:137] + "..."

    history = spam_message_times[user_id]

    history.append((now_ts, preview))
    while history and (now_ts - history[0][0]) > SPAM_WINDOW_SECONDS:
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
            timeout_result = f"User timed out for {timeout_delta}"
        except discord.Forbidden:
            await message.channel.send("I do not have permission to timeout that user.")
            timeout_result = "Failed to timeout user (missing permissions or role hierarchy)"

        recent_lines = []
        for received_ts, recent_preview in list(history):
            recent_lines.append(
                f"[{datetime.fromtimestamp(received_ts, tz=timezone.utc).strftime('%H:%M:%S')}] {recent_preview}"
            )

        recent_messages_value = "\n".join(recent_lines)
        if len(recent_messages_value) > 1024:
            recent_messages_value = recent_messages_value[:1021] + "..."

        spam_log_embed = discord.Embed(
            title="Spam Attempt Detected",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow(),
        )
        spam_log_embed.add_field(name="User", value=member.mention, inline=False)
        spam_log_embed.add_field(name="User ID", value=str(member.id), inline=False)
        spam_log_embed.add_field(
            name=f"Messages in {SPAM_WINDOW_SECONDS}s",
            value=str(len(history)),
            inline=False,
        )
        spam_log_embed.add_field(name="Recent Messages", value=recent_messages_value, inline=False)
        spam_log_embed.add_field(name="Channel", value=message.channel.mention, inline=False)
        spam_log_embed.add_field(
            name="Date",
            value=discord.utils.format_dt(discord.utils.utcnow(), style="F"),
            inline=False,
        )
        spam_log_embed.add_field(
            name="Action",
            value=f"Warning {warning_count}/5 | {timeout_result}",
            inline=False,
        )
        if message.guild.icon:
            spam_log_embed.set_thumbnail(url=message.guild.icon.url)
        spam_log_embed.set_footer(text="SLCRP | Salt Lake City RP Anti-spam")

        spam_log_channel = message.guild.get_channel(SPAM_LOG_CHANNEL_ID)
        if isinstance(spam_log_channel, discord.TextChannel):
            await spam_log_channel.send(embed=spam_log_embed)

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
        f"`{PREFIX}tick` - Send friendly tick announcement\n"
        f"`{PREFIX}ticklg <time> <date> <format> <against> <cup> <reward>` - Send league game tick announcement\n"
        f"`{PREFIX}ban @user <reason>` - Ban a member\n"
        f"`{PREFIX}unban <user_id|username#discriminator> <reason>` - Unban a user\n"
        f"`{PREFIX}kick @user <reason>` - Kick a member\n"
        f"`{PREFIX}warn @user <reason>` - Warn a member\n"
        f"`{PREFIX}timeout @user <duration> <reason>` - Timeout a member (10m, 2h, 1d)\n"
        f"`{PREFIX}vcmove @user <channel_link>` - Move user to voice channel"
    )


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


@ban_member.error
@unban_member.error
@kick_member.error
@warn_member.error
@timeout_member.error
@move_voice_member.error
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
