"""Wilder's Relative Strength Index."""

from typing import Optional
from src.exchange.adapter import SymbolState


def _wilder_rsi(closes: list[float], period: int) -> Optional[float]:
    if len(closes) < period + 1:
        return None

    gains = []
    losses = []
    for i in range(1, period + 1):
        diff = closes[i] - closes[i - 1]
        if diff > 0:
            gains.append(diff)
            losses.append(0.0)
        else:
            gains.append(0.0)
            losses.append(-diff)

    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period

    # Smoothed
    for i in range(period + 1, len(closes)):
        diff = closes[i] - closes[i - 1]
        gain = diff if diff > 0 else 0.0
        loss = -diff if diff < 0 else 0.0
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period

    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - 100.0 / (1.0 + rs)


def compute_rsi(state: SymbolState) -> dict:
    closes = [k.close for k in state.kline_buffer.klines_5m]
    return {
        "rsi6": _wilder_rsi(closes, 6),
        "rsi14": _wilder_rsi(closes, 14),
    }
