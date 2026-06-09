import discord
from discord.ext import commands, tasks
import os
import json
from dotenv import load_dotenv
import asyncio
from datetime import datetime
import io

# Prefer the dedicated ModMail environment file, then fall back to legacy bot2 env.
modmail_env_path = os.path.join(os.path.dirname(__file__), '.env.modmail')
legacy_env_path = os.path.join(os.path.dirname(__file__), '..', '.env.bot2')
load_dotenv(dotenv_path=modmail_env_path)
load_dotenv(dotenv_path=legacy_env_path)
TOKEN = os.getenv('MODMAIL_TOKEN') or os.getenv('DISCORD_TOKEN')

if not TOKEN:
    print("ERROR: No ModMail token found in .env.modmail (MODMAIL_TOKEN) or .env.bot2 (DISCORD_TOKEN)!")
    exit(1)

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix=('s!', '-'), intents=intents)

# Configuration - Change these to your server settings
GUILD_ID = 1500595644220444752  # Ban appeal server for ModMail
MODMAIL_CATEGORY_NAME = "ModMail Tickets"
LOG_CHANNEL_NAME = "modmail-logs"
STAFF_ROLE_NAME = "Staff"  # Role that can see and respond to tickets
BAN_APPEAL_DM_QUEUE_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', 'data', 'ban_appeal_dm_queue.jsonl')
)

active_tickets = {}  # {user_id: channel_id}


def ensure_ban_appeal_dm_queue_file():
    os.makedirs(os.path.dirname(BAN_APPEAL_DM_QUEUE_PATH), exist_ok=True)
    if not os.path.exists(BAN_APPEAL_DM_QUEUE_PATH):
        with open(BAN_APPEAL_DM_QUEUE_PATH, 'w', encoding='utf-8'):
            pass


def pop_pending_ban_appeal_dms():
    ensure_ban_appeal_dm_queue_file()

    try:
        with open(BAN_APPEAL_DM_QUEUE_PATH, 'r', encoding='utf-8') as file:
            raw_lines = file.readlines()
    except OSError:
        return []

    try:
        with open(BAN_APPEAL_DM_QUEUE_PATH, 'w', encoding='utf-8'):
            pass
    except OSError:
        return []

    payloads = []
    for raw_line in raw_lines:
        line = raw_line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            payloads.append(payload)

    return payloads


def append_pending_ban_appeal_dms(payloads):
    if not payloads:
        return

    ensure_ban_appeal_dm_queue_file()
    with open(BAN_APPEAL_DM_QUEUE_PATH, 'a', encoding='utf-8') as file:
        for payload in payloads:
            file.write(json.dumps(payload) + '\n')


async def get_ban_appeal_invite_url(guild):
    try:
        invites = await guild.invites()
        for invite in invites:
            if invite.max_age == 0 and invite.max_uses == 0:
                return invite.url
    except discord.Forbidden:
        pass
    except discord.HTTPException:
        pass

    for channel in guild.text_channels:
        permissions = channel.permissions_for(guild.me) if guild.me else None
        if permissions is None or not permissions.create_instant_invite:
            continue
        try:
            invite = await channel.create_invite(max_age=0, max_uses=0, reason='Ban appeal invite for banned user')
            return invite.url
        except discord.Forbidden:
            continue
        except discord.HTTPException:
            continue

    return None


def format_staff_tag(user: discord.abc.User) -> str:
    discriminator = getattr(user, 'discriminator', None)
    if discriminator and discriminator != '0':
        return f"{user.name}{discriminator}"
    return user.name


def build_blocked_banned_embed() -> discord.Embed:
    return discord.Embed(
        title='Blocked & Banned',
        description=(
            'You have been blocked and banned from using the Mod Mail system.\n\n'
            'This could be due to:\n'
            '- Rule violation\n'
            '- Spam or trolling\n'
            '- Misuse of Mod Mail\n\n'
            'You are not allowed to appeal.\n\n'
            'Thank you for understanding.'
        ),
        color=discord.Color.red(),
        timestamp=datetime.utcnow(),
    )


