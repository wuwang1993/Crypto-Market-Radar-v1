"""Telegram MarkdownV2 templates for market alerts."""

from src.alerts.engine import AlertEvent, AlertLevel, AlertType
from src.indicators import IndicatorSnapshot
from src.telegram.formatter import escape_markdown


ICONS: dict[AlertLevel, str] = {
    AlertLevel.L1: "ℹ️",
    AlertLevel.L2: "🔔",
    AlertLevel.L3: "⚠️",
    AlertLevel.L4: "🚨",
}

TYPE_ICONS: dict[AlertType, str] = {
    AlertType.FAST_UP: "🚀",
    AlertType.FAST_DOWN: "🔻",
    AlertType.BUY_PRESSURE: "🟢",
    AlertType.SELL_PRESSURE: "🔴",
    AlertType.BREAKOUT_UP: "📈",
    AlertType.BREAKDOWN: "📉",
    AlertType.DIVERGENCE_UP: "⚠️",
    AlertType.DIVERGENCE_DOWN: "⚠️",
    AlertType.LONG_CROWDED: "⚠️",
    AlertType.SHORT_CROWDED: "⚠️",
    AlertType.LONG_LIQUIDATION: "💥",
    AlertType.SHORT_LIQUIDATION: "💥",
    AlertType.ABNORMAL: "🚨",
    AlertType.SYSTEM_ERROR: "⚠️",
}

LABELS: dict[AlertType, str] = {
    AlertType.FAST_UP: "快速上涨提醒",
    AlertType.FAST_DOWN: "快速下跌提醒",
    AlertType.BUY_PRESSURE: "买盘增强",
    AlertType.SELL_PRESSURE: "卖盘增强",
    AlertType.BREAKOUT_UP: "放量突破",
    AlertType.BREAKDOWN: "放量下破",
    AlertType.DIVERGENCE_UP: "上涨背离",
    AlertType.DIVERGENCE_DOWN: "下跌背离",
    AlertType.LONG_CROWDED: "合约多头拥挤",
    AlertType.SHORT_CROWDED: "合约空头拥挤",
    AlertType.LONG_LIQUIDATION: "多单集中强平",
    AlertType.SHORT_LIQUIDATION: "空单集中强平",
    AlertType.ABNORMAL: "异常波动",
    AlertType.SYSTEM_ERROR: "系统异常提醒",
}

JUDGMENTS: dict[AlertType, str] = {
    AlertType.FAST_UP: "短线买盘明显增强，当前走势偏强。",
    AlertType.FAST_DOWN: "主动卖出明显增强，短线卖压较重。",
    AlertType.BUY_PRESSURE: "短线买盘增强，可能进入上涨观察区。",
    AlertType.SELL_PRESSURE: "主动卖出增强，短线走势偏弱。",
    AlertType.BREAKOUT_UP: "突破有效性较强，但短线追高风险存在。",
    AlertType.BREAKDOWN: "下跌趋势加强，短线风险较高。",
    AlertType.DIVERGENCE_UP: "价格上涨但主动买盘没有跟上，可能是假拉或空头平仓推动。",
    AlertType.DIVERGENCE_DOWN: "价格下跌但主动买入增加，可能有资金承接。",
    AlertType.LONG_CROWDED: "多头情绪偏热，追多风险升高。",
    AlertType.SHORT_CROWDED: "空头情绪偏热，追空风险升高。",
    AlertType.LONG_LIQUIDATION: "多单强平明显占优，短线可能处于下跌踩踏阶段。",
    AlertType.SHORT_LIQUIDATION: "空单强平明显占优，短线可能处于上涨挤空阶段。",
    AlertType.ABNORMAL: "市场波动异常，常规指标的可靠性可能下降。",
    AlertType.SYSTEM_ERROR: "系统运行出现异常，部分监控能力可能受到影响。",
}

