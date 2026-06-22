"""Volume-based indicators."""

from src.exchange.adapter import SymbolState


def compute_volume(state: SymbolState) -> dict:
    buf = state.kline_buffer
    k5 = buf.latest_5m
    recent = buf.recent_20_5m

    vol_5m_current = k5.volume if k5 else 0.0
    result = {"vol_5m_current": vol_5m_current}

    # avg volume of last 20 5m klines, excluding the current one
    if len(recent) >= 2:
        prev = [k.volume for k in recent[:-1]]
        vol_5m_avg = sum(prev) / len(prev)
    elif len(recent) == 1:
        vol_5m_avg = recent[0].volume
    else:
        vol_5m_avg = None
    result["vol_5m_avg"] = vol_5m_avg

    result["volume_amplify"] = (
        vol_5m_current / vol_5m_avg if vol_5m_avg and vol_5m_avg > 0 else None
    )
    return result
