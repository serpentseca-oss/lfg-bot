"""
embeds.py — Builds the LFG embed for every phase.

The embed colour + description change based on session["phase"]:
  "lobby"    → blue   — Waiting for racers
  "started"  → green  — Race in progress
  "finished" → grey   — Race ended
"""

import discord
import sessions as sess


# ── Colours ───────────────────────────────────────────────────────────────────
PHASE_COLOUR = {
    "lobby":    0x5865F2,   # Discord blurple
    "started":  0x57F287,   # green
    "finished": 0x747F8D,   # grey
}


def build(session: dict) -> discord.Embed:
    """Return a fully built Embed that reflects the current session state."""
    phase        = session["phase"]
    participants = session["participants"]
    host         = session["host"]
    count        = len(participants)

    # ── Title / description per phase ─────────────────────────────────────────
    if phase == "lobby":
        title       = "🏎️  Racing Master Lobby"
        if count >= sess.MIN_PLAYERS:
            description = f"🟢  **Ready!** ({count}/{sess.MAX_PLAYERS} racers)"
        else:
            needed = sess.MIN_PLAYERS - count
            description = (
                f"🔵  **Waiting…** {count}/{sess.MAX_PLAYERS} racers "
                f"— need {needed} more to unlock Start"
            )
    elif phase == "started":
        title       = "🏎️  Race Started!"
        description = f"🟡  **In progress** — {count} racers on track"
    else:  # finished
        title       = "🏎️  Race Finished"
        description = "⚫  **Finished** — great racing!"

    embed = discord.Embed(
        title       = title,
        description = description,
        colour      = PHASE_COLOUR[phase],
        timestamp   = discord.utils.utcnow(),
    )

    # ── Info fields ───────────────────────────────────────────────────────────
    embed.add_field(name="🏁 Mode",          value=session["mode"],      inline=True)
    embed.add_field(name="🏆 Rank",          value=session["rank"],      inline=True)
    embed.add_field(name="🎮 Playstyle",     value=session["playstyle"], inline=True)

    # ── Participant roster ────────────────────────────────────────────────────
    roster = "\n".join(
        f"{'👑' if m.id == host.id else '✅'}  {m.display_name}"
        for m in participants
    )
    # Show open slots while still in lobby
    if phase == "lobby":
        open_slots = sess.MAX_PLAYERS - count
        if open_slots > 0:
            roster += f"\n{'⬜  *(open)*\n' * open_slots}".rstrip()

    embed.add_field(
        name=f"Racers  ({count}/{sess.MAX_PLAYERS})",
        value=roster or "—",
        inline=False,
    )

    embed.set_thumbnail(url=host.display_avatar.url)
    embed.set_footer(text=f"Host: {host.display_name}  •  Min to start: {sess.MIN_PLAYERS}")
    return embed


def build_panel() -> discord.Embed:
    """Return the static embed for the persistent LFG panel."""
    return discord.Embed(
        title="🏁 Looking for Racers?",
        description=(
            "Create an LFG request and find the perfect racers to hit the track with you! 🏎️\n\n"
            "⚙️ **How It Works**\n"
            "1️⃣ Click the button below\n"
            "2️⃣ Choose your race preferences\n"
            "3️⃣ Your request will be posted in #find-racers — other players can join your lobby!\n\n"
            "🎯 **Find the Right Racers**\n"
            "Use LFG posts to match with players by mode, rank, or playstyle — "
            "perfect for finding racers that fit your pace and style.\n\n"
            "💡 **Quick Tips**\n"
            "Be clear about:\n"
            "• Your rank\n"
            "• Favorite mode\n"
            "• Playstyle (Competitive, Casual, Any)\n"
            "• Any specific requirements or notes\n\n"
            "🏆 The more details you share, the easier it is to find your perfect race crew!"
        ),
        colour=0x5865F2,
    )