ACTIONS: dict[AlertType, str] = {
    AlertType.FAST_UP: "不建议直接追高，等待回调 VWAP / EMA20 后观察。",
    AlertType.FAST_DOWN: "不要盲目接刀，等待卖压减弱。",
    AlertType.BUY_PRESSURE: "加入观察，不追高，等待回调确认。",
    AlertType.SELL_PRESSURE: "不建议追多，已有仓位注意风险控制。",
    AlertType.BREAKOUT_UP: "等待回踩确认，不建议市价追单。",
    AlertType.BREAKDOWN: "禁止盲目抄底，等待止跌结构。",
    AlertType.DIVERGENCE_UP: "谨慎追多，等待成交量和 CVD 确认。",
    AlertType.DIVERGENCE_DOWN: "观察是否出现止跌结构，避免过早入场。",
    AlertType.LONG_CROWDED: "不建议高位加杠杆追多。",
    AlertType.SHORT_CROWDED: "不建议低位加杠杆追空。",
    AlertType.LONG_LIQUIDATION: "避免盲目接刀，等待强平规模和卖压回落。",
    AlertType.SHORT_LIQUIDATION: "避免追高，等待挤空减弱和价格回踩确认。",
    AlertType.ABNORMAL: "降低仓位与杠杆，等待波动恢复正常。",
    AlertType.SYSTEM_ERROR: "系统正在继续运行并等待自动恢复，请关注后续状态。",
}


def _price(value: float) -> str:
    if value >= 100:
        return f"{value:,.2f}"
    if value >= 1:
        return f"{value:,.4f}".rstrip("0").rstrip(".")
    return f"{value:.8f}".rstrip("0").rstrip(".")


def _pct(value: float) -> str:
    return f"{value:+.2f}%"


def _money(value: float) -> str:
    if value >= 1_000_000:
        return f"${value / 1_000_000:.2f}M"
    if value >= 1_000:
        return f"${value / 1_000:.1f}K"
    return f"${value:.0f}"


def _cvd_label(direction: str) -> str:
    return {"up": "持续上升", "down": "持续下降", "flat": "基本持平"}.get(
        direction, direction or "未知"
    )


def _depth_label(ratio: float) -> str:
    if ratio > 2.0:
        return "买盘挂单很强"
    if ratio > 1.3:
        return "买盘较强"
    if ratio >= 0.8:
        return "盘口均衡"
    if ratio >= 0.5:
        return "卖压较强"
    return "卖压很强"


def _line(label: str, value: str) -> str:
    return escape_markdown(f"{label}：{value}")


