# 🏎️ Racing LFG Bot — Full Session Lifecycle

A clean, beginner-friendly Discord LFG bot with a complete session lifecycle:
**Lobby → Started → Finished → Cleanup.**

---

## Project structure

```
lfg_refactor/
├── bot.py          ← entry point
├── sessions.py     ← in-memory store (no database)
├── embeds.py       ← embed builder (one per phase)
├── views.py        ← all Discord UI: dropdowns + buttons
├── cogs/
│   ├── __init__.py
│   └── lfg.py      ← /lfg slash command
├── env.example
└── requirements.txt
```

---

## Session lifecycle

```
/lfg
  └─► Ephemeral dropdown form  (Region · Mode · Playstyle)
        └─► [Create Lobby]
              │
              ▼
         ┌─────────────────────────────┐
         │  PHASE: lobby               │
         │  Embed: blue                │
         │  Buttons: Join · Start · Close │
         └─────────────────────────────┘
              │ players join (min 2)
              │ Start unlocks
              ▼
         ┌─────────────────────────────┐
         │  PHASE: started             │
         │  Embed: green               │
         │  Voice channel created      │
         │  Thread: mentions all + VC  │
         │  Buttons: [Finish]          │
         └─────────────────────────────┘
              │ host clicks Finish
              ▼
         ┌─────────────────────────────┐
         │  PHASE: finished            │
         │  Embed: grey                │
         │  Thread: "session ended"    │
         │  Buttons: all disabled      │
         └─────────────────────────────┘
              │ 5 minutes later
              ▼
         Thread archived + locked
         Session deleted from memory
```

---

## Setup

### 1. Create a Discord bot
1. https://discord.com/developers/applications → **New Application**
2. **Bot** tab → **Add Bot** → copy the **Token**
3. Enable **Privileged Intents**: `Server Members Intent`
4. **OAuth2 → URL Generator**
   - Scopes: `bot`, `applications.commands`
   - Permissions:
     - Send Messages
     - Send Messages in Threads
     - Create Public Threads
     - Manage Threads ← archive/lock on cleanup
     - Embed Links
     - Read Message History
     - **Manage Channels** ← create voice channel on Start

### 2. Get your `#lfg` channel ID
User Settings → Advanced → **Developer Mode** ON
→ right-click `#lfg` → **Copy ID**

### 3. Configure
```bash
cp env.example .env
# Edit .env — fill in DISCORD_TOKEN and LFG_CHANNEL_ID
```

### 4. Run
```bash
pip install -r requirements.txt
python bot.py
```

---

## Customising options

All dropdown lists live at the top of `views.py`:

```python
REGIONS    = ["NA East", "NA West", "EU West", ...]
MODES      = ["Quick Race", "Ranked", ...]
PLAYSTYLES = ["Casual", "Competitive", ...]
```

Player limits are in `sessions.py`:
```python
MIN_PLAYERS = 2   # Start unlocks at this count
MAX_PLAYERS = 4   # Lobby closes to new joins
```

Cleanup delay is in `views.py`:
```python
await asyncio.sleep(300)   # 300 seconds = 5 minutes
```
