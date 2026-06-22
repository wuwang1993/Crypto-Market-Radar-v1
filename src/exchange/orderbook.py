"""Local order book maintained from WebSocket depth updates."""

from collections import defaultdict
from typing import Optional


class OrderBook:
    """Local order book maintained from WebSocket depth updates (depth20@100ms is full snapshot)."""
    def __init__(self, symbol: str) -> None:
        self.symbol = symbol
        self.bids: defaultdict[float, float] = defaultdict(float)
        self.asks: defaultdict[float, float] = defaultdict(float)
        self.last_update_id: int = 0
        self._depth: int = 20

    def apply_snapshot(self, bids: list[list[float]], asks: list[list[float]]) -> None:
        self.bids.clear()
        self.asks.clear()
        for p, q in bids[:self._depth]:
            self.bids[p] = q
        for p, q in asks[:self._depth]:
            self.asks[p] = q

    def apply_update(self, bids: list[list[float]], asks: list[list[float]]) -> None:
        for p, q in bids:
            if q == 0.0:
                self.bids.pop(p, None)
            else:
                self.bids[p] = q
        for p, q in asks:
            if q == 0.0:
                self.asks.pop(p, None)
            else:
                self.asks[p] = q

    @property
    def top_bid(self) -> Optional[float]:
        return max(self.bids) if self.bids else None

    @property
    def top_ask(self) -> Optional[float]:
        return min(self.asks) if self.asks else None

    @property
    def spread(self) -> Optional[float]:
        b, a = self.top_bid, self.top_ask
        if b and a:
            return a - b
        return None

    @property
    def depth_ratio(self) -> float:
        """bid_total / ask_total for top _depth levels."""
        top_bids = sorted(self.bids, reverse=True)[:self._depth]
        top_asks = sorted(self.asks)[:self._depth]
        bid_sum = sum(self.bids[p] for p in top_bids)
        ask_sum = sum(self.asks[p] for p in top_asks)
        return bid_sum / ask_sum if ask_sum > 0 else 1.0