def _snapshot_lines(event: AlertEvent, snap: IndicatorSnapshot) -> list[str]:
    atype = event.alert_type
    lines: list[str] = []

    if atype in (AlertType.FAST_UP, AlertType.FAST_DOWN):
        if snap.ret_5m is not None:
            lines.append(_line("5m涨跌", _pct(snap.ret_5m)))
        if snap.ret_15m is not None:
            lines.append(_line("15m涨跌", _pct(snap.ret_15m)))
        if snap.volume_amplify is not None:
            lines.append(_line("成交量", f"放大 {snap.volume_amplify:.1f} 倍"))
        lines.append(_line("买卖量比", f"{snap.buy_sell_ratio:.2f}"))
        lines.append(_line("CVD", _cvd_label(snap.cvd_direction)))
        if snap.depth_ratio is not None:
            lines.append(_line("盘口", _depth_label(snap.depth_ratio)))

    elif atype in (AlertType.BUY_PRESSURE, AlertType.SELL_PRESSURE):
        lines.extend([
            _line("主动买入量", f"{snap.buy_volume:,.4f}"),
            _line("主动卖出量", f"{snap.sell_volume:,.4f}"),
            _line("买卖量比", f"{snap.buy_sell_ratio:.2f}"),
            _line("CVD", _cvd_label(snap.cvd_direction)),
        ])
        if snap.vwap is not None:
            position = "站上 VWAP" if snap.price >= snap.vwap else "跌破 VWAP"
            lines.append(_line("价格位置", position))
        if snap.volume_amplify is not None:
            lines.append(_line("成交量", f"放大 {snap.volume_amplify:.1f} 倍"))

    elif atype in (AlertType.BREAKOUT_UP, AlertType.BREAKDOWN):
        position = "最近 20 根 5m K线高点" if atype == AlertType.BREAKOUT_UP else "最近 20 根 5m K线低点"
        lines.append(_line("突破位置" if atype == AlertType.BREAKOUT_UP else "跌破位置", position))
        if snap.volume_amplify is not None:
            lines.append(_line("成交量", f"放大 {snap.volume_amplify:.1f} 倍"))
        lines.extend([
            _line("买卖量比", f"{snap.buy_sell_ratio:.2f}"),
            _line("CVD", _cvd_label(snap.cvd_direction)),
        ])

    elif atype in (AlertType.DIVERGENCE_UP, AlertType.DIVERGENCE_DOWN):
        if snap.ret_5m is not None:
            lines.append(_line("价格变化", f"5m {_pct(snap.ret_5m)}"))
        lines.extend([
            _line("CVD", _cvd_label(snap.cvd_direction)),
            _line("买卖量比", f"{snap.buy_sell_ratio:.2f}"),
        ])

    elif atype in (AlertType.LONG_CROWDED, AlertType.SHORT_CROWDED):
        if snap.funding_rate is not None:
            lines.append(_line("当前资金费率", f"{snap.funding_rate * 100:+.3f}%"))
        if snap.oi is not None:
            lines.append(_line("当前 OI", f"{snap.oi:,.2f}"))
        if snap.oi_change_5m is not None:
            lines.append(_line("5m OI变化", _pct(snap.oi_change_5m)))
        if snap.oi_change_15m is not None:
            lines.append(_line("15m OI变化", _pct(snap.oi_change_15m)))
        if snap.oi_change_1h is not None:
            lines.append(_line("1h OI变化", _pct(snap.oi_change_1h)))
        if snap.ret_15m is not None:
            lines.append(_line("15m涨跌", _pct(snap.ret_15m)))
        lines.extend([
            _line("15m已观测多单强平", _money(snap.liquidation_long_15m)),
            _line("15m已观测空单强平", _money(snap.liquidation_short_15m)),
        ])

    elif atype in (AlertType.LONG_LIQUIDATION, AlertType.SHORT_LIQUIDATION):
        if snap.ret_5m is not None:
            lines.append(_line("5m涨跌", _pct(snap.ret_5m)))
        if snap.ret_15m is not None:
            lines.append(_line("15m涨跌", _pct(snap.ret_15m)))
        if snap.oi_change_15m is not None:
            lines.append(_line("15m OI变化", _pct(snap.oi_change_15m)))
        lines.extend([
            _line("5m已观测多单强平", _money(snap.liquidation_long_5m)),
            _line("5m已观测空单强平", _money(snap.liquidation_short_5m)),
            _line("15m已观测多单强平", _money(snap.liquidation_long_15m)),
            _line("15m已观测空单强平", _money(snap.liquidation_short_15m)),
            _line("1h已观测多单强平", _money(snap.liquidation_long_1h)),
            _line("1h已观测空单强平", _money(snap.liquidation_short_1h)),
        ])

    else:
        if snap.ret_5m is not None:
            lines.append(_line("5m涨跌", _pct(snap.ret_5m)))
        if snap.volume_amplify is not None:
            lines.append(_line("成交量", f"放大 {snap.volume_amplify:.1f} 倍"))

    lines.append(_line("状态", event.market_state.value))
    return lines


def format_alert(event: AlertEvent) -> str:
    """Build an evidence-rich Telegram alert without inventing unavailable data."""
    atype = event.alert_type
    label = LABELS.get(atype, "多币对异动") if atype else "多币对异动"
    icon = TYPE_ICONS.get(atype, ICONS.get(event.level, "")) if atype else ICONS.get(event.level, "")
    lines = [f"{icon} *{escape_markdown(label)}*", ""]

    if event.symbol and event.symbol != "MULTI" and atype != AlertType.SYSTEM_ERROR:
        lines.append(_line("币对", event.symbol))
    if event.price > 0:
        lines.append(_line("价格", _price(event.price)))
    if event.snapshot is not None:
        lines.extend(_snapshot_lines(event, event.snapshot))
    elif event.message:
        lines.append(escape_markdown(event.message))

    if atype in JUDGMENTS:
        lines.extend(["", "*系统判断*", escape_markdown(JUDGMENTS[atype])])
    if atype in ACTIONS:
        lines.extend(["", "*操作提示*", escape_markdown(ACTIONS[atype])])
    return "\n".join(lines)
