import os
import re
import asyncio
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
APPLICATION_LOG_CHANNEL_ID = 1514004708497424454

LOCKDOWN_ROLE_ID = 1513997243915436142
TICK_COMMAND_ROLE_ID = 1513997062306267167
SPAM_BYPASS_ROLE_ID = 1513996972074340452
AUTOMOD_BYPASS_ROLE_ID = 1513996922749325464
BAN_ROLE_ID = 1513997158108364921
UNBAN_ROLE_ID = 1513997196436050080

# Track recent message times and warning count per user for anti-spam handling.
spam_message_times: dict[int, Deque[tuple[float, str]]] = defaultdict(deque)
spam_warning_counts: dict[int, int] = defaultdict(int)
trigger_words_enabled: dict[int, bool] = defaultdict(lambda: True)
channel_lock_original_send: dict[int, bool | None] = {}

APPLICATION_QUESTIONS = [
    "1. Question 1: What is your Discord username and user ID?\n-# Do !myid to get your discord ID",
    "2. Question 2: How old are you?",
    "3. Question 3: What timezone are you in?",
    "4. Question 4: How active are you on a scale of 1-10?",
    "5. Question 5: What moderation experience do you have?",
    "6. Question 6: Why do you want to become Santos C.F. Modrator?",
    "7. Question 7: How would you handle arguments between members?",
    "8. Question 8: How would you handle a spammer or raider?",
    "9. Question 9: Have you ever been punished in this server? Timedout? Warninged? Kicked? Baned?",
    "10. Question 10: Anything else we should know about you?",
]


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


def parse_lockdown_duration(duration: str) -> int | None:
    value = duration.strip().lower()
    if value == "forever":
        return None

    if len(value) < 2:
        raise ValueError("Invalid duration format")

    unit = value[-1]
    amount_text = value[:-1]
    if not amount_text.isdigit():
        raise ValueError("Invalid duration format")

    amount = int(amount_text)
    if amount <= 0:
        raise ValueError("Duration must be greater than zero")

    if unit == "m":
        return amount * 60
    if unit == "h":
        return amount * 3600
    if unit == "d":
        return amount * 86400
    if unit == "w":
        return amount * 604800

    raise ValueError("Invalid duration unit")


def member_has_role(member: discord.Member, role_id: int) -> bool:
    return any(role.id == role_id for role in member.roles)


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


def build_application_prompt_embed() -> discord.Embed:
    embed = discord.Embed(
        description=(
            "Want to apply to become a moderator? Say !apply or !application.\n"
            "-# Note: Do !settigns and turn of trigger words if you are sick of these messages!"
        ),
        color=discord.Color.blue(),
    )
    return embed


def build_settings_embed(user: discord.abc.User) -> discord.Embed:
    enabled = trigger_words_enabled[user.id]
    status = "Trigger Words 🟢" if enabled else "Trigger Words 🔴"
    next_hint = (
        "Trigger words off 🔴 (If off say Trrigger words on 🟢)"
        if enabled
        else "Trigger words on 🟢 (If off say Trrigger words on 🟢)"
    )
    embed = discord.Embed(
        title=f"Here is {user.display_name} Settigns",
        description=(
            "Trigger Words 🟢=If on 🔴= If off\n"
            f"Current: {status}\n"
            f"{next_hint}"
        ),
        color=discord.Color.blue(),
    )
    return embed


