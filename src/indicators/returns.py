"""Price returns over multiple timeframes."""

from src.exchange.adapter import SymbolState


def compute_returns(state: SymbolState) -> dict:
    buf = state.kline_buffer
    price = state.price
    result = {}

    # 1m return
    k1 = buf.latest_1m
    result["ret_1m"] = ((price - k1.close) / k1.close * 100) if k1 and k1.close > 0 else None

    # 5m return
    k5 = buf.latest_5m
    result["ret_5m"] = ((price - k5.close) / k5.close * 100) if k5 and k5.close > 0 else None

    # 15m return: 3rd-to-last 5m close
    recent = buf.recent_20_5m
    if len(recent) >= 3:
        ref = recent[-3].close
        result["ret_15m"] = ((price - ref) / ref * 100) if ref > 0 else None
    else:
        result["ret_15m"] = None

    # 1h return: 12th-to-last 5m close
    if len(recent) >= 12:
        ref = recent[-12].close
        result["ret_1h"] = ((price - ref) / ref * 100) if ref > 0 else None
    else:
        result["ret_1h"] = None

    return result