async def send_modmail_ban_appeal_dm(payload):
    user_id = int(payload.get('user_id'))
    user = await bot.fetch_user(user_id)
    guild = bot.get_guild(GUILD_ID)
    invite_url = payload.get('appeal_invite_url')
    if not invite_url and guild is not None:
        invite_url = await get_ban_appeal_invite_url(guild)

    action = str(payload.get('action') or 'banned')
    reason = str(payload.get('reason') or 'No reason provided')
    moderator = str(payload.get('moderator') or 'Unknown staff member')

    embed = discord.Embed(
        title='BP | Mod Mail Ban Appeal',
        description=(
            f'You have been {action}. If you want to appeal, join the ban appeal server below '
            'and DM this bot after you join.'
        ),
        color=discord.Color.orange(),
        timestamp=datetime.utcnow(),
    )
    embed.add_field(name='Reason', value=reason, inline=False)
    embed.add_field(name='Actioned By', value=moderator, inline=False)
    if invite_url:
        embed.add_field(name='Ban Appeal Server', value=invite_url, inline=False)
    else:
        embed.add_field(
            name='Ban Appeal Server',
            value='Invite unavailable right now. Contact staff if you need the appeal link.',
            inline=False,
        )

    if invite_url:
        await user.send(content=f'Ban appeal server link: {invite_url}', embed=embed)
    else:
        await user.send(embed=embed)


async def close_ticket_channel(channel, closed_by, close_reason='Ticket closed'):
    user_id = None
    for uid, channel_id in active_tickets.items():
        if channel_id == channel.id:
            user_id = uid
            break

    if not user_id:
        return False

    user = await bot.fetch_user(user_id)

    transcript = []
    async for msg in channel.history(limit=200, oldest_first=True):
        if msg.embeds:
            for embed in msg.embeds:
                if embed.author.name:
                    transcript.append(f"[{msg.created_at.strftime('%Y-%m-%d %H:%M:%S')}] {embed.author.name}: {embed.description}")
        elif not msg.author.bot:
            transcript.append(f"[{msg.created_at.strftime('%Y-%m-%d %H:%M:%S')}] {msg.author.name}: {msg.content}")

    transcript_text = '\n'.join(transcript)

    guild = channel.guild
    log_channel = discord.utils.get(guild.text_channels, name=LOG_CHANNEL_NAME)
    if log_channel:
        log_embed = discord.Embed(
            title='🔒 Ticket Closed',
            description=(
                f'**User:** {user.mention} ({user.name}#{user.discriminator})\n'
                f'**Closed by:** {closed_by.mention}\n'
                f'**Channel:** {channel.name}\n'
                f'**Reason:** {close_reason}'
            ),
            color=discord.Color.red(),
            timestamp=datetime.utcnow()
        )
        await log_channel.send(embed=log_embed)

        if transcript_text:
            transcript_bytes = io.BytesIO(transcript_text.encode('utf-8'))
            transcript_file = discord.File(
                fp=transcript_bytes,
                filename=f"transcript-{user.name}-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}.txt"
            )
            await log_channel.send(file=transcript_file)

    try:
        close_embed = discord.Embed(
            title='🔒 Ticket Closed',
            description=(
                f'Your ModMail ticket has been closed by {closed_by.name}.\n\n'
                f'Reason: {close_reason}\n\n'
                'If you need further assistance, feel free to send another message!'
            ),
            color=discord.Color.red(),
            timestamp=datetime.utcnow()
        )
        await user.send(embed=close_embed)
    except:
        pass

    if user_id in active_tickets:
        del active_tickets[user_id]

    await channel.delete()
    return True


@tasks.loop(seconds=10)
async def process_ban_appeal_dm_queue():
    payloads = pop_pending_ban_appeal_dms()
    if not payloads:
        return

    retry_payloads = []
    for payload in payloads:
        try:
            await send_modmail_ban_appeal_dm(payload)
        except discord.Forbidden:
            continue
        except discord.NotFound:
            continue
        except (discord.HTTPException, OSError, ValueError, TypeError):
            retry_payloads.append(payload)

    if retry_payloads:
        append_pending_ban_appeal_dms(retry_payloads)


@process_ban_appeal_dm_queue.before_loop
async def before_process_ban_appeal_dm_queue():
    await bot.wait_until_ready()

