import os

import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("THIRD_BOT_TOKEN")

if not TOKEN:
    print("ERROR: THIRD_BOT_TOKEN is not set.")
    raise SystemExit(1)

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="t!", intents=intents)


@bot.event
async def on_ready():
    print(f"Third bot logged in as {bot.user}")


@bot.command()
async def ping(ctx):
    await ctx.send("pong")


if __name__ == "__main__":
    print("Starting third bot...")
    bot.run(TOKEN)