class TriggerWordsSelect(discord.ui.Select):
    def __init__(self) -> None:
        super().__init__(
            placeholder="Choose trigger word setting",
            min_values=1,
            max_values=1,
            options=[
                discord.SelectOption(
                    label="Trigger words off [OFF]",
                    value="off",
                    description="Turn off application trigger replies",
                ),
                discord.SelectOption(
                    label="Trigger words on [ON]",
                    value="on",
                    description="Turn on application trigger replies",
                ),
            ],
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        if self.values[0] == "off":
            trigger_words_enabled[interaction.user.id] = False
        else:
            trigger_words_enabled[interaction.user.id] = True

        embed = build_settings_embed(interaction.user)
        await interaction.response.edit_message(embed=embed, view=TriggerWordsView())


class TriggerWordsView(discord.ui.View):
    def __init__(self) -> None:
        super().__init__(timeout=300)
        self.add_item(TriggerWordsSelect())


class ApplicationDecisionModal(discord.ui.Modal):
    def __init__(self, applicant_id: int, action: str) -> None:
        super().__init__(title=f"Application {action.title()}")
        self.applicant_id = applicant_id
        self.action = action

        self.reason = discord.ui.InputText(
            label="Reason",
            style=discord.InputTextStyle.long,
            required=True,
            max_length=1000,
            placeholder="Enter decision reason",
        )
        self.add_item(self.reason)

    async def callback(self, interaction: discord.Interaction) -> None:
        reason_text = self.reason.value.strip()
        decision = "Approved" if self.action == "approve" else "Denied"

        try:
            user = await bot.fetch_user(self.applicant_id)
        except discord.HTTPException:
            await interaction.response.send_message("Could not find that applicant.", ephemeral=True)
            return

        if self.action == "approve":
            dm_embed = discord.Embed(
                title="Application Approved",
                description=(
                    "Your staff application has been approved.\n\n"
                    f"Reason: {reason_text}\n\n"
                    "Information about staff: check your staff channels, follow staff guidance, "
                    "and contact leadership if you need onboarding support."
                ),
                color=discord.Color.green(),
                timestamp=discord.utils.utcnow(),
            )
        else:
            dm_embed = discord.Embed(
                title="Application Denied",
                description=(
                    "Your staff application has been denied.\n\n"
                    f"Reason: {reason_text}\n\n"
                    "You can re-apply in 7 days."
                ),
                color=discord.Color.red(),
                timestamp=discord.utils.utcnow(),
            )

        dm_status = "DM sent"
        try:
            await user.send(embed=dm_embed)
        except discord.Forbidden:
            dm_status = "Could not DM applicant"

        if interaction.message and interaction.message.embeds:
            updated = interaction.message.embeds[0]
        else:
            updated = discord.Embed(title="Staff Application Submission")

        updated.color = discord.Color.green() if self.action == "approve" else discord.Color.red()
        updated.add_field(name="Decision", value=decision, inline=True)
        updated.add_field(name="Handled By", value=interaction.user.mention, inline=True)
        updated.add_field(name="Decision Reason", value=reason_text[:1024], inline=False)
        updated.add_field(name="Applicant DM", value=dm_status, inline=False)
        updated.set_footer(text=f"Application status: {decision}")

        view = ApplicationReviewView(self.applicant_id)
        for item in view.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True

        await interaction.response.edit_message(embed=updated, view=view)


class ApplicationReviewView(discord.ui.View):
    def __init__(self, applicant_id: int) -> None:
        super().__init__(timeout=None)
        self.applicant_id = applicant_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("Only staff can review applications.", ephemeral=True)
            return False
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message("You need Manage Server permission.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Approve", style=discord.ButtonStyle.green)
    async def approve(self, button: discord.ui.Button, interaction: discord.Interaction) -> None:
        await interaction.response.send_modal(ApplicationDecisionModal(self.applicant_id, "approve"))

    @discord.ui.button(label="Deny", style=discord.ButtonStyle.red)
    async def deny(self, button: discord.ui.Button, interaction: discord.Interaction) -> None:
        await interaction.response.send_modal(ApplicationDecisionModal(self.applicant_id, "deny"))


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

    message_text = (message.content or "").strip()
    lowered_text = message_text.lower()
    role_ids = set()
    if isinstance(message.author, discord.Member):
        role_ids = {role.id for role in message.author.roles}

    if lowered_text in {"trigger words off", "trrigger words off"}:
        trigger_words_enabled[message.author.id] = False
        await message.channel.send("Trigger words are now off [OFF].")
        await bot.process_commands(message)
        return

    if lowered_text in {"trigger words on", "trrigger words on"}:
        trigger_words_enabled[message.author.id] = True
        await message.channel.send("Trigger words are now on [ON].")
        await bot.process_commands(message)
        return

    if (
        trigger_words_enabled[message.author.id]
        and not message_text.startswith(PREFIX)
        and lowered_text in {"application", "apply"}
    ):
        await message.channel.send(embed=build_application_prompt_embed())

    banned_word = get_insta_ban_word(message.content)
    if banned_word is not None and AUTOMOD_BYPASS_ROLE_ID not in role_ids:
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

    if len(history) >= SPAM_MESSAGE_COUNT and SPAM_BYPASS_ROLE_ID not in role_ids:
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
        f"`{PREFIX}applications` - Show application info\n"
        f"`{PREFIX}apply` or `{PREFIX}application` - Start mod application in DMs\n"
        f"`{PREFIX}settigns` - Trigger-word settings\n"
        f"`{PREFIX}myid` - Show your user ID\n"
        f"`{PREFIX}tick` - Send friendly tick announcement\n"
        f"`{PREFIX}ticklg <time> <date> <format> <against> <cup> <reward>` - Send league game tick announcement\n"
        f"`{PREFIX}ban @user <reason>` - Ban a member\n"
        f"`{PREFIX}unban <user_id|username#discriminator> <reason>` - Unban a user\n"
        f"`{PREFIX}kick @user <reason>` - Kick a member\n"
        f"`{PREFIX}warn @user <reason>` - Warn a member\n"
        f"`{PREFIX}timeout @user <duration> <reason>` - Timeout a member (10m, 2h, 1d)\n"
        f"`{PREFIX}vcmove @user <channel_link>` - Move user to voice channel"
    )


