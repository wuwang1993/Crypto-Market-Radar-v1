"""State judgment engine with hysteresis and exit-condition forcing."""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.state.state_types import MarketState
from src.state.rules import STATE_SCORERS
from src.indicators import get_indicator_value

if TYPE_CHECKING:
    from src.indicators import IndicatorSnapshot


def _p(snap: "IndicatorSnapshot") -> float | None:
    """Best price proxy: raw price > VWAP."""
    p = get_indicator_value(snap, "price", None)
    return float(p) if p is not None and p > 0 else snap.vwap


# ── Score computation ─────────────────────────────────────────────

def _score(snap: "IndicatorSnapshot") -> dict[MarketState, float]:
    """Compute score for all 14 evaluable states.

    Score = (core_hits/core_total)*0.7 + (aux_hits/aux_total)*0.3
    """
    results: dict[MarketState, float] = {}
    for name, scorer in STATE_SCORERS.items():
        state = MarketState[name]
        ch, ct, ah, at = scorer(snap)
        if ct == 0:
            core_s = 0.0
        else:
            core_s = ch / ct
        if at == 0:
            aux_s = 0.0
        else:
            aux_s = ah / at
        results[state] = core_s * 0.7 + aux_s * 0.3
    return results


# ── Exit condition helpers ────────────────────────────────────────

def _exit_strong_up(snap: "IndicatorSnapshot") -> bool:
    return snap.buy_sell_ratio < 0.8


def _exit_strong_down(snap: "IndicatorSnapshot") -> bool:
    return snap.buy_sell_ratio > 1.2


def _exit_breakout_up(snap: "IndicatorSnapshot") -> bool:
    return (snap.volume_amplify or 0) < 1.0


def _exit_breakdown(snap: "IndicatorSnapshot") -> bool:
    return (snap.volume_amplify or 0) < 1.0


def _exit_top_stall(snap: "IndicatorSnapshot") -> bool:
    rsi_ok = snap.rsi14 is not None and snap.rsi14 < 60
    p = _p(snap)
    price_ok = snap.ema20 is not None and p is not None and p > snap.ema20
    return rsi_ok or price_ok


def _exit_bottom_stabilize(snap: "IndicatorSnapshot") -> bool:
    rsi_ok = snap.rsi14 is not None and snap.rsi14 > 40
    p = _p(snap)
    price_ok = snap.ema20 is not None and p is not None and p > snap.ema20
    return rsi_ok and price_ok


def _exit_buy_strengthen(snap: "IndicatorSnapshot") -> bool:
    return snap.buy_sell_ratio < 1.2


def _exit_sell_strengthen(snap: "IndicatorSnapshot") -> bool:
    return snap.buy_sell_ratio > 0.8


_EXIT_HANDLERS: dict[MarketState, callable] = {
    MarketState.STRONG_UP: _exit_strong_up,
    MarketState.STRONG_DOWN: _exit_strong_down,
    MarketState.BREAKOUT_UP: _exit_breakout_up,
    MarketState.BREAKDOWN: _exit_breakdown,
    MarketState.TOP_STALL: _exit_top_stall,
    MarketState.BOTTOM_STABILIZE: _exit_bottom_stabilize,
    MarketState.BUY_STRENGTHEN: _exit_buy_strengthen,
    MarketState.SELL_STRENGTHEN: _exit_sell_strengthen,
}


# ── Main evaluation ───────────────────────────────────────────────

def evaluate_state(
    snap: "IndicatorSnapshot",
    prev_state: MarketState = MarketState.NORMAL,
) -> tuple[MarketState, float]:
    """Determine MarketState from IndicatorSnapshot with hysteresis.

    1. Score all 14 states
    2. Find best >= 0.65; return it
    3. If best < 0.35, return NORMAL (0.0)
    4. If 0.35 <= best < 0.65, check exit conditions:
       - If prev_state's exit triggers → force best
       - Otherwise cling to prev_state (hysteresis)
    5. Return (state, score)
    """
    scores = _score(snap)

    # Sort states by score descending
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    best_state, best_score = ranked[0]

    # High confidence — commit immediately
    if best_score >= 0.65:
        return (best_state, best_score)

    # No clear signal — default to NORMAL
    if best_score < 0.35:
        return (MarketState.NORMAL, 0.0)

    # Hysteresis zone 0.35–0.65
    exit_handler = _EXIT_HANDLERS.get(prev_state)
    if exit_handler is not None and exit_handler(snap):
        # Exit condition triggered: force best candidate even if in hysteresis zone
        return (best_state, best_score)

    # Cling to previous state
    return (prev_state, scores.get(prev_state, best_score))
