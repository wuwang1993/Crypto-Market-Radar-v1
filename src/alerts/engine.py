"""Alert engine — market and derivatives alert checkers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Callable, List, Optional

from src.indicators import IndicatorSnapshot, get_indicator_value
from src.state.state_types import MarketState


# ── Types ────────────────────────────────────────────────────────────────

class AlertLevel(Enum):
    L1 = "普通提醒"
    L2 = "重要提醒"
    L3 = "风险提醒"
    L4 = "紧急提醒"


class AlertType(Enum):
    FAST_UP = "fast_up"
    FAST_DOWN = "fast_down"
    BUY_PRESSURE = "buy_pressure"
    SELL_PRESSURE = "sell_pressure"
    BREAKOUT_UP = "breakout_up"
    BREAKDOWN = "breakdown"
    DIVERGENCE_UP = "divergence_up"
    DIVERGENCE_DOWN = "divergence_down"
    LONG_CROWDED = "long_crowded"
    SHORT_CROWDED = "short_crowded"
    LONG_LIQUIDATION = "long_liquidation"
    SHORT_LIQUIDATION = "short_liquidation"
    ABNORMAL = "abnormal"
    SYSTEM_ERROR = "system_error"


@dataclass
class AlertEvent:
    symbol: str
    alert_type: AlertType
    level: AlertLevel
    price: float = 0.0
    message: str = ""
    cooldown_seconds: int = 300
    snapshot: Optional[IndicatorSnapshot] = None
    market_state: MarketState = MarketState.NORMAL


# ── Cooldowns ────────────────────────────────────────────────────────────

COOLDOWNS: dict[AlertType, int] = {
    AlertType.FAST_UP: 300,
    AlertType.FAST_DOWN: 300,
    AlertType.BUY_PRESSURE: 600,
    AlertType.SELL_PRESSURE: 600,
    AlertType.BREAKOUT_UP: 900,
    AlertType.BREAKDOWN: 900,
    AlertType.DIVERGENCE_UP: 600,
    AlertType.DIVERGENCE_DOWN: 600,
    AlertType.LONG_CROWDED: 900,
    AlertType.SHORT_CROWDED: 900,
    AlertType.LONG_LIQUIDATION: 600,
    AlertType.SHORT_LIQUIDATION: 600,
    AlertType.ABNORMAL: 600,
    AlertType.SYSTEM_ERROR: 300,
}

# AlertType → AlertLevel mapping
ALERT_LEVELS: dict[AlertType, AlertLevel] = {
    AlertType.FAST_UP: AlertLevel.L2,
    AlertType.FAST_DOWN: AlertLevel.L2,
    AlertType.BUY_PRESSURE: AlertLevel.L2,
    AlertType.SELL_PRESSURE: AlertLevel.L2,
    AlertType.BREAKOUT_UP: AlertLevel.L2,
    AlertType.BREAKDOWN: AlertLevel.L2,
    AlertType.DIVERGENCE_UP: AlertLevel.L3,
    AlertType.DIVERGENCE_DOWN: AlertLevel.L3,
    AlertType.LONG_CROWDED: AlertLevel.L3,
    AlertType.SHORT_CROWDED: AlertLevel.L3,
    AlertType.LONG_LIQUIDATION: AlertLevel.L3,
    AlertType.SHORT_LIQUIDATION: AlertLevel.L3,
    AlertType.ABNORMAL: AlertLevel.L3,
    AlertType.SYSTEM_ERROR: AlertLevel.L4,
}


# ── Helper ───────────────────────────────────────────────────────────────

def _price(snap: IndicatorSnapshot) -> Optional[float]:
    """Best-effort price: raw price attr > VWAP fallback."""
    p = get_indicator_value(snap, "price", None)
    return float(p) if p is not None and p > 0 else snap.vwap


def _make_event(
    snap: IndicatorSnapshot,
    atype: AlertType,
    msg: str = "",
    market_state: MarketState = MarketState.NORMAL,
) -> Optional[AlertEvent]:
    """Build AlertEvent with cooldown from lookup table."""
    level = ALERT_LEVELS.get(atype, AlertLevel.L2)
    price = _price(snap) or 0.0
    return AlertEvent(
        symbol=snap.symbol,
        alert_type=atype,
        level=level,
        price=price,
        message=msg,
        cooldown_seconds=COOLDOWNS.get(atype, 300),
        snapshot=snap,
        market_state=market_state,
    )


# ── Alert Checkers ──────────────────────────────────────────────────────

def _check_fast_up(snap: IndicatorSnapshot, _state: MarketState, _p: float) -> Optional[AlertEvent]:
    if (
        snap.ret_5m is not None and snap.ret_5m > 1.0
        and snap.volume_amplify is not None and snap.volume_amplify > 1.5
        and snap.buy_sell_ratio > 1.3
    ):
        return _make_event(snap, AlertType.FAST_UP,
                           f"5min 涨幅 {snap.ret_5m:.1f}% 量比 {snap.volume_amplify:.1f}", _state)
    return None


def _check_fast_down(snap: IndicatorSnapshot, _state: MarketState, _p: float) -> Optional[AlertEvent]:
    if (
        snap.ret_5m is not None and snap.ret_5m < -1.0
        and snap.volume_amplify is not None and snap.volume_amplify > 1.5
        and snap.buy_sell_ratio < 0.7
    ):
        return _make_event(snap, AlertType.FAST_DOWN,
                           f"5min 跌幅 {snap.ret_5m:.1f}% 量比 {snap.volume_amplify:.1f}", _state)
    return None


def _check_buy_pressure(snap: IndicatorSnapshot, _state: MarketState, price: float) -> Optional[AlertEvent]:
    if (
        snap.buy_sell_ratio > 1.8
        and snap.cvd_direction == "up"
        and snap.vwap is not None and price is not None and price > snap.vwap
    ):
        return _make_event(snap, AlertType.BUY_PRESSURE,
                           f"买卖比 {snap.buy_sell_ratio:.2f} CVD↑ 价高于VWAP", _state)
    return None


def _check_sell_pressure(snap: IndicatorSnapshot, _state: MarketState, price: float) -> Optional[AlertEvent]:
    if (
        snap.buy_sell_ratio < 0.6
        and snap.cvd_direction == "down"
        and snap.vwap is not None and price is not None and price < snap.vwap
    ):
        return _make_event(snap, AlertType.SELL_PRESSURE,
                           f"买卖比 {snap.buy_sell_ratio:.2f} CVD↓ 价低于VWAP", _state)
    return None


def _check_breakout_up(snap: IndicatorSnapshot, state: MarketState, _p: float) -> Optional[AlertEvent]:
    if state == MarketState.BREAKOUT_UP:
        return _make_event(snap, AlertType.BREAKOUT_UP, "放量突破上轨", state)
    return None


def _check_breakdown(snap: IndicatorSnapshot, state: MarketState, _p: float) -> Optional[AlertEvent]:
    if state == MarketState.BREAKDOWN:
        return _make_event(snap, AlertType.BREAKDOWN, "放量下破支撑", state)
    return None


def _check_divergence_up(snap: IndicatorSnapshot, _state: MarketState, _p: float) -> Optional[AlertEvent]:
    if (
        snap.ret_5m is not None and snap.ret_5m > 0.5
        and snap.cvd_direction == "down"
        and snap.buy_sell_ratio < 1.0
    ):
        return _make_event(snap, AlertType.DIVERGENCE_UP,
                           f"价格涨 {snap.ret_5m:.1f}% 但CVD↓ 买卖比 {snap.buy_sell_ratio:.2f}", _state)
    return None


def _check_divergence_down(snap: IndicatorSnapshot, _state: MarketState, _p: float) -> Optional[AlertEvent]:
    if (
        snap.ret_5m is not None and snap.ret_5m < -0.5
        and snap.cvd_direction == "up"
        and snap.buy_sell_ratio > 1.2
    ):
        return _make_event(snap, AlertType.DIVERGENCE_DOWN,
                           f"价格跌 {snap.ret_5m:.1f}% 但CVD↑ 买卖比 {snap.buy_sell_ratio:.2f}", _state)
    return None


def _check_long_crowded(snap: IndicatorSnapshot, state: MarketState, _p: float) -> Optional[AlertEvent]:
    if (
        snap.funding_rate is not None and snap.funding_rate > 0.0008
        and snap.oi_change_15m is not None and snap.oi_change_15m > 5.0
        and snap.ret_15m is not None and snap.ret_15m > 1.0
        and state in (MarketState.STRONG_UP, MarketState.BREAKOUT_UP)
    ):
        return _make_event(snap, AlertType.LONG_CROWDED,
                           f"资金费率 {snap.funding_rate*100:.2f}% 多头拥挤", state)
    return None


def _check_short_crowded(snap: IndicatorSnapshot, state: MarketState, _p: float) -> Optional[AlertEvent]:
    if (
        snap.funding_rate is not None and snap.funding_rate < -0.0005
        and snap.oi_change_15m is not None and snap.oi_change_15m > 5.0
        and snap.ret_15m is not None and snap.ret_15m < -1.0
        and state in (MarketState.STRONG_DOWN, MarketState.BREAKDOWN)
    ):
        return _make_event(snap, AlertType.SHORT_CROWDED,
                           f"资金费率 {snap.funding_rate*100:.2f}% 空头拥挤", state)
    return None


def _check_long_liquidation(snap: IndicatorSnapshot, state: MarketState, _p: float) -> Optional[AlertEvent]:
    observed = snap.liquidation_long_5m
    opposite = snap.liquidation_short_5m
    if observed >= 500_000 and observed >= max(opposite * 2, 1):
        return _make_event(
            snap,
            AlertType.LONG_LIQUIDATION,
            f"5m 已观测多单强平 ${observed:,.0f}",
            state,
        )
    return None


def _check_short_liquidation(snap: IndicatorSnapshot, state: MarketState, _p: float) -> Optional[AlertEvent]:
    observed = snap.liquidation_short_5m
    opposite = snap.liquidation_long_5m
    if observed >= 500_000 and observed >= max(opposite * 2, 1):
        return _make_event(
            snap,
            AlertType.SHORT_LIQUIDATION,
            f"5m 已观测空单强平 ${observed:,.0f}",
            state,
        )
    return None


def _check_abnormal(snap: IndicatorSnapshot, state: MarketState, _p: float) -> Optional[AlertEvent]:
    if state == MarketState.ABNORMAL:
        return _make_event(snap, AlertType.ABNORMAL, "异常波动 请关注", state)
    return None


# ── Checker registry ─────────────────────────────────────────────────────

# Ordered list: each called per symbol per tick
_ALERT_CHECKERS: List[Callable] = [
    _check_fast_up,
    _check_fast_down,
    _check_buy_pressure,
    _check_sell_pressure,
    _check_breakout_up,
    _check_breakdown,
    _check_divergence_up,
    _check_divergence_down,
    _check_long_crowded,
    _check_short_crowded,
    _check_long_liquidation,
    _check_short_liquidation,
    _check_abnormal,
]


# ── Public API ───────────────────────────────────────────────────────────

def evaluate_alerts(
    snap: IndicatorSnapshot,
    state: MarketState,
    price: float = 0.0,
) -> List[AlertEvent]:
    """Run all 11 indicator-based alert checkers.

    Returns list of triggered AlertEvent (may be empty).
    """
    p = price if price > 0 else _price(snap)
    alerts: List[AlertEvent] = []
    for checker in _ALERT_CHECKERS:
        result = checker(snap, state, p)
        if result is not None:
            alerts.append(result)
    return alerts


def system_error_alert(symbol: str, reason: str) -> AlertEvent:
    """Generate a L4 system_error alert (triggered externally)."""
    return AlertEvent(
        symbol=symbol,
        alert_type=AlertType.SYSTEM_ERROR,
        level=AlertLevel.L4,
        price=0.0,
        message=(
            f"问题：{reason}\n"
            f"影响：{symbol} 相关监控可能暂时受影响\n"
            "处理：主循环保持运行并等待自动恢复\n"
            f"时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        ),
        cooldown_seconds=300,
    )
