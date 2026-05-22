"""
views.py — Discord UI components.

LFGPanelView  — persistent "Create Lobby" button  (always alive)
LFGSetupView  — the /lfg dropdown form
LFGLobbyView  — Join · Start · Close   (phase: lobby)
LFGActiveView — Finish                  (phase: started)
LFGDoneView   — all buttons disabled    (phase: finished)

The active view stores message_id so every button can look up its
session in the in-memory store and refresh the embed.
"""

import asyncio
import os
import discord
from discord import ui
from datetime import datetime, timedelta
import sessions as sess
import embeds

LOBBY_COOLDOWNS = {}


# ── Dropdown options ──────────────────────────────────────────────────────────
MODES = [
    "Ranked Race",
    "Master Series",
    "RM Land",
    "Custom Room",
    "Cruise",
]
RANKS = [
    "Novice",
    "Junior",
    "Intermediate",
    "Proficient",
    "Veteran",
    "Ace",
    "Champion",
    "Racing Master",
]
PLAYSTYLES = [
    "Competitive",
    "Casual",
    "Any",
]


# ─────────────────────────────────────────────────────────────────────────────
# 1.  SETUP VIEW  (ephemeral dropdowns shown to /lfg caller)
# ─────────────────────────────────────────────────────────────────────────────
class LFGSetupView(ui.View):
    """Three dropdowns + a Create button. Entirely ephemeral."""

    def __init__(self, lfg_channel: discord.TextChannel):
        super().__init__(timeout=120)
        self.lfg_channel = lfg_channel

        self.mode      = MODES[0]
        self.rank      = RANKS[0]
        self.playstyle = PLAYSTYLES[0]
        self._dropdowns_used = set()

        self.add_item(_Dropdown("🏁 Game Mode",     MODES,       "mode",      self))
        self.add_item(_Dropdown("🏆 Rank",          RANKS,       "rank",      self))
        self.add_item(_Dropdown("🎮 Playstyle",     PLAYSTYLES,  "playstyle", self))

    def _check_enable_create(self):
        if len(self._dropdowns_used) >= 3:
            for item in self.children:
                if isinstance(item, ui.Button) and item.label == "Create Lobby":
                    item.disabled = False

    def _mark_dropdown_used(self, attr: str):
        self._dropdowns_used.add(attr)
        self._check_enable_create()

    @ui.button(label="Create Lobby", style=discord.ButtonStyle.success,
               emoji="🏎️", row=3, disabled=True)
    async def create(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer(ephemeral=True)

        now = datetime.now()
        last_used = LOBBY_COOLDOWNS.get(interaction.user.id)

        if last_used and (now - last_used) < timedelta(minutes=1):
            await interaction.followup.send(
                "⏳ Please wait before creating another lobby.",
                ephemeral=True,
            )
            return

        LOBBY_COOLDOWNS[interaction.user.id] = now

        if sess.get_active_by_host(interaction.user.id):
            await interaction.followup.send(
                "❌ You already have an active lobby. "
                "Close it before creating a new one.",
                ephemeral=True,
            )
            return

        temp = {
            "host":         interaction.user,
            "mode":         self.mode,
            "rank":         self.rank,
            "playstyle":    self.playstyle,
            "participants": [interaction.user],
            "phase":        "lobby",
            "thread":       None,
            "voice":        None,
        }

        channel_id = int(os.getenv("LFG_CHANNEL_ID"))
        channel = interaction.client.get_channel(channel_id) or interaction.guild.get_channel(channel_id)

        if channel is None:
            await interaction.followup.send(
                "❌ Unable to access the LFG channel (ID not found in cache). "
                "Please verify the bot has permission to view that channel.",
                ephemeral=True,
            )
            return

        try:
            lobby_view = LFGLobbyView(bot=interaction.client)
            message    = await channel.send(
                embed=embeds.build(temp),
                view=lobby_view,
            )

            session = sess.create(
                message_id = message.id,
                host       = interaction.user,
                mode       = self.mode,
                rank       = self.rank,
                playstyle  = self.playstyle,
            )

            # --- Log creation ---
            sess.log_creation(session, channel.id, message.id)

            # Give the view its message ID so buttons can find the session
            lobby_view.message_id = message.id

            # Create thread
            thread = await message.create_thread(
                name                 = f"🏎️ {interaction.user.display_name} • {self.mode}",
                auto_archive_duration= 60,
            )
            session["thread"] = thread

            await thread.send(
                f"👋 {interaction.user.mention} started a Racing Master lobby!\n"
                f"Minimum **{sess.MIN_PLAYERS}** racers needed to unlock Start."
            )

            await interaction.followup.send(
                f"✅ Lobby created in {channel.mention}!",
                ephemeral=True,
            )
        except Exception as e:
            await interaction.followup.send(
                f"❌ Failed to create lobby: {e}",
                ephemeral=True,
            )
            return

        self.stop()

    async def on_timeout(self):
        # Silently expire — user will see the dropdowns stop responding
        self.stop()


class _Dropdown(ui.Select):
    """Generic single-select dropdown that writes its value back to the parent view."""

    def __init__(self, placeholder: str, options: list[str],
                 attr: str, setup_view: LFGSetupView):
        super().__init__(
            placeholder=placeholder,
            options=[discord.SelectOption(label=o, value=o) for o in options],
            min_values=1,
            max_values=1,
        )
        self.attr = attr
        self.setup_view = setup_view   # renamed to avoid property conflict

    async def callback(self, interaction: discord.Interaction):
        selected = self.values[0]

        setattr(self.setup_view, self.attr, selected)

        self.setup_view._mark_dropdown_used(self.attr)

        for option in self.options:
            option.default = (option.value == selected)

        await interaction.response.edit_message(view=self.setup_view)


# ─────────────────────────────────────────────────────────────────────────────
# PANEL VIEW  — persistent entry point for LFG
# ─────────────────────────────────────────────────────────────────────────────
class LFGPanelView(ui.View):
    """A single persistent button that opens the LFGSetupView dropdown UI."""

    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="Create LFG Request", emoji="🏎️",
               style=discord.ButtonStyle.success, custom_id="lfg_panel_create")
    async def create_lobby(self, interaction: discord.Interaction, button: ui.Button):
        channel_id = int(os.getenv("LFG_CHANNEL_ID"))
        channel = interaction.guild.get_channel(channel_id)
        if not isinstance(channel, discord.TextChannel):
            await interaction.response.send_message(
                "❌ LFG channel not configured. "
                "Set `LFG_CHANNEL_ID` in your `.env` file.",
                ephemeral=True,
            )
            return

        view = LFGSetupView(lfg_channel=channel)
        await interaction.response.send_message(
            "### 🏎️  Racing Master Lobby\n"
            "Choose your race preferences and create your lobby.",
            view=view,
            ephemeral=True,
        )


