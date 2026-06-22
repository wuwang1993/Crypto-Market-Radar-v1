"""Telegram bot command handlers.

Uses python-telegram-bot v21.x async callback style.
"""

import logging
import time
from typing import Any

from telegram import Update
from telegram.ext import ContextTypes

from src.alerts.dedup import DB_PATH
from src.telegram.formatter import escape_markdown

logger = logging.getLogger(__name__)

_START_TIME: float = time.time()
_TODAY_ALERT_COUNT: int = 0
_WS_STATUS: str = "disconnected"


def get_uptime() -> str:
    delta = int(time.time() - _START_TIME)
    h, rem = divmod(delta, 3600)
    m, s = divmod(rem, 60)
    parts = []
    if h:
        parts.append(f"{h}h")
    if m:
        parts.append(f"{m}m")
    parts.append(f"{s}s")
    return " ".join(parts)


def set_alert_stats(bot: Any, count: int) -> None:
    global _TODAY_ALERT_COUNT
    _TODAY_ALERT_COUNT = count
    if hasattr(bot, 'alert_count'):
        bot.alert_count = count


def set_ws_status(bot: Any, status: str) -> None:
    global _WS_STATUS
    _WS_STATUS = status
    if hasattr(bot, 'ws_connected'):
        bot.ws_connected = (status == "connected")


# ── helpers ──────────────────────────────────────────────────────────

async def _reply(update: Update, text: str) -> None:
    await update.message.reply_text(
        text, parse_mode="MarkdownV2",
        disable_web_page_preview=True,
    )


# ── command handlers ─────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send welcome message."""
    lines = [
        "🤖 *Crypto Market Radar Bot*",
        "",
        "24×7 行情监控 \\| 实时告警 \\| 智能推送",
        "",
        "输入 /help 查看所有命令",
        "输入 /summary 查看当前行情摘要",
    ]
    await _reply(update, "\n".join(lines))


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List available commands."""
    lines = [
        "📋 *可用命令*",
        "",
        "/start — 欢迎消息",
        "/status — 系统运行状态",
        "/summary — 当前行情摘要",
        "/watch — 监控币对列表",
        "/alerts — 最近告警记录",
        "/reload — 热重载配置",
        "/help — 本帮助",
    ]
    await _reply(update, "\n".join(lines))


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Report system runtime status."""
    uptime = get_uptime()
    ws_icon = "🟢" if _WS_STATUS == "connected" else "🔴"
    lines = [
        "📊 *系统状态*",
        "",
        f"运行时长: `{uptime}`",
        f"监控币对: `6`",
        f"今日告警: `{_TODAY_ALERT_COUNT}`",
        f"WS 状态: {ws_icon} `{_WS_STATUS}`",
        f"版本: `1\\.0\\.0`",
    ]
    await _reply(update, "\n".join(lines))


async def cmd_summary(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Return a live summary supplied by the running scheduler."""
    provider = context.application.bot_data.get("summary_provider")
    if provider is None:
        await _reply(update, "📊 *行情摘要*\n\n实时行情尚未就绪，请稍后重试\\.")
        return
    await _reply(update, provider())


async def cmd_watch(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List monitored symbols — placeholder data for phase 1."""
    symbols = [
        ("BTC/USDT", "S", "现货\\+合约"),
        ("ETH/USDT", "S", "现货\\+合约"),
        ("SOL/USDT", "S", "现货\\+合约"),
        ("BNB/USDT", "A", "现货"),
        ("DOGE/USDT", "A", "现货"),
        ("XRP/USDT", "A", "现货"),
    ]
    lines = ["🔍 *监控币对*", ""]
    for sym, level, mkt in symbols:
        lines.append(f"• `{sym}` \\[{level}\\] — {mkt}")
    await _reply(update, "\n".join(lines))


async def cmd_reload(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Trigger config reload signal. Phase 1: acknowledge only."""
    logger.info("Reload requested via TG command")
    # In later phases this will set a reload-requested flag or send a signal.
    await _reply(
        update,
        "🔄 *配置重载已提交*\n\n系统将在下一个检查周期刷新配置\\. 本阶段为骨架实现, 完整逻辑后续接入\\.",
    )


async def cmd_alerts(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Fetch recent alerts from SQLite. Phase 1: placeholder."""
    try:
        import sqlite3
        conn = sqlite3.connect(str(DB_PATH))
        cur = conn.execute(
            "SELECT symbol, alert_type, level, price, triggered_at "
            "FROM alert_log ORDER BY triggered_at DESC LIMIT 10"
        )
        rows = cur.fetchall()
        conn.close()
    except Exception:
        rows = []

    if not rows:
        await _reply(update, "📭 *最近告警*\n\n暂无告警记录\\. 数据库尚未初始化\\.")
        return

    lines = ["📋 *最近告警 \\(最近 10 条\\)*", ""]
    for sym, atype, level, price, ts in rows:
        p_str = f" @ {float(price):.2f}" if price else ""
        lines.append(
            f"• `{escape_markdown(sym)}` \\[{escape_markdown(level)}\\] "
            f"{escape_markdown(atype)}{escape_markdown(p_str)} \\- _{escape_markdown(ts)}_"
        )
    await _reply(update, "\n".join(lines))


# ── wiring ───────────────────────────────────────────────────────────

def setup_commands(app: Any, allowed_chat_id: str) -> None:
    """Register command handlers on a PTB Application instance."""
    app.bot_data["allowed_chat_id"] = str(allowed_chat_id)
    handlers = [
        ("start", cmd_start),
        ("help", cmd_help),
        ("status", cmd_status),
        ("summary", cmd_summary),
        ("watch", cmd_watch),
        ("reload", cmd_reload),
        ("alerts", cmd_alerts),
    ]
    from telegram.ext import CommandHandler
    for cmd_name, handler in handlers:
        async def authorized(update: Update, context: ContextTypes.DEFAULT_TYPE, callback=handler) -> None:
            chat = update.effective_chat
            if chat is None or str(chat.id) != context.application.bot_data["allowed_chat_id"]:
                logger.warning("Ignored unauthorized Telegram command")
                return
            await callback(update, context)

        app.add_handler(CommandHandler(cmd_name, authorized))
    logger.info("Registered %d command handlers", len(handlers))
