"""Message formatting utilities for Telegram MarkdownV2-style output.

python-telegram-bot uses Telegram's native Markdown mode.  We escape
special characters so that dynamic data (symbols, prices) never break
the parse.
"""

import re

_MD_SPECIAL = re.compile(r"([_*\[\]()~`>#+\-=|{}.!\\])")


def escape_markdown(text: str) -> str:
    """Escape Telegram Markdown special characters."""
    return _MD_SPECIAL.sub(r"\\\1", str(text))


def format_price(price: float, decimals: int = 2) -> str:
    """Format a price with the given number of decimal places.

    >>> format_price(104200.5, 2)
    '104,200.50'
    """
    fmt = f"{{:,.{decimals}f}}"
    return fmt.format(price)


def format_pct(value: float) -> str:
    """Format a percentage change with explicit sign.

    >>> format_pct(0.42)
    '+0.42%'
    >>> format_pct(-0.86)
    '-0.86%'
    """
    sign = "+" if value >= 0 else ""
    return f"{sign}{value:.2f}%"


def startup_message(
    exchange: str = "Binance",
    symbols: str = "BTC/USDT、ETH/USDT、SOL/USDT、BNB/USDT、DOGE/USDT、XRP/USDT",
    summary_interval_min: int = 15,
    version: str = "1.0.0",
) -> str:
    """Build the launch notification message."""
    lines = [
        "✅ *Crypto Market Radar Bot 已启动*",
        "",
        f"交易所: `{escape_markdown(exchange)}`",
        f"监控币对: `{escape_markdown(symbols)}`",
        f"定时摘要: `{summary_interval_min}` 分钟一次",
        "告警状态: *已启用*",
        f"系统版本: `v{escape_markdown(version)}`",
        "",
        "⏳ 数据预热中, 预计 30 秒后开始告警监控\\.\\.\\.",
    ]
    return "\n".join(lines)


def warmup_done_message(
    symbol_count: int = 6,
    warmup_seconds: float = 0.0,
) -> str:
    """Build the 'warmup complete' notification."""
    lines = [
        "✅ *数据预热完成*",
        "",
        f"已加载 `{symbol_count}` 个币对的历史 K 线数据",
    ]
    if warmup_seconds > 0:
        lines.append(f"预热耗时: `{warmup_seconds:.1f}s`")
    lines += [
        "",
        "🟢 告警监控已启用, 将开始实时盯盘\\.",
    ]
    return "\n".join(lines)