# ─────────────────────────────────────────────────────────────────────────────
# SHARED HELPER
# ─────────────────────────────────────────────────────────────────────────────
async def _refresh_embed(interaction: discord.Interaction,
                         session: dict, new_view: discord.ui.View):
    """Edit the LFG message with a fresh embed + updated view."""
    await interaction.message.edit(embed=embeds.build(session), view=new_view)


# ─────────────────────────────────────────────────────────────────────────────
# 2.  LOBBY VIEW   phase = "lobby"
# ─────────────────────────────────────────────────────────────────────────────
class LFGLobbyView(ui.View):
    """
    Buttons: [Join Lobby]  [Start ▶]  [Close ✖]

    • Join Lobby — toggles join/leave for non-host players
    • Start      — host-only; unlocks when ≥ MIN_PLAYERS joined
    • Close      — host-only; cancels lobby
    """

    def __init__(self, bot=None):
        super().__init__(timeout=1800)
        self.message_id: int | None = None
        self.bot = bot

    # ── helpers ───────────────────────────────────────────────────────────────
    def _update_start_button(self, session: dict):
        count = len(session["participants"])
        for item in self.children:
            if getattr(item, "custom_id", None) == "lfg_start":
                item.disabled = count < sess.MIN_PLAYERS

    async def _get_session(self, interaction: discord.Interaction) -> dict | None:
        s = sess.get(self.message_id)
        if s is None:
            await interaction.response.send_message(
                "❌ Session not found.", ephemeral=True
            )
        return s

    # ── Join Lobby ────────────────────────────────────────────────────────────
    @ui.button(label="Join Lobby", emoji="✅",
               style=discord.ButtonStyle.success, custom_id="lfg_join", row=0)
    async def join(self, interaction: discord.Interaction, button: ui.Button):
        session = await self._get_session(interaction)
        if session is None:
            return

        user = interaction.user

        # Host cannot leave via Join button
        if user.id == session["host"].id:
            await interaction.response.send_message(
                "👑 You're the host — use **Close** to cancel.", ephemeral=True
            )
            return

        if user in session["participants"]:
            # Toggle: leave
            session["participants"].remove(user)
            await interaction.response.defer()
            self._update_start_button(session)
            await _refresh_embed(interaction, session, self)

            # --- log leave ---
            sess.log_event(
                "leave",
                session_id=self.message_id,
                user_id=user.id,
                user_name=user.name,
                extra={"participant_count": len(session["participants"])}
            )

            if session["thread"]:
                await session["thread"].send(f"👋  {user.mention} left the lobby.")
            return

        if len(session["participants"]) >= sess.MAX_PLAYERS:
            await interaction.response.send_message(
                "❌ Lobby is full!", ephemeral=True
            )
            return

        session["participants"].append(user)
        await interaction.response.defer()
        self._update_start_button(session)
        await _refresh_embed(interaction, session, self)

        # --- log join ---
        sess.log_event(
            "join",
            session_id=self.message_id,
            user_id=user.id,
            user_name=user.name,
            extra={"participant_count": len(session["participants"])}
        )

        if session["thread"]:
            await session["thread"].send(f"✅  {user.mention} joined the lobby!")

    # ── Start ─────────────────────────────────────────────────────────────────
    @ui.button(label="Start", emoji="▶️",
               style=discord.ButtonStyle.primary, custom_id="lfg_start",
               disabled=True, row=0)
    async def start(self, interaction: discord.Interaction, button: ui.Button):
        session = await self._get_session(interaction)
        if session is None:
            return

        if interaction.user.id != session["host"].id:
            await interaction.response.send_message(
                "⚠️ Only the **host** can start.", ephemeral=True
            )
            return

        await interaction.response.defer()

        # ── Create voice channel ───────────────────────────────────────────
        guild    = interaction.guild
        category = interaction.channel.category
        vc_name  = f"🏎️ {session['host'].display_name}'s Race"

        try:
            vc = await guild.create_voice_channel(
                name       = vc_name,
                category   = category,
                user_limit = sess.MAX_PLAYERS,
                reason     = "LFG session started",
            )
            session["voice"] = vc
        except discord.Forbidden:
            await interaction.followup.send(
                "⚠️ Missing **Manage Channels** permission — "
                "can't create the voice channel.",
                ephemeral=True,
            )
            return

        # ── Advance phase ──────────────────────────────────────────────────
        session["phase"] = "started"

        # --- log start (and voice creation) ---
        sess.log_event(
            "start",
            session_id=self.message_id,
            user_id=interaction.user.id,
            extra={
                "voice_channel_id": vc.id,
                "participant_count": len(session["participants"])
            }
        )

        # Switch to LFGActiveView (only Finish button)
        active_view             = LFGActiveView()
        active_view.message_id  = self.message_id
        await _refresh_embed(interaction, session, active_view)

        # Notify thread
        if session["thread"]:
            mentions = " ".join(m.mention for m in session["participants"])
            await session["thread"].send(
                f"🚦 **Race Started!**\n"
                f"{mentions}\n\n"
                f"🎙️ Voice channel: {vc.mention}"
            )

        self.stop()

    # ── Close ─────────────────────────────────────────────────────────────────
    @ui.button(label="Close", emoji="✖️",
               style=discord.ButtonStyle.danger, custom_id="lfg_close", row=0)
    async def close(self, interaction: discord.Interaction, button: ui.Button):
        session = await self._get_session(interaction)
        if session is None:
            return

        if interaction.user.id != session["host"].id:
            await interaction.response.send_message(
                "⚠️ Only the **host** can close the lobby.", ephemeral=True
            )
            return

        await interaction.response.defer()

        session["phase"] = "finished"

        # --- log close (include duration if created_at exists) ---
        extra = {"reason": "host_closed"}
        if "created_at" in session:
            duration = (datetime.now() - session["created_at"]).total_seconds()
            extra["duration_seconds"] = round(duration, 1)
        sess.log_event(
            "close",
            session_id=self.message_id,
            user_id=interaction.user.id,
            extra=extra
        )

        # Delete voice channel if it exists
        vc = session.get("voice")
        if vc:
            try:
                await vc.delete(reason="LFG session closed by host")
            except (discord.Forbidden, discord.NotFound):
                pass

        done_view = LFGDoneView()
        await _refresh_embed(interaction, session, done_view)

        if session["thread"]:
            await session["thread"].send(
                "🔒 The host cancelled this lobby.\n"
                "This lobby has ended. Thread will archive automatically in 5 minutes."
            )
            asyncio.create_task(_schedule_cleanup(self.message_id, session))

        sess.delete(self.message_id)
        self.stop()

    async def on_timeout(self):
        session = sess.get(self.message_id)
        if session is None or session["phase"] != "lobby":
            return

        session["phase"] = "finished"

        extra = {"reason": "inactivity_timeout"}
        if "created_at" in session:
            duration = (datetime.now() - session["created_at"]).total_seconds()
            extra["duration_seconds"] = round(duration, 1)
        sess.log_event(
            "timeout",
            session_id=self.message_id,
            extra=extra,
        )

        if self.bot:
            try:
                channel_id = int(os.getenv("LFG_CHANNEL_ID"))
                channel = self.bot.get_channel(channel_id)
                if channel:
                    msg = await channel.fetch_message(self.message_id)
                    await msg.edit(embed=embeds.build(session), view=LFGDoneView())
            except Exception:
                pass

        if session.get("thread"):
            await session["thread"].send(
                "⏰ This lobby has timed out due to inactivity.\n"
                "This lobby has ended. Thread will archive automatically in 5 minutes."
            )
            asyncio.create_task(_schedule_cleanup(self.message_id, session))

        sess.delete(self.message_id)


