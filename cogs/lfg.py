"""
cogs/lfg.py — Registers the /lfg slash command.
"""

import discord
from discord import app_commands
from discord.ext import commands
import os

from views import LFGSetupView, LFGPanelView
import embeds

LFG_CHANNEL_ID = int(os.getenv("LFG_CHANNEL_ID", "0"))


class LFGCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="lfg", description="Open the LFG lobby setup form")
    @app_commands.guild_only()
    async def lfg(self, interaction: discord.Interaction):
        # Resolve the #lfg channel
        channel = interaction.guild.get_channel(LFG_CHANNEL_ID)
        if not isinstance(channel, discord.TextChannel):
            await interaction.response.send_message(
                "❌ LFG channel not configured. "
                "Set `LFG_CHANNEL_ID` in your `.env` file.",
                ephemeral=True,
            )
            return

        # Send the ephemeral dropdown form
        view = LFGSetupView(lfg_channel=channel)
        await interaction.response.send_message(
            "### 🏎️  Racing Master Lobby\n"
            "Choose your race preferences and create your lobby.",
            view=view,
            ephemeral=True,
        )

    @app_commands.command(name="setup_lfg_panel", description="Send the persistent LFG panel to this channel")
    @app_commands.default_permissions(administrator=True)
    @app_commands.guild_only()
    async def setup_lfg_panel(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "❌ This command is restricted to server administrators.",
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            embed=embeds.build_panel(),
            view=LFGPanelView(),
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(LFGCog(bot))
