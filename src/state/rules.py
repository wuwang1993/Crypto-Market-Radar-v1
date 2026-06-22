"""State scoring — one func per state. Returns (core_hits, core_total, aux_hits, aux_total)."""

from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from src.indicators import IndicatorSnapshot

from src.indicators import get_indicator_value


def _p(snap) -> float | None:
    """Best price proxy: raw price > VWAP."""
    p = get_indicator_value(snap, "price", None)
    return float(p) if p is not None and p > 0 else snap.vwap


def _score_strong_up(snap) -> tuple[int, int, int, int]:
    p = _p(snap)
    core = [(snap.ret_5m or 0) > 0.5, (snap.volume_amplify or 0) > 1.5, snap.buy_sell_ratio > 1.2]
    aux = [(snap.ret_15m or 0) > 0.5, snap.cvd_direction == "up",
           p is not None and snap.vwap is not None and p > snap.vwap,
           p is not None and snap.ema20 is not None and p > snap.ema20]
    return sum(core), len(core), sum(aux), len(aux)


def _score_weak_up(snap) -> tuple[int, int, int, int]:
    p = _p(snap)
    core = [(snap.ret_5m or 0) > 0.1, (snap.volume_amplify or 0) > 1.0, snap.buy_sell_ratio > 1.0]
    aux = [(snap.ret_1m or 0) > 0, (snap.ret_15m or 0) > 0.1,
           p is not None and snap.vwap is not None and p > snap.vwap]
    return sum(core), len(core), sum(aux), len(aux)


def _score_range_bias_up(snap) -> tuple[int, int, int, int]:
    r, va, p = snap.ret_15m or 0, snap.volume_amplify or 0, _p(snap)
    core = [-0.3 <= r <= 1.0, 0.7 <= va <= 1.5, 0.8 <= snap.buy_sell_ratio <= 1.3]
    aux = []
    if snap.vwap is not None and p is not None:
        aux.append(p > snap.vwap)
    if snap.ema20 is not None and snap.ema60 is not None:
        aux.append(snap.ema20 > snap.ema60)
    if snap.rsi14 is not None:
        aux.append(snap.rsi14 > 50)
    return sum(core), len(core), sum(aux), max(len(aux), 1)


def _score_range(snap) -> tuple[int, int, int, int]:
    va = snap.volume_amplify or 0
    core = [abs(snap.ret_5m or 0) < 0.3, 0.5 <= va <= 1.5, 0.7 <= snap.buy_sell_ratio <= 1.4]
    aux = [abs(snap.ret_1m or 0) < 0.2]
    v = snap.vol_5m_current
    aux.append(abs(snap.cvd_1m) / v < 0.3 if v > 0 else False)
    if snap.rsi14 is not None:
        aux.append(40 <= snap.rsi14 <= 60)
    return sum(core), len(core), sum(aux), len(aux)


def _score_range_bias_down(snap) -> tuple[int, int, int, int]:
    r, va, p = snap.ret_15m or 0, snap.volume_amplify or 0, _p(snap)
    core = [-1.0 <= r <= 0.3, 0.7 <= va <= 1.5, 0.7 <= snap.buy_sell_ratio <= 1.2]
    aux = []
    if snap.vwap is not None and p is not None:
        aux.append(p < snap.vwap)
    if snap.ema20 is not None and snap.ema60 is not None:
        aux.append(snap.ema20 < snap.ema60)
    if snap.rsi14 is not None:
        aux.append(snap.rsi14 < 50)
    return sum(core), len(core), sum(aux), max(len(aux), 1)


def _score_weak_down(snap) -> tuple[int, int, int, int]:
    p = _p(snap)
    core = [(snap.ret_5m or 0) < -0.1, (snap.volume_amplify or 0) > 1.0, snap.buy_sell_ratio < 1.0]
    aux = [(snap.ret_1m or 0) < 0, (snap.ret_15m or 0) < -0.1,
           p is not None and snap.vwap is not None and p < snap.vwap]
    return sum(core), len(core), sum(aux), len(aux)


def _score_strong_down(snap) -> tuple[int, int, int, int]:
    p = _p(snap)
    core = [(snap.ret_5m or 0) < -0.5, (snap.volume_amplify or 0) > 1.5, snap.buy_sell_ratio < 0.8]
    aux = [(snap.ret_15m or 0) < -0.5, snap.cvd_direction == "down",
           p is not None and snap.vwap is not None and p < snap.vwap,
           p is not None and snap.ema20 is not None and p < snap.ema20]
    return sum(core), len(core), sum(aux), len(aux)