@bot.event
async def on_ready():
    print(f'ModMail Bot logged in as {bot.user.name}')
    print(f'Bot ID: {bot.user.id}')
    print('--------------------------------------------------')
    
    guild = bot.get_guild(GUILD_ID)
    if guild:
        print(f'Connected to server: {guild.name} (ID: {guild.id})')
        
        # Check/Create ModMail category
        category = discord.utils.get(guild.categories, name=MODMAIL_CATEGORY_NAME)
        if not category:
            print(f'Creating category: {MODMAIL_CATEGORY_NAME}')
            await guild.create_category(MODMAIL_CATEGORY_NAME)
        
        # Check/Create log channel
        log_channel = discord.utils.get(guild.text_channels, name=LOG_CHANNEL_NAME)
        if not log_channel:
            print(f'Creating log channel: {LOG_CHANNEL_NAME}')
            await guild.create_text_channel(LOG_CHANNEL_NAME)
        
        print('ModMail system is ready!')
    else:
        print(f'ERROR: Could not find server with ID {GUILD_ID}')
        print('Make sure the bot is invited to the server!')

    if not process_ban_appeal_dm_queue.is_running():
        process_ban_appeal_dm_queue.start()
    
    print('--------------------------------------------------')

@bot.event
async def on_message(message):
    # Ignore bot messages
    if message.author.bot:
        return
    
    # Check if it's a DM
    if isinstance(message.channel, discord.DMChannel):
        await handle_dm(message)
        return
    
    # Check if it's a message in a ticket channel
    if message.channel.name.startswith('ticket-'):
        await handle_ticket_reply(message)
    
    await bot.process_commands(message)

