"""Volume-Weighted Average Price."""

from typing import Optional
from src.exchange.adapter import SymbolState


def compute_vwap(state: SymbolState) -> Optional[float]:
    klines = list(state.kline_buffer.klines_1m)
    if not klines:
        return None

    tp_vol_sum = 0.0
    vol_sum = 0.0
    for k in klines:
        tp = (k.high + k.low + k.close) / 3.0
        tp_vol_sum += tp * k.volume
        vol_sum += k.volume

    return tp_vol_sum / vol_sum if vol_sum > 0 else None