@bot.command(name="applications")
async def applications_info(ctx: commands.Context) -> None:
    await ctx.send(embed=build_application_prompt_embed())


@bot.command(name="settigns")
async def settings_command(ctx: commands.Context) -> None:
    await ctx.send(embed=build_settings_embed(ctx.author), view=TriggerWordsView())


@bot.command(name="myid")
async def myid_command(ctx: commands.Context) -> None:
    await ctx.send(f"Your Discord ID is: `{ctx.author.id}`")


@bot.command(name="apply", aliases=["application"])
async def apply_command(ctx: commands.Context) -> None:
    dm_channel = await ctx.author.create_dm()

    await dm_channel.send(
        "Welcome to the Santos C.F. Moderation Application. Please answer each question one by one. "
        "You have 15 minutes per question. If you agree say \"I agree to the following\" "
        "If you do not your application will end."
    )

    def dm_check(dm_message: discord.Message) -> bool:
        return dm_message.author.id == ctx.author.id and dm_message.channel.id == dm_channel.id

    try:
        agreement = await bot.wait_for("message", timeout=900, check=dm_check)
    except asyncio.TimeoutError:
        await dm_channel.send("Application ended due to timeout.")
        return

    if agreement.content.strip().lower() != "i agree to the following":
        await dm_channel.send("Application ended because agreement was not confirmed.")
        return

    answers: list[str] = []
    for question in APPLICATION_QUESTIONS:
        await dm_channel.send(question)
        try:
            answer = await bot.wait_for("message", timeout=900, check=dm_check)
        except asyncio.TimeoutError:
            await dm_channel.send("Application ended due to timeout.")
            return
        answers.append(answer.content.strip() or "[No answer]")

    await dm_channel.send("Thank you. Your staff application has been submitted to staff.")

    log_channel = ctx.guild.get_channel(APPLICATION_LOG_CHANNEL_ID) if ctx.guild else None
    if not isinstance(log_channel, discord.TextChannel):
        await dm_channel.send("I could not find the staff application review channel.")
        return

    application_embed = discord.Embed(
        title="Staff Application Submission",
        color=discord.Color.blue(),
        timestamp=discord.utils.utcnow(),
    )
    application_embed.add_field(name="Applicant", value=ctx.author.mention, inline=False)
    application_embed.add_field(name="Applicant ID", value=str(ctx.author.id), inline=False)

    for index, question in enumerate(APPLICATION_QUESTIONS):
        short_question = question.split("\n", 1)[0]
        answer_text = answers[index][:1024]
        application_embed.add_field(name=short_question, value=answer_text, inline=False)

    application_embed.add_field(
        name="Staff Review",
        value=(
            "Use buttons below to approve or deny with a reason.\n"
            f"Fallback: `{PREFIX}appapprove {ctx.author.id} <reason>` or `{PREFIX}appdeny {ctx.author.id} <reason>`"
        ),
        inline=False,
    )
    application_embed.set_footer(text="Application status: Pending")

    await log_channel.send(embed=application_embed, view=ApplicationReviewView(ctx.author.id))


@bot.command(name="appapprove")
@commands.has_permissions(manage_guild=True)
async def appapprove_command(ctx: commands.Context, user: discord.User, *, reason: str) -> None:
    approve_embed = discord.Embed(
        title="Application Approved",
        description=(
            "Congratulations, your Santos C.F. moderator application has been approved.\n\n"
            f"Reason: {reason}\n\n"
            "Staff Information: Please check all staff channels, follow staff rules, "
            "and contact leadership if you need onboarding help."
        ),
        color=discord.Color.green(),
        timestamp=discord.utils.utcnow(),
    )

    try:
        await user.send(embed=approve_embed)
    except discord.Forbidden:
        await ctx.send("Approved, but I could not DM that user.")
        return

    await ctx.send(f"Approved application for {user.mention}. Reason sent in DM.")


@bot.command(name="appdeny")
@commands.has_permissions(manage_guild=True)
async def appdeny_command(ctx: commands.Context, user: discord.User, *, reason: str) -> None:
    deny_embed = discord.Embed(
        title="Application Denied",
        description=(
            "Your Santos C.F. moderator application has been denied.\n\n"
            f"Reason: {reason}\n\n"
            "You can improve based on this feedback and re-apply in 7 days."
        ),
        color=discord.Color.red(),
        timestamp=discord.utils.utcnow(),
    )

    try:
        await user.send(embed=deny_embed)
    except discord.Forbidden:
        await ctx.send("Denied, but I could not DM that user.")
        return

    await ctx.send(f"Denied application for {user.mention}. Reason sent in DM.")


