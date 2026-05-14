"""
bot.py — Entry point. Start the bot with: python bot.py
"""

import discord
from discord.ext import commands
from dotenv import load_dotenv
import os

from views import LFGPanelView

load_dotenv()

# ── Intents ───────────────────────────────────────────────────────────────────
intents = discord.Intents.default()
intents.members = True               # needed to mention / look up members

# ── Bot ───────────────────────────────────────────────────────────────────────
bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    await bot.load_extension("cogs.lfg")
    bot.add_view(LFGPanelView())
    await bot.tree.sync()
    print(f"✅  Logged in as {bot.user}  |  Slash commands synced")
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching, name="/lfg"
        )
    )


bot.run(os.getenv("DISCORD_TOKEN"))
