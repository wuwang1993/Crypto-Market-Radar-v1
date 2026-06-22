"""Trade-flow indicators: CVD, buy/sell imbalance."""

import time
from src.exchange.adapter import SymbolState


def compute_trades(state: SymbolState) -> dict:
    tb = state.trade_buffer
    now_ms = int(time.time() * 1000)

    result = {
        "buy_volume": tb.buy_volume,
        "sell_volume": tb.sell_volume,
        "buy_sell_ratio": tb.buy_sell_ratio,
    }

    # CVD over last 60 seconds: net buy = qty*(+1 if taker-buy, -1 if taker-sell)
    cvd = 0.0
    for t in tb.trades:
        if now_ms - t.timestamp < 60_000:
            cvd += t.quantity * (1.0 if not t.is_buyer_maker else -1.0)
    result["cvd_1m"] = cvd

    result["cvd_direction"] = tb.cvd_direction

    return result