async def handle_dm(message):
    """Handle incoming DMs and create/update tickets"""
    user = message.author
    guild = bot.get_guild(GUILD_ID)
    
    if not guild:
        await message.author.send("❌ Bot is not connected to a server.")
        return
    
    # Check if user is in the server
    member = guild.get_member(user.id)
    if not member:
        # User is not in the server, send them an invite link
        try:
            # Try to get an existing invite or create a new one
            invites = await guild.invites()
            invite_link = None
            
            # Look for a non-expiring invite
            for invite in invites:
                if invite.max_age == 0:  # Non-expiring invite
                    invite_link = invite.url
                    break
            
            # If no permanent invite exists, create one
            if not invite_link:
                # Get the first text channel to create an invite
                channel = guild.text_channels[0] if guild.text_channels else None
                if channel:
                    invite = await channel.create_invite(max_age=0, max_uses=0, reason="ModMail invite for user not in server")
                    invite_link = invite.url
            
            if invite_link:
                not_in_server_embed = discord.Embed(
                    title="📬 Server Invite Required",
                    description=f"You need to join **{guild.name}** to use ModMail.\n\n**Join here:** {invite_link}",
                    color=discord.Color.orange()
                )
                await message.author.send(embed=not_in_server_embed)
            else:
                await message.author.send("❌ You need to be in the server to use ModMail, but I couldn't create an invite link. Please contact an administrator.")
        except discord.Forbidden:
            await message.author.send("❌ You need to be in the server to use ModMail. Please contact an administrator for an invite.")
        return
    
    # Check if user already has an open ticket
    if user.id in active_tickets:
        channel_id = active_tickets[user.id]
        channel = guild.get_channel(channel_id)
        
        if channel:
            content_text = message.content.strip() if message.content else "[No text content]"
            forward_lines = [f"**{user.name}** Sent: {content_text}"]
            if message.attachments:
                for attachment in message.attachments:
                    forward_lines.append(f"**{user.name}** Sent: {attachment.url}")

            await channel.send("\n".join(forward_lines))
            await message.add_reaction('✅')
            return
    
    # Create new ticket
    category = discord.utils.get(guild.categories, name=MODMAIL_CATEGORY_NAME)
    if not category:
        category = await guild.create_category(MODMAIL_CATEGORY_NAME)
    
    # Create ticket channel
    channel_name = f"ticket-{user.name.lower()}-{user.discriminator}"
    
    # Set permissions
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),
        guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        member: discord.PermissionOverwrite(read_messages=True, send_messages=True, attach_files=True)
    }
    
    # Add staff role if it exists
    staff_role = discord.utils.get(guild.roles, name=STAFF_ROLE_NAME)
    if staff_role:
        overwrites[staff_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
    
    ticket_channel = await guild.create_text_channel(
        name=channel_name,
        category=category,
        overwrites=overwrites
    )
    
    # Store active ticket
    active_tickets[user.id] = ticket_channel.id
    
    # Send initial message in ticket
    initial_embed = discord.Embed(
        title="📬 New ModMail Ticket",
        description=f"**User:** {user.mention} ({user.name}#{user.discriminator})\n**User ID:** {user.id}",
        color=discord.Color.green(),
        timestamp=datetime.utcnow()
    )
    initial_embed.set_thumbnail(url=user.display_avatar.url)
    initial_embed.add_field(
        name="Commands",
        value="`!close` - Close this ticket\n`!reply <message>` - Reply to user (or just type normally)",
        inline=False
    )
    
    await ticket_channel.send(embed=initial_embed)
    
    # Send user's first message as plain text in the ticket channel.
    content_text = message.content.strip() if message.content else "[No text content]"
    first_lines = [f"**{user.name}** Sent: {content_text}"]
    if message.attachments:
        for attachment in message.attachments:
            first_lines.append(f"**{user.name}** Sent: {attachment.url}")

    await ticket_channel.send("\n".join(first_lines))
    
    # Notify staff
    if staff_role:
        await ticket_channel.send(f"{staff_role.mention} New ticket opened!")
    
    # Confirm to user with a styled open-notice card.
    opened_embed = discord.Embed(
        title='Mod Mail Opened',
        description='Your ban appeal has been opened.\nPlease remain respectful.',
        color=discord.Color.blue(),
        timestamp=datetime.utcnow(),
    )
    await message.author.send(embed=opened_embed)
    await message.add_reaction('✅')
    
    # Log in log channel
    log_channel = discord.utils.get(guild.text_channels, name=LOG_CHANNEL_NAME)
    if log_channel:
        log_embed = discord.Embed(
            title="📬 New Ticket Opened",
            description=f"**User:** {user.mention} ({user.name}#{user.discriminator})\n**Channel:** {ticket_channel.mention}",
            color=discord.Color.green(),
            timestamp=datetime.utcnow()
        )
        await log_channel.send(embed=log_embed)

async def handle_ticket_reply(message):
    """Handle staff replies in ticket channels"""
    if message.author.bot:
        return
    
    # Get the user ID from active tickets
    user_id = None
    for uid, channel_id in active_tickets.items():
        if channel_id == message.channel.id:
            user_id = uid
            break
    
    if not user_id:
        return
    
    user = await bot.fetch_user(user_id)
    if not user:
        return
    
    # Don't forward if it's a command.
    if message.content.startswith(('!', '-', 's!')):
        return

    guild = message.guild
    staff_role = discord.utils.get(guild.roles, name=STAFF_ROLE_NAME)
    opener_pinged_staff = (
        message.author.id == user_id
        and staff_role is not None
        and any(role.id == staff_role.id for role in message.role_mentions)
    )
    if opener_pinged_staff:
        await message.add_reaction('✅')
        await close_ticket_channel(
            message.channel,
            message.author,
            close_reason='Staff was pinged in the ticket channel',
        )
        return

    # Let the ticket opener type in-server without DM echoing to themselves.
    if message.author.id == user_id:
        await message.add_reaction('✅')
        return
    
    # Send staff message in the screenshot style.
    content_text = message.content.strip() if message.content else "[No text content]"
    staff_tag = format_staff_tag(message.author)
    dm_lines = [f"`Staff` **{staff_tag}** Sent: {content_text}"]
    if message.attachments:
        for attachment in message.attachments:
            dm_lines.append(f"`Staff` **{staff_tag}** Sent: {attachment.url}")

    try:
        await user.send("\n".join(dm_lines))
        await message.add_reaction('✅')
    except discord.Forbidden:
        await message.channel.send("❌ Cannot send message to user. They may have DMs disabled.")

@bot.command()
async def close(ctx):
    """Close a ModMail ticket"""
    if not ctx.channel.name.startswith('ticket-'):
        await ctx.send("❌ This command can only be used in ticket channels.")
        return

    await ctx.send("🔒 Closing ticket...")
    await close_ticket_channel(ctx.channel, ctx.author, close_reason='Closed by staff command')

@bot.command()
async def reply(ctx, *, message: str):
    """Reply to a user in a ticket (alternative to just typing)"""
    if not ctx.channel.name.startswith('ticket-'):
        await ctx.send("❌ This command can only be used in ticket channels.")
        return
    
    # Find user
    user_id = None
    for uid, channel_id in active_tickets.items():
        if channel_id == ctx.channel.id:
            user_id = uid
            break
    
    if not user_id:
        await ctx.send("❌ Could not find associated user for this ticket.")
        return
    
    user = await bot.fetch_user(user_id)
    
    # Send message in the screenshot style.
    try:
        await user.send(f"`Staff` **{format_staff_tag(ctx.author)}** Sent: {message}")
        await ctx.message.delete()
        await ctx.send("✅ Message sent!", delete_after=3)
    except discord.Forbidden:
        await ctx.send("❌ Cannot send message to user. They may have DMs disabled.")

@bot.command()
async def tickets(ctx):
    """List all open tickets"""
    if not active_tickets:
        await ctx.send("No open tickets.")
        return
    
    embed = discord.Embed(
        title="📬 Open ModMail Tickets",
        color=discord.Color.blue(),
        timestamp=datetime.utcnow()
    )
    
    for user_id, channel_id in active_tickets.items():
        user = await bot.fetch_user(user_id)
        channel = bot.get_channel(channel_id)
        if user and channel:
            embed.add_field(
                name=f"{user.name}#{user.discriminator}",
                value=f"Channel: {channel.mention}\nUser ID: {user_id}",
                inline=False
            )
    
    await ctx.send(embed=embed)

@bot.command()
async def modmail(ctx):
    """Display information about the ModMail bot and Ban Appeal Server"""
    embed = discord.Embed(
        description="Hello! I am the BP | Mod Mail Bot. 🤩\n\nI run the [BP | Ban Appeal Server](https://discord.gg/qGXMwhKf)! If you ever need to appeal a ban DM me!",
        color=discord.Color.blue()
    )
    embed.set_author(name="BP | Mod Mail Bot", icon_url=bot.user.display_avatar.url if bot.user else None)
    
    await ctx.send(embed=embed)


@bot.command(name='cmds', aliases=['commands'])
async def cmds(ctx):
    """List all ModMail commands"""
    embed = discord.Embed(
        title="ModMail Command List",
        color=discord.Color.blurple(),
        timestamp=datetime.utcnow(),
    )
    embed.description = (
        "Use either `-` or `s!` as the prefix.\n\n"
        "`-cmds` - Show this command list\n"
        "`-modmail` - Show ModMail info\n"
        "`-tickets` - List open tickets\n"
        "`-close` - Close current ticket channel\n"
        "`-reply <message>` - Reply to ticket user\n"
        "`-ban <user> <reason>` - Ban user in appeal server\n"
        "`-unban <user> <reason>` - Unban user in appeal server\n"
        "`-banappeal <user> <reason>` - Notify main server staff of appeal\n"
        "`-restart_bot` - Restart ModMail bot (admin)"
    )
    await ctx.send(embed=embed)

@bot.command()
async def restart_bot(ctx):
    """Restart the ModMail bot (Admin only)"""
    # Check if user has administrator permissions
    if not ctx.author.guild_permissions.administrator:
        await ctx.send("❌ You need Administrator permission to restart the bot.")
        return
    
    await ctx.send("🔄 Restarting ModMail bot...")
    await asyncio.sleep(1)
    
    # Close the bot gracefully and exit
    # The process will need to be manually restarted
    import sys
    await bot.close()
    sys.exit(0)

@bot.command(aliases=['BAban', 'baban'])
async def ban(ctx, target: str, *, reason: str = "No reason provided"):
    """Ban a user from the Ban Appeal Server"""
    # Check if user has ban permissions
    if not ctx.author.guild_permissions.ban_members:
        await ctx.send("❌ You need Ban Members permission to use this command.")
        return
    
    guild = bot.get_guild(GUILD_ID)
    if not guild:
        await ctx.send("❌ Could not find the Ban Appeal Server.")
        return
    
    # Resolve target into a User object
    user = None
    try:
        import re
        if target.isdigit():
            user = await bot.fetch_user(int(target))
        else:
            try:
                user = await commands.UserConverter().convert(ctx, target)
            except Exception:
                m = re.search(r"(\d{17,20})", target)
                if m:
                    user = await bot.fetch_user(int(m.group(1)))
    except Exception as e:
        await ctx.send(f"❌ Error resolving user: {e}")
        return
    
    if not user:
        await ctx.send("❌ Could not find that user. Provide a valid mention or ID.")
        return
    
    # Check if user is already banned
    try:
        await guild.fetch_ban(user)
        await ctx.send(f"⚠️ {user.mention} is already banned in this server.")
        return
    except discord.NotFound:
        pass  # User is not banned, continue
    
    # Ban the user
    try:
        await guild.ban(user, reason=f"[ModMail Ban] {reason} (by {ctx.author})", delete_message_days=0)
        
        # Send confirmation
        ban_embed = discord.Embed(
            title="🔨 User Banned",
            color=discord.Color.red(),
            timestamp=datetime.utcnow()
        )
        ban_embed.add_field(name="User", value=f"{user.mention} ({user.name}#{user.discriminator})", inline=False)
        ban_embed.add_field(name="User ID", value=str(user.id), inline=False)
        ban_embed.add_field(name="Reason", value=reason, inline=False)
        ban_embed.add_field(name="Banned By", value=ctx.author.mention, inline=False)
        
        await ctx.send(embed=ban_embed)
        
        # Log to modmail-logs
        log_channel = discord.utils.get(guild.text_channels, name=LOG_CHANNEL_NAME)
        if log_channel:
            await log_channel.send(embed=ban_embed)
        
        # Try to DM the user in the same style shown in screenshots
        try:
            staff_tag = format_staff_tag(ctx.author)
            invite_link = await get_ban_appeal_invite_url(guild)
            await user.send(f"`Staff` **{staff_tag}** Sent: {reason}")
            if invite_link:
                await user.send(f"`Staff` **{staff_tag}** Sent: {invite_link}")
            await user.send(embed=build_blocked_banned_embed())
        except:
            pass  # User has DMs disabled
            
    except discord.Forbidden:
        await ctx.send("❌ I don't have permission to ban this user.")
    except Exception as e:
        await ctx.send(f"❌ Failed to ban user: {e}")

@bot.command(aliases=['BAunban', 'baunban'])
async def unban(ctx, target: str, *, reason: str = "No reason provided"):
    """Unban a user from the Ban Appeal Server"""
    # Check if user has ban permissions
    if not ctx.author.guild_permissions.ban_members:
        await ctx.send("❌ You need Ban Members permission to use this command.")
        return
    
    guild = bot.get_guild(GUILD_ID)
    if not guild:
        await ctx.send("❌ Could not find the Ban Appeal Server.")
        return
    
    # Resolve target into a User object
    user = None
    try:
        import re
        if target.isdigit():
            user = await bot.fetch_user(int(target))
        else:
            try:
                user = await commands.UserConverter().convert(ctx, target)
            except Exception:
                m = re.search(r"(\d{17,20})", target)
                if m:
                    user = await bot.fetch_user(int(m.group(1)))
    except Exception as e:
        await ctx.send(f"❌ Error resolving user: {e}")
        return
    
    if not user:
        await ctx.send("❌ Could not find that user. Provide a valid mention or ID.")
        return
    
    # Check if user is actually banned
    try:
        await guild.fetch_ban(user)
    except discord.NotFound:
        await ctx.send(f"⚠️ {user.mention} is not banned in this server.")
        return
    
    # Unban the user
    try:
        await guild.unban(user, reason=f"[ModMail Unban] {reason} (by {ctx.author})")
        
        # Send confirmation
        unban_embed = discord.Embed(
            title="✅ User Unbanned",
            color=discord.Color.green(),
            timestamp=datetime.utcnow()
        )
        unban_embed.add_field(name="User", value=f"{user.mention} ({user.name}#{user.discriminator})", inline=False)
        unban_embed.add_field(name="User ID", value=str(user.id), inline=False)
        unban_embed.add_field(name="Reason", value=reason, inline=False)
        unban_embed.add_field(name="Unbanned By", value=ctx.author.mention, inline=False)
        
        await ctx.send(embed=unban_embed)
        
        # Log to modmail-logs
        log_channel = discord.utils.get(guild.text_channels, name=LOG_CHANNEL_NAME)
        if log_channel:
            await log_channel.send(embed=unban_embed)
        
        # Try to DM the user in the same style shown in screenshots
        try:
            staff_tag = format_staff_tag(ctx.author)
            invite_link = await get_ban_appeal_invite_url(guild)
            await user.send(f"`Staff` **{staff_tag}** Sent: Unbanned.")
            if invite_link:
                await user.send(f"`Staff` **{staff_tag}** Sent: {invite_link}")
            await user.send(
                f"`Staff` **{staff_tag}** Sent: You are unbanned. You may rejoin your departments if they allow it via tickets inside your previous WL Departments."
            )
        except:
            pass  # User has DMs disabled
            
    except discord.Forbidden:
        await ctx.send("❌ I don't have permission to unban this user.")
    except Exception as e:
        await ctx.send(f"❌ Failed to unban user: {e}")

@bot.command(name='banappeal', aliases=['ban_appeal', 'appealban'])
async def banappeal(ctx, target: str, *, reason: str = "No reason provided"):
    """Mark a ban as appealed and notify staff in the main server"""
    # Check if command is used in the Ban Appeal Server
    if ctx.guild.id != GUILD_ID:
        await ctx.send("❌ This command can only be used in the Ban Appeal Server.")
        return
    
    # Check if user has ban permissions
    if not ctx.author.guild_permissions.ban_members:
        await ctx.send("❌ You need Ban Members permission to use this command.")
        return
    
    # Resolve target into a User object
    user = None
    try:
        import re
        if target.isdigit():
            user = await bot.fetch_user(int(target))
        else:
            try:
                user = await commands.UserConverter().convert(ctx, target)
            except Exception:
                m = re.search(r"(\d{17,20})", target)
                if m:
                    user = await bot.fetch_user(int(m.group(1)))
    except Exception as e:
        await ctx.send(f"❌ Error resolving user: {e}")
        return
    
    if not user:
        await ctx.send("❌ Could not find that user. Provide a valid mention or ID.")
        return
    
    # Get the main server and staff channel
    main_guild_id = 1433178246647779450
    staff_channel_id = 1478907387585761534
    staff_role_id = 1479248603309539349
    
    main_guild = bot.get_guild(main_guild_id)
    if not main_guild:
        await ctx.send("❌ Could not find the main server.")
        return
    
    staff_channel = main_guild.get_channel(staff_channel_id)
    if not staff_channel:
        await ctx.send("❌ Could not find the staff notification channel.")
        return
    
    # Create embed
    appeal_embed = discord.Embed(
        title="BAN APPEALED",
        color=discord.Color.green(),
        timestamp=datetime.utcnow()
    )
    appeal_embed.add_field(name="User That Appealed", value=f"{user.mention} ({user.name}#{user.discriminator})\nID: {user.id}", inline=False)
    appeal_embed.add_field(name="Ban Appeal Staff Member", value=f"{ctx.author.mention} ({ctx.author.name}#{ctx.author.discriminator})", inline=False)
    appeal_embed.add_field(name="Reason", value=reason, inline=False)
    appeal_embed.add_field(name="Action Required", value=f"{user.mention} has appealed their ban and needs to be unbanned. Someone please use the command:", inline=False)
    appeal_embed.add_field(name="Command", value=f"`?asunban {user.id} Appealed`", inline=False)
    
    # Send to staff channel
    try:
        await staff_channel.send(f"<@&{staff_role_id}>", embed=appeal_embed)
        
        # Confirm in Ban Appeal Server
        confirm_embed = discord.Embed(
            title="✅ Ban Appeal Logged",
            description=f"Ban appeal for {user.mention} has been sent to staff in the main server.",
            color=discord.Color.green()
        )
        await ctx.send(embed=confirm_embed)
        
    except discord.Forbidden:
        await ctx.send("❌ I don't have permission to send messages in the staff channel.")
    except Exception as e:
        await ctx.send(f"❌ Failed to send appeal notification: {e}")

if __name__ == "__main__":
    print("Starting ModMail Bot...")
    bot.run(TOKEN)
