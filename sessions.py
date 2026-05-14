"""
sessions.py — Simple in-memory store for LFG sessions.

Each session is a plain Python dict, keyed by the LFG embed message ID.

Session fields:
    host            discord.Member      who created the lobby
    mode            str
    rank            str
    playstyle       str
    participants    list[discord.Member]   always includes host
    phase           str     "lobby" | "started" | "finished"
    thread          discord.Thread | None
    voice           discord.VoiceChannel | None
    created_at      datetime              when lobby was created (for duration stats)

Constants (fixed per spec):
    MIN_PLAYERS = 2
    MAX_PLAYERS = 4
"""

import json
from datetime import datetime

MIN_PLAYERS = 2
MAX_PLAYERS = 4

# message_id (int) → session dict
_store: dict[int, dict] = {}


def create(message_id: int, host, mode: str, rank: str, playstyle: str) -> dict:
    """Create and store a new session. Returns the session dict."""
    session = {
        "host":         host,
        "mode":         mode,
        "rank":         rank,
        "playstyle":    playstyle,
        "participants": [host],
        "phase":        "lobby",
        "thread":       None,
        "voice":        None,
        "created_at":   datetime.now(),          # for duration calculation
    }
    _store[message_id] = session
    return session


def get(message_id: int) -> dict | None:
    """Return the session for this message ID, or None."""
    return _store.get(message_id)


def delete(message_id: int) -> None:
    """Remove a session from memory."""
    _store.pop(message_id, None)


def get_active_by_host(host_id: int) -> dict | None:
    """Return the first active (non-finished) session owned by host_id, or None."""
    for session in _store.values():
        if session["host"].id == host_id and session["phase"] != "finished":
            return session
    return None


# ----------------------------------------------------------------------
# Business event logging (statistics)
# ----------------------------------------------------------------------
def log_event(event_type: str, session_id: int = None,
              user_id: int = None, user_name: str = None,
              extra: dict = None):
    """
    Append one event line to lfg_events.jsonl.
    event_type: create, join, leave, start, finish, close, voice_created, bot_start, bot_stop
    session_id: the message_id of the LFG embed
    extra: any additional fields (e.g. participant_count, mode, duration)
    """
    try:
        record = {
            "timestamp": datetime.now().isoformat(timespec='milliseconds'),
            "event": event_type,
            "session_id": session_id,
        }
        if user_id:
            record["user_id"] = user_id
        if user_name:
            record["user_name"] = user_name
        if extra:
            record.update(extra)

        # Use 'a' to append, one JSON object per line (jsonl format)
        with open("lfg_events.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as e:
        # Don't crash the bot if logging fails
        print(f"[WARN] Failed to log event '{event_type}': {e}")


def log_creation(session: dict, channel_id: int = None, message_id: int = None):
    """Convenience wrapper for 'create' events."""
    extra = {
        "host_id": session["host"].id,
        "host_name": session["host"].name,
        "mode": session["mode"],
        "rank": session["rank"],
        "playstyle": session["playstyle"],
        "min_players": MIN_PLAYERS,
        "max_players": MAX_PLAYERS,
    }
    if channel_id:
        extra["channel_id"] = channel_id
    # session_id is the message_id of the LFG embed
    log_event("create", session_id=message_id, extra=extra)