@bot.command(name="tick")
async def tick_announcement(ctx: commands.Context) -> None:
    if not isinstance(ctx.author, discord.Member) or not member_has_role(ctx.author, TICK_COMMAND_ROLE_ID):
        await ctx.send("You do not have permission to use this command.")
        return

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
    if not isinstance(ctx.author, discord.Member) or not member_has_role(ctx.author, TICK_COMMAND_ROLE_ID):
        await ctx.send("You do not have permission to use this command.")
        return

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
async def ban_member(ctx: commands.Context, member: discord.Member, *, reason: str) -> None:
    if not isinstance(ctx.author, discord.Member) or not member_has_role(ctx.author, BAN_ROLE_ID):
        await ctx.send("You do not have permission to use this command.")
        return

    if member == ctx.author:
        await ctx.send("You cannot ban yourself.")
        return

    if member.top_role >= ctx.author.top_role and ctx.author != ctx.guild.owner:
        await ctx.send("You cannot ban someone with an equal or higher role.")
        return

    await member.ban(reason=reason)
    await ctx.send(f"Banned {member.mention}. Reason: {reason}")


@bot.command(name="unban")
async def unban_member(ctx: commands.Context, user: str, *, reason: str) -> None:
    if not isinstance(ctx.author, discord.Member) or not member_has_role(ctx.author, UNBAN_ROLE_ID):
        await ctx.send("You do not have permission to use this command.")
        return

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
async def move_voice_member(ctx: commands.Context, member: discord.Member, channel_link: str) -> None:
    if not isinstance(ctx.author, discord.Member) or not member_has_role(ctx.author, TICK_COMMAND_ROLE_ID):
        await ctx.send("You do not have permission to use this command.")
        return

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


async def unlock_channel_later(
    guild: discord.Guild,
    channels: list[discord.TextChannel],
    seconds: int,
) -> None:
    await asyncio.sleep(seconds)
    default_role = guild.default_role

    for channel in channels:
        overwrite = channel.overwrites_for(default_role)
        original_send = channel_lock_original_send.get(channel.id)
        overwrite.send_messages = original_send
        try:
            await channel.set_permissions(default_role, overwrite=overwrite, reason="Lockdown expired")
        except discord.Forbidden:
            continue


@bot.command(name="lockdown")
async def lockdown_command(ctx: commands.Context, channel_target: str, duration: str) -> None:
    if ctx.guild is None or not isinstance(ctx.author, discord.Member):
        await ctx.send("This command can only be used in a server.")
        return

    if not member_has_role(ctx.author, LOCKDOWN_ROLE_ID):
        await ctx.send("You do not have permission to use this command.")
        return

    try:
        duration_seconds = parse_lockdown_duration(duration)
    except ValueError:
        await ctx.send("Invalid duration. Use 1m, 1h, 1d, 1w, or Forever.")
        return

    channels_to_lock: list[discord.TextChannel] = []
    if channel_target.lower() == "all":
        channels_to_lock = list(ctx.guild.text_channels)
    else:
        channel_id = parse_channel_id(channel_target)
        if channel_id is None:
            await ctx.send("Invalid channel ID. Use a valid channel ID, mention, or `all`.")
            return

        target_channel = ctx.guild.get_channel(channel_id)
        if not isinstance(target_channel, discord.TextChannel):
            await ctx.send("Channel not found or not a text channel.")
            return
        channels_to_lock = [target_channel]

    default_role = ctx.guild.default_role
    locked_count = 0
    for channel in channels_to_lock:
        overwrite = channel.overwrites_for(default_role)
        if channel.id not in channel_lock_original_send:
            channel_lock_original_send[channel.id] = overwrite.send_messages

        overwrite.send_messages = False
        try:
            await channel.set_permissions(default_role, overwrite=overwrite, reason=f"Lockdown by {ctx.author}")
            locked_count += 1
        except discord.Forbidden:
            continue

    if locked_count == 0:
        await ctx.send("I could not lock any channels due to missing permissions.")
        return

    if duration_seconds is None:
        await ctx.send(f"Locked {locked_count} channel(s) indefinitely.")
        return

    asyncio.create_task(unlock_channel_later(ctx.guild, channels_to_lock, duration_seconds))
    await ctx.send(f"Locked {locked_count} channel(s) for {duration}.")


@ban_member.error
@unban_member.error
@kick_member.error
@warn_member.error
@timeout_member.error
@move_voice_member.error
@appapprove_command.error
@appdeny_command.error
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
