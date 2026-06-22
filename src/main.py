"""Crypto Market Radar Bot — entry point.

Phase 2: Exchange adapter + WebSocket connection + warmup flow
with health-check main loop.
"""

import asyncio
import ctypes
import gc
import logging
import sys
import time
from pathlib import Path

from src.telegram.bot import RadarBot
from src.telegram.commands import setup_commands, set_ws_status
from typing import Any
from src.exchange.adapter import ExchangeAdapter, DEFAULT_SYMBOLS
from src.indicators import compute_all
from src.state.engine import evaluate_state
from src.alerts import (
    evaluate_alerts,
    is_in_cooldown,
    record_alert,
    merge_l2_alerts,
)
from src.scheduler import SummaryScheduler
from src.notifier import Notifier

# ── Logging setup ─────────────────────────────────────────────────────

def _setup_logging() -> None:
    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)-7s] %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(fmt)
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(handler)
    # httpx logs Telegram API URLs, which include the bot token.
    logging.getLogger("httpx").setLevel(logging.WARNING)


# ── Helpers ───────────────────────────────────────────────────────────

def _on_ws_connected(bot: Any) -> None:
    set_ws_status(bot, "connected")


def _on_ws_disconnected(bot: Any) -> None:
    set_ws_status(bot, "disconnected")


def _reclaim_memory() -> int:
    """Force gc collect + glibc malloc_trim; returns bytes freed estimate."""
    before = gc.collect()
    try:
        ctypes.CDLL("libc.so.6").malloc_trim(0)
    except Exception:
        pass
    after = gc.collect()
    return before + after


# ── Main ──────────────────────────────────────────────────────────────

async def main() -> None:
    _setup_logging()
    logger = logging.getLogger("main")

    logger.info("Starting Crypto Market Radar Bot v1.0.0")

    # 1. Init Telegram bot
    bot = RadarBot()
    await bot.start()

    # 2. Register command handlers
    setup_commands(bot.app, bot.chat_id)

    # 2.5 Create notifier
    notifier = Notifier(bot.send_message)

    # 3. Send startup notification (with warmup hint)
    await notifier.send_startup(len(DEFAULT_SYMBOLS))
    logger.info("Startup notification sent")

    # 4. Init exchange adapter + scheduler + warmup
    exchange = ExchangeAdapter(symbols=DEFAULT_SYMBOLS)
    scheduler = SummaryScheduler(exchange, notifier, bot)
    bot.app.bot_data["summary_provider"] = scheduler._build_summary
    t0 = time.monotonic()
    logger.info("Starting data warmup for %d symbols...", len(DEFAULT_SYMBOLS))
    await exchange.warmup()
    warmup_sec = time.monotonic() - t0
    logger.info("Warmup complete in %.1fs", warmup_sec)

    # 4.5 Start Telegram polling (deferred to avoid PTB blocking warmup)
    await bot.start_polling()
    logger.info("Telegram polling started")

    # 5. Connect WebSocket
    await exchange.start()
    set_ws_status(bot, "connected")
    logger.info("WebSocket streams active")

    # 6. Send "warmup done" notification
    await notifier.send_warmup_done(len(DEFAULT_SYMBOLS), round(warmup_sec, 1))
    logger.info("Warmup-done notification sent")

    # 6.5 Start scheduler
    await scheduler.start()
    logger.info("Scheduler started")

    # 7. Main loop — alert evaluation + health check every 30s
    stale_threshold = 10  # seconds
    tick = 0
    try:
        while True:
            try:
                await asyncio.sleep(30)
                tick += 1
                # Periodic memory reclaim (every 60 ticks = 30 min)
                if tick % 60 == 0:
                    freed = _reclaim_memory()
                    logger.debug("Memory reclaim: %d objects collected", freed)
                now = time.monotonic()
                # Health: check WS status and update
                if exchange.connected:
                    set_ws_status(bot, "connected")
                elif exchange.fallback_mode:
                    set_ws_status(bot, "fallback")
                else:
                    set_ws_status(bot, "disconnected")
                # Alert evaluation + stale data check
                stale = []
                raw_alerts = []
                for sym, state in exchange.cache.items():
                    if now - state.last_update > stale_threshold:
                        stale.append(sym)
                    snap = compute_all(sym, state)
                    mstate, _confidence = evaluate_state(snap)
                    triggered = evaluate_alerts(snap, mstate)
                    raw_alerts.extend(triggered)
                if stale:
                    logger.warning("Stale data for: %s", stale)
                # Dedup + merge + send
                merged = merge_l2_alerts(raw_alerts)
                for alert in merged:
                    skip_cd = alert.alert_type is None  # merged batch alert — no dedup/record
                    if not skip_cd:
                        if is_in_cooldown(alert.symbol, alert.alert_type, alert.cooldown_seconds):
                            continue
                    try:
                        await notifier.send_alert(alert)
                        if not skip_cd:
                            record_alert(alert)
                            scheduler.record_alert(alert.symbol)
                    except Exception:
                        logger.exception("Failed to send alert message")
                logger.info("Main loop tick — %d symbols, %d alerts in this batch", len(DEFAULT_SYMBOLS), len(merged))
            except Exception as e:
                logger.exception("Main loop fatal error")
                await notifier.send_system_error("SYSTEM", str(e))
                continue
    except asyncio.CancelledError:
        logger.info("Main loop cancelled")
    finally:
        await scheduler.stop()
        await exchange.stop()
        await bot.stop()
        logger.info("Shutdown complete")


if __name__ == "__main__":
    asyncio.run(main())
