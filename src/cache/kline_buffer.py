from dataclasses import dataclass, field
from collections import deque
from typing import Optional


@dataclass
class Kline:
    timestamp: int  # ms
    open: float
    high: float
    low: float
    close: float
    volume: float


class KlineBuffer:
    def __init__(self) -> None:
        self.klines_1m: deque[Kline] = deque(maxlen=1440)
        self.klines_5m: deque[Kline] = deque(maxlen=288)

    def add_1m(self, k: Kline) -> None:
        self._upsert(self.klines_1m, k)

    def add_5m(self, k: Kline) -> None:
        self._upsert(self.klines_5m, k)

    @staticmethod
    def _upsert(buffer: deque[Kline], k: Kline) -> None:
        """Append a new candle or refresh the currently forming candle."""
        if not buffer:
            buffer.append(k)
        elif k.timestamp == buffer[-1].timestamp:
            buffer[-1] = k
        elif k.timestamp > buffer[-1].timestamp:
            buffer.append(k)

    @property
    def recent_20_5m(self) -> list[Kline]:
        return list(self.klines_5m)[-20:]

    @property
    def latest_5m(self) -> Optional[Kline]:
        if self.klines_5m:
            return self.klines_5m[-1]
        return None

    @property
    def latest_1m(self) -> Optional[Kline]:
        if self.klines_1m:
            return self.klines_1m[-1]
        return None