# ─────────────────────────────────────────────────────────────────────────────
# 3.  ACTIVE VIEW   phase = "started"
# ─────────────────────────────────────────────────────────────────────────────
class LFGActiveView(ui.View):
    """Single Finish button — only visible during an active session."""

    def __init__(self):
        super().__init__(timeout=None)
        self.message_id: int | None = None

    @ui.button(label="Finish", emoji="🏁",
               style=discord.ButtonStyle.danger, custom_id="lfg_finish", row=0)
    async def finish(self, interaction: discord.Interaction, button: ui.Button):
        session = sess.get(self.message_id)
        if session is None:
            await interaction.response.send_message(
                "❌ Session not found.", ephemeral=True
            )
            return

        if interaction.user.id != session["host"].id:
            await interaction.response.send_message(
                "⚠️ Only the **host** can finish the session.", ephemeral=True
            )
            return

        await interaction.response.defer()

        session["phase"] = "finished"

        # --- log finish (include duration) ---
        extra = {}
        if "created_at" in session:
            duration = (datetime.now() - session["created_at"]).total_seconds()
            extra["duration_seconds"] = round(duration, 1)
        sess.log_event(
            "finish",
            session_id=self.message_id,
            user_id=interaction.user.id,
            extra=extra
        )

        # Delete voice channel if it exists
        vc = session.get("voice")
        if vc:
            try:
                await vc.delete(reason="LFG session finished")
            except (discord.Forbidden, discord.NotFound):
                pass

        done_view = LFGDoneView()
        await _refresh_embed(interaction, session, done_view)

        if session["thread"]:
            await session["thread"].send(
                "🏁 **Race Finished!** Great racing everyone.\n\n"
                "This race has ended. "
                "Thread will archive automatically in 5 minutes."
            )
            asyncio.create_task(_schedule_cleanup(self.message_id, session))

        sess.delete(self.message_id)
        self.stop()


# ─────────────────────────────────────────────────────────────────────────────
# 4.  DONE VIEW   phase = "finished"
# ─────────────────────────────────────────────────────────────────────────────
class LFGDoneView(ui.View):
    """All buttons disabled — shown after finish or cancel."""

    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="Session Ended", emoji="🏁",
               style=discord.ButtonStyle.secondary, disabled=True)
    async def ended(self, interaction: discord.Interaction, button: ui.Button):
        pass   # unreachable — button is disabled


# ─────────────────────────────────────────────────────────────────────────────
# CLEANUP HELPER
# ─────────────────────────────────────────────────────────────────────────────
async def _schedule_cleanup(message_id: int, session: dict):
    """Wait 5 minutes then archive + lock the thread."""
    await asyncio.sleep(300)   # 5 minutes

    thread = session.get("thread")
    if thread:
        try:
            await thread.edit(
                archived = True,
                locked   = True,
                reason   = "LFG session ended — auto-cleanup",
            )
        except (discord.Forbidden, discord.HTTPException):
            pass   # thread may already be archived
