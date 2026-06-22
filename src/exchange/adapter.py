"""Unified exchange interface with callback-driven data dispatch.

Wraps Binance WS + REST behind a clean API.  Maintains per-symbol
market state and fires user-registered callbacks on every update.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Optional

from src.cache.kline_buffer import KlineBuffer
from src.cache.trade_buffer import TradeBuffer
from src.cache.derivatives_buffer import LiquidationBuffer, OpenInterestBuffer
from src.exchange.orderbook import OrderBook
from src.exchange.binance_ws import BinanceWS
from src.exchange.binance_liquidation_ws import BinanceLiquidationWS
from src.exchange.binance_rest import BinanceREST

logger = logging.getLogger(__name__)

Callback = Callable[..., Awaitable[None]]

DEFAULT_SYMBOLS = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT",
    "BNB/USDT", "DOGE/USDT", "XRP/USDT",
]


@dataclass
class SymbolState:
    symbol: str
    price: float = 0.0
    ticker_24h: dict[str, Any] = field(default_factory=dict)
    kline_buffer: KlineBuffer = field(default_factory=KlineBuffer)
    trade_buffer: TradeBuffer = field(default_factory=TradeBuffer)
    orderbook: OrderBook | None = None
    funding_rate: float = 0.0
    open_interest: float = 0.0
    oi_buffer: OpenInterestBuffer = field(default_factory=OpenInterestBuffer)
    liquidation_buffer: LiquidationBuffer = field(default_factory=LiquidationBuffer)
    last_update: float = 0.0  # monotonic timestamp

    def __post_init__(self) -> None:
        if self.orderbook is None:
            self.orderbook = OrderBook(self.symbol)


class MarketCache:
    def __init__(self, symbols: list[str]) -> None:
        self._states: dict[str, SymbolState] = {
            s: SymbolState(symbol=s) for s in symbols
        }

    def get(self, symbol: str) -> SymbolState:
        return self._states[symbol]

    def items(self):
        return self._states.items()

    def keys(self):
        return self._states.keys()

    @property
    def symbols(self) -> list[str]:
        return list(self._states)


class ExchangeAdapter:
    def __init__(
        self,
        symbols: Optional[list[str]] = None,
        ws_ping_interval: int = 180,
        ws_pong_timeout: int = 30,
        rest_poll_interval: float = 5.0,
    ) -> None:
        self._symbols = symbols or DEFAULT_SYMBOLS
        self._cache = MarketCache(self._symbols)
        self._ws = BinanceWS(self._symbols, ping_interval=ws_ping_interval, pong_timeout=ws_pong_timeout)
        self._liquidation_ws = BinanceLiquidationWS(self._symbols)
        self._rest = BinanceREST(self._symbols, poll_interval=rest_poll_interval)
        self._callbacks: dict[str, list[Callback]] = {}
        self._fallback_mode = False
        self._running = False
        self._tasks: list[asyncio.Task] = []
        self._last_kline_ts: dict[str, dict[str, int]] = {}
        self._funding_oi_counter = 0

    @property
    def cache(self) -> MarketCache:
        return self._cache

    @property
    def fallback_mode(self) -> bool:
        return self._fallback_mode

    @property
    def connected(self) -> bool:
        return self._ws.connected if self._ws else False

    @property
    def derivatives_connected(self) -> bool:
        return self._liquidation_ws.connected

    def subscribe_callbacks(self, **handlers: Callback) -> None:
        """Register typed callbacks: on_ticker, on_kline_1m, on_kline_5m,
        on_trade, on_depth, on_funding_rate, on_open_interest."""
        for name, cb in handlers.items():
            self._callbacks.setdefault(name, []).append(cb)

    async def _dispatch(self, name: str, *args: Any) -> None:
        for cb in self._callbacks.get(name, ()):
            try:
                await cb(*args)
            except Exception:
                logger.exception("Callback %s(%s) failed", name, args[:1])

    # ── internal WS data handlers ─────────────────────────────────

    async def _on_ticker(self, symbol: str, data: dict) -> None:
        state = self._cache.get(symbol)
        state.price = float(data.get("last", 0) or 0)
        state.ticker_24h = data
        state.last_update = time.monotonic()
        await self._dispatch("on_ticker", symbol, data)

    async def _on_kline(self, symbol: str, tf: str, data: list | None) -> None:
        if data is None:
            return
        state = self._cache.get(symbol)
        k = self._to_kline(data)
        if tf == "1m":
            state.kline_buffer.add_1m(k)
        elif tf == "5m":
            state.kline_buffer.add_5m(k)
        state.last_update = time.monotonic()
        await self._dispatch(f"on_kline_{tf}", symbol, k)

    async def _on_trade(self, symbol: str, data: dict) -> None:
        from src.cache.trade_buffer import Trade
        state = self._cache.get(symbol)
        # Binance aggTrade: side=buy means taker bought (buy-taker)
        # side=sell means taker sold (sell-taker → buyer was maker)
        side = data.get("side", "buy")
        is_maker = (side == "sell")
        t = Trade(
            timestamp=int(data.get("timestamp", 0)),
            price=float(data.get("price", 0)),
            quantity=float(data.get("amount", 0)),
            is_buyer_maker=is_maker,
        )
        state.trade_buffer.add(t)
        state.last_update = time.monotonic()
        await self._dispatch("on_trade", symbol, t)

    async def _on_depth(self, symbol: str, data: dict) -> None:
        state = self._cache.get(symbol)
        if state.orderbook is None:
            state.orderbook = OrderBook(symbol)
        bids = data.get("bids", [])
        asks = data.get("asks", [])
        if bids or asks:
            state.orderbook.apply_update(bids, asks)
        state.last_update = time.monotonic()
        await self._dispatch("on_depth", symbol, state.orderbook)

    async def _on_liquidation(self, symbol: str, data: dict) -> None:
        state = self._cache.get(symbol)
        state.liquidation_buffer.add(
            timestamp=int(data.get("timestamp", 0)),
            side=str(data.get("side", "")),
            notional_usdt=float(data.get("notional_usdt", 0) or 0),
        )
        await self._dispatch("on_liquidation", symbol, data)

    @staticmethod
    def _to_kline(data: list) -> "Kline":
        from src.cache.kline_buffer import Kline
        ts, o, h, l, c, v = data[0:6]
        return Kline(timestamp=int(ts), open=float(o), high=float(h),
                     low=float(l), close=float(c), volume=float(v))

    # ── lifecycle ─────────────────────────────────────────────────

    async def warmup(self) -> None:
        """Pull historical klines + ticker via REST before WS connect."""
        t0 = time.monotonic()
        results = await self._rest.warmup()
        for symbol, data in results.items():
            state = self._cache.get(symbol)
            ticker = data.get("ticker", {})
            if ticker:
                state.price = float(ticker.get("last", 0) or 0)
                state.ticker_24h = ticker
            for kline in data.get("klines_5m", []):
                state.kline_buffer.add_5m(kline)
            fr = data.get("funding_rate")
            if fr is not None:
                state.funding_rate = float(fr)
            oi = data.get("open_interest")
            if oi is not None:
                state.open_interest = float(oi)
            for point in data.get("oi_history", []):
                state.oi_buffer.add(point["timestamp"], point["openInterest"])
            if state.open_interest > 0:
                state.oi_buffer.add(int(time.time() * 1000), state.open_interest)
            state.last_update = time.monotonic()
        logger.info("Warmup complete for %d symbols in %.1fs",
                     len(results), time.monotonic() - t0)

    async def start(self) -> None:
        """Start WebSocket connection, kline poller, and fallback monitor."""
        self._running = True
        # Wire WS callbacks into adapter handlers (ticker/trades/depth only)
        self._ws.on_ticker = self._on_ticker
        self._ws.on_trade = self._on_trade
        self._ws.on_depth = self._on_depth
        self._liquidation_ws.on_liquidation = self._on_liquidation

        self._tasks.append(asyncio.create_task(self._ws.connect()))
        self._tasks.append(asyncio.create_task(self._liquidation_ws.connect()))
        self._tasks.append(asyncio.create_task(self._fallback_monitor()))
        self._tasks.append(asyncio.create_task(self._kline_poller()))
        logger.info("Exchange adapter started")

    async def stop(self) -> None:
        self._running = False
        await self._ws.disconnect()
        await self._liquidation_ws.disconnect()
        for t in self._tasks:
            t.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        await self._rest.close()
        logger.info("Exchange adapter stopped")

    async def _fallback_monitor(self) -> None:
        """Monitor WS health; fall back to REST polling when WS is down."""
        while self._running:
            await asyncio.sleep(5)
            if self._ws.connected:
                if self._fallback_mode:
                    self._fallback_mode = False
                    logger.info("WS reconnected, leaving fallback mode")
                continue
            if not self._fallback_mode:
                self._fallback_mode = True
                logger.warning("WS disconnected, entering fallback mode")
                while self._running and not self._ws.connected:
                    try:
                        data = await self._rest.poll()
                        for symbol, ticker in data.items():
                            state = self._cache.get(symbol)
                            state.price = float(ticker.get("last", 0) or 0)
                            state.ticker_24h = ticker
                            state.last_update = time.monotonic()
                            await self._dispatch("on_ticker", symbol, ticker)
                    except Exception:
                        logger.exception("REST fallback poll failed")
                    await asyncio.sleep(self._rest.poll_interval)

    async def _kline_poller(self) -> None:
        """Poll latest 1m and 5m klines via REST every 5s."""
        while self._running:
            await asyncio.sleep(5)
            try:
                klines_data = await self._rest.poll_klines()
                for symbol, klines in klines_data.items():
                    state = self._cache.get(symbol)
                    sym_ts = self._last_kline_ts.setdefault(symbol, {"1m": 0, "5m": 0})
                    new_data = False
                    for k in klines.get("1m", []):
                        if k.timestamp >= sym_ts["1m"]:
                            state.kline_buffer.add_1m(k)
                            sym_ts["1m"] = k.timestamp
                            new_data = True
                    for k in klines.get("5m", []):
                        if k.timestamp >= sym_ts["5m"]:
                            state.kline_buffer.add_5m(k)
                            sym_ts["5m"] = k.timestamp
                            new_data = True
                    if new_data:
                        state.last_update = time.monotonic()
                # Periodic funding rate / open interest refresh (every 30 polls = 150s)
                self._funding_oi_counter += 1
                if self._funding_oi_counter >= 30:
                    self._funding_oi_counter = 0
                    for symbol in self._symbols:
                        try:
                            state = self._cache.get(symbol)
                            fr = await self._rest.fetch_funding_rate(symbol)
                            if fr:
                                state.funding_rate = float(fr.get("fundingRate", 0) or 0)
                            oi = await self._rest.fetch_open_interest(symbol)
                            if oi:
                                state.open_interest = float(oi.get("openInterestAmount", 0) or 0)
                                state.oi_buffer.add(
                                    int(oi.get("timestamp", 0) or time.time() * 1000),
                                    state.open_interest,
                                )
                        except Exception:
                            logger.debug("Funding/OI poll failed for %s", symbol)
            except Exception:
                logger.exception("Kline poll failed")

    def get_state(self, symbol: str) -> Optional[SymbolState]:
        return self._cache._states.get(symbol)
