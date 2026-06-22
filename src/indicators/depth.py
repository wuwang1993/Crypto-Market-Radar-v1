"""Order-book depth indicators."""

from typing import Optional
from src.exchange.adapter import SymbolState


def compute_depth(state: SymbolState) -> dict:
    ob = state.orderbook
    if ob is None:
        return {
            "depth_ratio": None,
            "spread": None,
            "spread_pct": None,
            "bid_wall": None,
            "ask_wall": None,
        }

    dr = ob.depth_ratio
    sp = ob.spread
    ta = ob.top_ask
    sp_pct = (sp / ta * 100) if sp is not None and ta is not None and ta > 0 else None

    # bid wall = top 5 bid levels
    bw: Optional[float] = None
    if ob.bids:
        sorted_bids = sorted(ob.bids, reverse=True)[:5]
        bw = sum(ob.bids[p] for p in sorted_bids)

    aw: Optional[float] = None
    if ob.asks:
        sorted_asks = sorted(ob.asks)[:5]
        aw = sum(ob.asks[p] for p in sorted_asks)

    return {
        "depth_ratio": dr,
        "spread": sp,
        "spread_pct": sp_pct,
        "bid_wall": bw,
        "ask_wall": aw,
    }
