from __future__ import annotations

import json
import os
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

from erlc_integration import register_erlc_commands
from shift_management import register_active_shift_commands, register_shift_commands
from shift_types import register_shift_setup


BASE_PATH = Path(__file__).resolve().parent
CONFIG_PATH = BASE_PATH / "config.json"


def load_config() -> dict:
    with CONFIG_PATH.open("r", encoding="utf-8") as config_file:
        config = json.load(config_file)

    if not isinstance(config, dict) or not isinstance(config.get("commands"), dict):
        raise ValueError("config.json must contain a commands object.")
    return config


def make_prefix_callback(response: str):
    async def callback(ctx: commands.Context) -> None:
        await ctx.send(response)

    return callback


def make_slash_callback(response: str):
    async def callback(interaction: discord.Interaction) -> None:
        await interaction.response.send_message(response)

    return callback


def create_bot(config: dict) -> commands.Bot:
    intents = discord.Intents.default()
    intents.message_content = bool(config.get("message_content_intent", True))

    bot = commands.Bot(command_prefix=config.get("prefix", "!"), intents=intents)
    for command_name, command_config in config["commands"].items():
        description = str(command_config.get("description", "Run a Vortex command"))
        response = str(command_config.get("response", ""))
        bot.add_command(
            commands.Command(
                make_prefix_callback(response),
                name=command_name,
                help=description,
            )
        )
        bot.tree.add_command(
            app_commands.Command(
                name=command_name,
                description=description,
                callback=make_slash_callback(response),
            )
        )

    register_shift_setup(bot)
    register_shift_commands(bot)
    register_active_shift_commands(bot)

    async def sync_erlc_for_guild(guild: discord.Guild) -> None:
        synced_guilds: set[int] = getattr(bot, "_erlc_synced_guilds", set())
        if guild.id in synced_guilds:
            return
        register_erlc_commands(bot, guild.id)
        await bot.tree.sync(guild=guild)
        synced_guilds.add(guild.id)
        bot._erlc_synced_guilds = synced_guilds

    bot.add_listener(sync_erlc_for_guild, "on_guild_join")

    activity_config = config.get("activity", {})
    activity_type = getattr(
        discord.ActivityType,
        activity_config.get("type", "playing"),
        discord.ActivityType.playing,
    )
    activity_text = str(activity_config.get("text", "Vortex"))

    @bot.event
    async def on_ready() -> None:
        if config.get("sync_slash_commands", True) and not getattr(bot, "_vortex_synced", False):
            await bot.tree.sync()
            bot._vortex_synced = True
        if config.get("sync_slash_commands", True):
            for guild in bot.guilds:
                await sync_erlc_for_guild(guild)
        await bot.change_presence(
            activity=discord.Activity(type=activity_type, name=activity_text)
        )
        print(f"{config.get('name', 'Vortex')} connected as {bot.user}")

    return bot


def main() -> None:
    load_dotenv(BASE_PATH / ".env")
    token = os.getenv("DISCORD_BOT_TOKEN", "").strip()
    if not token:
        raise SystemExit("Set DISCORD_BOT_TOKEN in vortex_bot/.env before starting Vortex.")

    config = load_config()
    bot = create_bot(config)
    bot.run(token)


if __name__ == "__main__":
    main()
