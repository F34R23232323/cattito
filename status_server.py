"""
status_server.py - WebSocket shard status server for Cattito

Reads live shard data directly from the bot (AutoShardedBot.shards)
and broadcasts it to connected status page clients every 200ms.

Also exposes a safe error-tracking API so commands/events/db failures
can be reported and surfaced on the public status page WITHOUT leaking
any sensitive information (no tokens, user IDs, server IDs, stack traces,
or internal paths).

Usage: call start_status_server(bot) from bot.py's setup_hook, e.g.:
    from status_server import start_status_server, track_error
    asyncio.ensure_future(start_status_server(bot))

Reporting errors from main.py / database.py:
    from status_server import track_error
    track_error("command", "catch")          # a command failed
    track_error("db", "Profile.get")         # a DB call failed
    track_error("event", "on_message")       # an event handler failed
"""

import asyncio
import json
import logging
import os
import time
from collections import defaultdict, deque

import websockets

logger = logging.getLogger(__name__)

# Port the WebSocket server listens on (put this behind nginx with wss://)
STATUS_PORT = int(os.environ.get("STATUS_WS_PORT", "8765"))
# How often to push updates to clients (seconds)
UPDATE_INTERVAL = 0.2

# ── Error tracking config ─────────────────────────────────────────────────────
# How long (seconds) to keep error records in the rolling window
ERROR_WINDOW_SECONDS = 3600          # 1 hour shown to users
# How many distinct names to surface per category
TOP_N = 8
# Minimum error count before an item appears on the status page
MIN_COUNT = 1

# ── Internal error store ──────────────────────────────────────────────────────
# Structure: { category: { name: deque([timestamp, ...]) } }
#   category: "command" | "db" | "event"
#   name: safe human-readable label (e.g. "catch", "Profile.save", "on_message")
_error_store: dict[str, dict[str, deque]] = defaultdict(lambda: defaultdict(deque))

# Allowlist of categories — only these are accepted, prevents injection of
# arbitrary category strings from caller mistakes.
_VALID_CATEGORIES = {"command", "db", "event"}

# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def track_error(category: str, name: str) -> None:
    """
    Record one occurrence of an error for the given category and name.

    This is the ONLY information stored — no tracebacks, no IDs, no context.
    Designed to be safe to call from anywhere in main.py / database.py.

    Args:
        category: one of "command", "db", "event"
        name:     a short, fixed label — e.g. "catch", "Profile.save",
                  "on_message". Must not contain user/guild IDs or tokens.
                  Names longer than 64 chars are truncated.
    """
    if category not in _VALID_CATEGORIES:
        logger.debug("track_error: ignored unknown category %r", category)
        return
    # Sanitise name: truncate + strip whitespace; never store raw exception text
    safe_name = str(name).strip()[:64]
    if not safe_name:
        return
    _error_store[category][safe_name].append(time.monotonic())


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _prune_old_errors(cutoff: float) -> None:
    """Drop timestamps older than the rolling window."""
    for cat_data in _error_store.values():
        for dq in cat_data.values():
            while dq and dq[0] < cutoff:
                dq.popleft()


def _build_error_summary() -> dict:
    """
    Return a safe, sanitised summary suitable for public broadcast.

    Output shape:
    {
        "command": [{"name": "catch", "count": 12}, ...],   # top-N by count
        "db":      [{"name": "Profile.save", "count": 3}],
        "event":   [],
        "total":   15,
        "window":  3600
    }
    """
    cutoff = time.monotonic() - ERROR_WINDOW_SECONDS
    _prune_old_errors(cutoff)

    summary: dict = {"window": ERROR_WINDOW_SECONDS, "total": 0}
    grand_total = 0

    for cat in _VALID_CATEGORIES:
        cat_data = _error_store.get(cat, {})
        entries = []
        for name, dq in cat_data.items():
            count = len(dq)
            if count >= MIN_COUNT:
                entries.append({"name": name, "count": count})
                grand_total += count
        # Sort descending by count, take top N
        entries.sort(key=lambda x: x["count"], reverse=True)
        summary[cat] = entries[:TOP_N]

    summary["total"] = grand_total
    return summary


# ─────────────────────────────────────────────────────────────────────────────
# WebSocket broadcast machinery (unchanged from original, extended with errors)
# ─────────────────────────────────────────────────────────────────────────────

connected_clients: set = set()
last_shard_data: dict = {}


async def broadcast(data: dict):
    if not connected_clients:
        return
    payload = json.dumps(data)
    tasks = [client.send(payload) for client in list(connected_clients)]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    for client, result in zip(list(connected_clients), results):
        if isinstance(result, Exception):
            connected_clients.discard(client)


def collect_shard_data(bot) -> dict:
    """
    Build a shard status dict from bot.shards.
    Each shard entry: { ping, guilds, status, change }

    discord.py shard status values map to the status page's colour scheme:
      4 = CONNECTED    -> green
      3 = DISCONNECTED -> black
      2 = LOGGING_IN   -> orange  (discord.py uses CONNECTING)
      1 = RECONNECTING -> blue
      0 = DEAD         -> red
     -1 = UNKNOWN      -> gray
    """
    result = {}
    for shard_id, shard in bot.shards.items():
        raw_latency = shard.latency
        if shard.is_closed():
            status = 3
            ping = last_shard_data.get(shard_id, {}).get("ping", 0)
        elif raw_latency != raw_latency or raw_latency == float("inf"):
            status = 2
            ping = 0
        else:
            status = 4
            ping = round(raw_latency * 1000, 2)

        guilds = sum(1 for g in bot.guilds if g.shard_id == shard_id)

        last = last_shard_data.get(shard_id, {})
        shard_entry = {
            "ping": ping,
            "guilds": guilds,
            "status": status,
            "change": (
                last.get("ping") != ping
                or last.get("guilds") != guilds
                or last.get("status") != status
            ),
        }
        result[shard_id] = shard_entry

    return {k: result[k] for k in sorted(result)}


async def push_loop(bot):
    """Continuously collect shard + error data and broadcast to clients."""
    global last_shard_data
    while True:
        start = time.monotonic()
        try:
            if bot.is_ready():
                shards = collect_shard_data(bot)
                errors = _build_error_summary()
                await broadcast({"shards": shards, "errors": errors})
                last_shard_data = {
                    shard_id: {k: v for k, v in entry.items() if k != "change"}
                    for shard_id, entry in shards.items()
                }
        except Exception:
            logger.exception("Error in status push_loop")
        elapsed = time.monotonic() - start
        await asyncio.sleep(max(0, UPDATE_INTERVAL - elapsed))


async def handle_client(websocket):
    """Handle an incoming WebSocket connection from the status page."""
    connected_clients.add(websocket)
    logger.info(f"Status client connected: {websocket.remote_address}")
    try:
        if last_shard_data:
            # Send current snapshot immediately on connect
            await websocket.send(json.dumps({
                "shards": last_shard_data,
                "errors": _build_error_summary(),
            }))
        async for _ in websocket:
            pass
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        connected_clients.discard(websocket)
        logger.info(f"Status client disconnected: {websocket.remote_address}")


async def start_status_server(bot):
    """Start the WebSocket status server. Call this from setup_hook."""
    asyncio.ensure_future(push_loop(bot))
    server = await websockets.serve(handle_client, "127.0.0.1", STATUS_PORT)
    logger.info(f"✅ Shard status WebSocket server running on port {STATUS_PORT}")
    await server.wait_closed()