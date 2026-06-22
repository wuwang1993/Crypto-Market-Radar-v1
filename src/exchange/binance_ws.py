"""Binance WebSocket using aiohttp — lightweight replacement for ccxt.pro.

Single multiplex connection: all symbols×3 streams on one TCP socket.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Awaitable, Callable, Optional

import aiohttp

logger = logging.getLogger(__name__)

WS_BASE = "wss://stream.binance.com:9443/stream"
MAX_RETRIES = 10
BACKOFF_BASE = 1.0
BACKOFF_MAX = 32.0


class BinanceWS:
    def __init__(
        self,
        symbols: list[str],
        ping_interval: int = 180,
        pong_timeout: int = 30,
    ) -> None:
        self.symbols = symbols
        self.ping_interval = ping_interval
        self.pong_timeout = pong_timeout
        self.connected = False
        self.on_ticker: Optional[Callable[..., Awaitable[None]]] = None
        self.on_trade: Optional[Callable[..., Awaitable[None]]] = None
        self.on_depth: Optional[Callable[..., Awaitable[None]]] = None
        self._ws: Optional[aiohttp.ClientWebSocketResponse] = None
        self._session: Optional[aiohttp.ClientSession] = None
        self._tasks: list[asyncio.Task] = []
        self._last_seq: dict[str, Optional[int]] = {}  # track duplicate sequence per stream

    @staticmethod
    def _ws_symbol(symbol: str) -> str:
        """BTC/USDT → btcusdt"""
        return symbol.replace("/", "").lower()

    @staticmethod
    def _to_display(ws_symbol: str) -> str:
        """btcusdt → BTC/USDT, ethusdt → ETH/USDT"""
        s = ws_symbol.upper()
        if "USDT" in s:
            idx = s.index("USDT")
            return f"{s[:idx]}/USDT"
        return s

    def _build_stream_url(self) -> str:
        streams = []
        for sym in self.symbols:
            s = self._ws_symbol(sym)
            streams.append(f"{s}@ticker")
            streams.append(f"{s}@aggTrade")
            streams.append(f"{s}@depth20@100ms")
        return f"{WS_BASE}?streams={'/'.join(streams)}"

    async def connect(self) -> None:
        retries = 0
        while retries < MAX_RETRIES:
            try:
                self._session = aiohttp.ClientSession()
                self._ws = await self._session.ws_connect(self._build_stream_url())
                self.connected = True
                retries = 0
                logger.info("Binance WS connected — %d symbols × 3 streams on 1 connection", len(self.symbols))
                self._tasks = [
                    asyncio.create_task(self._read_loop()),
                    asyncio.create_task(self._ping_loop()),
                ]
                await asyncio.gather(*self._tasks)
            except (aiohttp.ClientError, asyncio.TimeoutError, ConnectionError) as e:
                self.connected = False
                retries += 1
                delay = min(BACKOFF_BASE * (2 ** (retries - 1)), BACKOFF_MAX)
                logger.error("Binance WS disconnected (attempt %d/%d), reconnecting in %.1fs: %s",
                             retries, MAX_RETRIES, delay, e)
                await self._cleanup_session()
                if retries >= MAX_RETRIES:
                    logger.critical("Binance WS: max retries reached, giving up")
                    return
                await asyncio.sleep(delay)
            except Exception:
                self.connected = False
                logger.exception("Binance WS unexpected error")
                await self._cleanup_session()
                await asyncio.sleep(BACKOFF_MAX)

    async def _cleanup_session(self) -> None:
        for t in self._tasks:
            t.cancel()
        self._tasks.clear()
        if self._ws and not self._ws.closed:
            await self._ws.close()
        if self._session and not self._session.closed:
            await self._session.close()
        self._ws = None
        self._session = None

    async def disconnect(self) -> None:
        self.connected = False
        await self._cleanup_session()
        logger.info("Binance WS disconnected")

    async def _read_loop(self) -> None:
        while self.connected and self._ws and not self._ws.closed:
            try:
                msg = await self._ws.receive(timeout=self.pong_timeout + 30)
                if msg.type == aiohttp.WSMsgType.TEXT:
                    await self._dispatch(json.loads(msg.data))
                elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                    logger.warning("WS closed/error: %s", msg.type)
                    self.connected = False
                    break
            except asyncio.TimeoutError:
                logger.warning("WS read timeout after %.1fs", self.pong_timeout + 30)
                self.connected = False
                break
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("WS read error")
                self.connected = False
                break

    async def _dispatch(self, msg: dict) -> None:
        stream: str = msg.get("stream", "")
        data: dict = msg.get("data", {})
        if not stream or not data:
            return

        # Dedup by sequence number (E field for ticker/aggTrade)
        seq = data.get("E", data.get("T", data.get("lastUpdateId", 0)))
        prev = self._last_seq.get(stream)
        if prev is not None and seq <= prev:
            return
        self._last_seq[stream] = seq

        # Extract symbol: "btcusdt@ticker" → "btcusdt"
        ws_symbol = stream.split("@")[0]
        symbol = self._to_display(ws_symbol)

        if "@ticker" in stream:
            mapped = {
                "symbol": symbol,
                "last": float(data.get("c", 0)),
                "high": float(data.get("h", 0)),
                "low": float(data.get("l", 0)),
            }
            if self.on_ticker:
                await self.on_ticker(symbol, mapped)

        elif "@aggTrade" in stream:
            m: bool = data.get("m", False)
            mapped = {
                "side": "sell" if m else "buy",
                "price": float(data.get("p", 0)),
                "amount": float(data.get("q", 0)),
                "timestamp": int(data.get("T", 0)),
            }
            if self.on_trade:
                await self.on_trade(symbol, mapped)

        elif "@depth" in stream:
            bids = [[float(b[0]), float(b[1])] for b in data.get("bids", [])]
            asks = [[float(a[0]), float(a[1])] for a in data.get("asks", [])]
            mapped = {"bids": bids, "asks": asks}
            if self.on_depth:
                await self.on_depth(symbol, mapped)

    async def _ping_loop(self) -> None:
        while self.connected and self._ws and not self._ws.closed:
            await asyncio.sleep(self.ping_interval)
            if not self.connected:
                break
            try:
                await self._ws.ping()
            except Exception:
                logger.error("WS ping failed — forcing disconnect")
                self.connected = False
                break
