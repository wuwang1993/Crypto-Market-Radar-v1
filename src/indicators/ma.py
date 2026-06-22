"""Exponential Moving Averages."""

from typing import Optional
from src.exchange.adapter import SymbolState


def _ema(values: list[float], period: int) -> Optional[float]:
    if len(values) < period:
        return None
    k = 2.0 / (period + 1)
    ema = sum(values[:period]) / period
    for v in values[period:]:
        ema = v * k + ema * (1 - k)
    return ema


def compute_ma(state: SymbolState) -> dict:
    all_closes = [k.close for k in state.kline_buffer.klines_5m]
    return {
        "ema20": _ema(all_closes, 20) if len(all_closes) >= 20 else None,
        "ema60": _ema(all_closes, 60) if len(all_closes) >= 60 else None,
    }
