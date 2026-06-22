"""Bounded rolling buffers for futures open interest and liquidations."""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass


@dataclass(frozen=True)
class OpenInterestPoint:
    timestamp: int
    value: float


class OpenInterestBuffer:
    """Keep enough 5-minute OI samples to calculate changes up to one hour."""

    def __init__(self, max_points: int = 36) -> None:
        self._points: deque[OpenInterestPoint] = deque(maxlen=max_points)

    def add(self, timestamp: int, value: float) -> None:
        if timestamp <= 0 or value <= 0:
            return
        point = OpenInterestPoint(int(timestamp), float(value))
        if self._points and point.timestamp == self._points[-1].timestamp:
            self._points[-1] = point
        elif not self._points or point.timestamp > self._points[-1].timestamp:
            self._points.append(point)

    @property
    def latest(self) -> float | None:
        return self._points[-1].value if self._points else None

    def change_pct(self, minutes: int) -> float | None:
        if len(self._points) < 2:
            return None
        latest = self._points[-1]
        target = latest.timestamp - minutes * 60_000
        baseline = None
        for point in reversed(self._points):
            if point.timestamp <= target:
                baseline = point
                break
        if baseline is None or baseline.value <= 0:
            return None
        return (latest.value - baseline.value) / baseline.value * 100


@dataclass
class LiquidationBucket:
    minute: int
    long_usdt: float = 0.0
    short_usdt: float = 0.0


class LiquidationBuffer:
    """Aggregate observed force-order events into bounded minute buckets."""

    def __init__(self, retention_minutes: int = 65) -> None:
        self._buckets: deque[LiquidationBucket] = deque(maxlen=retention_minutes + 1)

    def add(self, timestamp: int, side: str, notional_usdt: float) -> None:
        if timestamp <= 0 or notional_usdt <= 0:
            return
        minute = int(timestamp) // 60_000 * 60_000
        if not self._buckets or minute > self._buckets[-1].minute:
            self._buckets.append(LiquidationBucket(minute=minute))
        elif minute < self._buckets[-1].minute:
            return
        bucket = self._buckets[-1]
        if side == "long":
            bucket.long_usdt += float(notional_usdt)
        elif side == "short":
            bucket.short_usdt += float(notional_usdt)

    def totals(self, minutes: int, now_ms: int | None = None) -> tuple[float, float]:
        now = int(now_ms if now_ms is not None else time.time() * 1000)
        cutoff = now - minutes * 60_000
        long_total = 0.0
        short_total = 0.0
        for bucket in reversed(self._buckets):
            if bucket.minute + 60_000 <= cutoff:
                break
            long_total += bucket.long_usdt
            short_total += bucket.short_usdt
        return long_total, short_total
