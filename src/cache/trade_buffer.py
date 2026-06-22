from dataclasses import dataclass
from collections import deque


@dataclass
class Trade:
    timestamp: int  # ms
    price: float
    quantity: float
    is_buyer_maker: bool  # True = sell taker, False = buy taker


class TradeBuffer:
    def __init__(self, maxlen: int = 5000) -> None:
        self.trades: deque[Trade] = deque(maxlen=maxlen)
        self._buy_volume = 0.0
        self._sell_volume = 0.0
        self._cvd_by_minute: dict[int, float] = {}

    def add(self, t: Trade) -> None:
        if len(self.trades) == self.trades.maxlen:
            oldest = self.trades[0]
            if oldest.is_buyer_maker:
                self._sell_volume -= oldest.quantity
            else:
                self._buy_volume -= oldest.quantity
        if t.is_buyer_maker:
            self._sell_volume += t.quantity
        else:
            self._buy_volume += t.quantity
        self.trades.append(t)

        minute = t.timestamp // 60_000
        signed_qty = -t.quantity if t.is_buyer_maker else t.quantity
        self._cvd_by_minute[minute] = self._cvd_by_minute.get(minute, 0.0) + signed_qty
        cutoff = minute - 10
        for old_minute in tuple(self._cvd_by_minute):
            if old_minute < cutoff:
                del self._cvd_by_minute[old_minute]

    @property
    def buy_volume(self) -> float:
        return self._buy_volume

    @property
    def sell_volume(self) -> float:
        return self._sell_volume

    @property
    def buy_sell_ratio(self) -> float:
        sv = self._sell_volume
        return self._buy_volume / sv if sv > 0 else 1.0

    @property
    def cvd_direction(self) -> str:
        """Trend of CVD across the last three completed one-minute buckets."""
        if not self._cvd_by_minute:
            return "flat"
        end = max(self._cvd_by_minute) - 1
        values = [self._cvd_by_minute.get(m, 0.0) for m in range(end - 2, end + 1)]
        if values[0] < values[1] < values[2]:
            return "up"
        if values[0] > values[1] > values[2]:
            return "down"
        return "flat"