def _score_breakout_up(snap) -> tuple[int, int, int, int]:
    p = _p(snap)
    core = [(snap.ret_5m or 0) > 0.5, (snap.volume_amplify or 0) > 2.0, snap.buy_sell_ratio > 1.5]
    aux = [snap.cvd_direction == "up",
           p is not None and snap.vwap is not None and p > snap.vwap,
           p is not None and snap.ema20 is not None and p > snap.ema20]
    if snap.rsi14 is not None:
        aux.append(snap.rsi14 > 60)
    return sum(core), len(core), sum(aux), len(aux)


def _score_breakdown(snap) -> tuple[int, int, int, int]:
    p = _p(snap)
    core = [(snap.ret_5m or 0) < -0.5, (snap.volume_amplify or 0) > 2.0, snap.buy_sell_ratio < 0.6]
    aux = [snap.cvd_direction == "down",
           p is not None and snap.vwap is not None and p < snap.vwap,
           p is not None and snap.ema20 is not None and p < snap.ema20]
    if snap.rsi14 is not None:
        aux.append(snap.rsi14 < 40)
    return sum(core), len(core), sum(aux), len(aux)


def _score_top_stall(snap) -> tuple[int, int, int, int]:
    p = _p(snap)
    core = [p is not None and snap.ema20 is not None and p < snap.ema20]
    if snap.rsi14 is not None:
        core.append(snap.rsi14 > 70)
    core.append(snap.buy_sell_ratio < 1.0)
    aux = [(snap.ret_1m or 0) < 0, -0.2 <= (snap.ret_5m or 0) <= 0.2, (snap.volume_amplify or 0) < 1.0]
    return sum(core), len(core), sum(aux), len(aux)


def _score_bottom_stabilize(snap) -> tuple[int, int, int, int]:
    p = _p(snap)
    core = [p is not None and snap.ema20 is not None and p > snap.ema20]
    if snap.rsi14 is not None:
        core.append(snap.rsi14 < 30)
    core.append(snap.buy_sell_ratio > 1.0)
    aux = [(snap.ret_1m or 0) > 0, -0.2 <= (snap.ret_5m or 0) <= 0.2, (snap.volume_amplify or 0) < 1.0]
    return sum(core), len(core), sum(aux), len(aux)


def _score_buy_strengthen(snap) -> tuple[int, int, int, int]:
    p = _p(snap)
    core = [snap.buy_sell_ratio > 1.8, snap.cvd_direction == "up", (snap.volume_amplify or 0) > 1.2]
    aux = [(snap.ret_1m or 0) > 0, p is not None and snap.vwap is not None and p > snap.vwap]
    if snap.depth_ratio is not None:
        aux.append(snap.depth_ratio > 1.2)
    return sum(core), len(core), sum(aux), len(aux)


def _score_sell_strengthen(snap) -> tuple[int, int, int, int]:
    p = _p(snap)
    core = [snap.buy_sell_ratio < 0.6, snap.cvd_direction == "down", (snap.volume_amplify or 0) > 1.2]
    aux = [(snap.ret_1m or 0) < 0, p is not None and snap.vwap is not None and p < snap.vwap]
    if snap.depth_ratio is not None:
        aux.append(snap.depth_ratio < 0.8)
    return sum(core), len(core), sum(aux), len(aux)


def _score_abnormal(snap) -> tuple[int, int, int, int]:
    core = [abs(snap.ret_1m or 0) > 3, (snap.volume_amplify or 0) > 4.0]
    if snap.spread_pct is not None:
        core.append(snap.spread_pct > 2)
    if snap.funding_is_extreme:
        core.append(True)
    aux = [snap.cvd_direction in ("up", "down"), abs(snap.buy_sell_ratio - 1.0) > 0.5]
    return sum(core), len(core), sum(aux), len(aux)


STATE_SCORERS = {
    "STRONG_UP": _score_strong_up,
    "WEAK_UP": _score_weak_up,
    "RANGE_BIAS_UP": _score_range_bias_up,
    "RANGE": _score_range,
    "RANGE_BIAS_DOWN": _score_range_bias_down,
    "WEAK_DOWN": _score_weak_down,
    "STRONG_DOWN": _score_strong_down,
    "BREAKOUT_UP": _score_breakout_up,
    "BREAKDOWN": _score_breakdown,
    "TOP_STALL": _score_top_stall,
    "BOTTOM_STABILIZE": _score_bottom_stabilize,
    "BUY_STRENGTHEN": _score_buy_strengthen,
    "SELL_STRENGTHEN": _score_sell_strengthen,
    "ABNORMAL": _score_abnormal,
}
