"""Binance USD-M futures liquidation stream."""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from typing import Optional

import aiohttp

logger = logging.getLogger(__name__)

FUTURES_WS_BASE = "wss://fstream.binance.com/stream"
BACKOFF_MAX = 32.0


class BinanceLiquidationWS:
    """Consume per-symbol force-order streams over one multiplex connection."""

    def __init__(self, symbols: list[str]) -> None:
        self.symbols = symbols
        self.connected = False
        self.on_liquidation: Optional[Callable[..., Awaitable[None]]] = None
        self._running = False
        self._session: aiohttp.ClientSession | None = None
        self._ws: aiohttp.ClientWebSocketResponse | None = None
        self._last_event: dict[str, tuple] = {}

    @staticmethod
    def _ws_symbol(symbol: str) -> str:
        return symbol.replace("/", "").lower()

    @staticmethod
    def _to_display(symbol: str) -> str:
        value = symbol.upper()
        return f"{value[:-4]}/USDT" if value.endswith("USDT") else value

    def _url(self) -> str:
        streams = "/".join(
            f"{self._ws_symbol(symbol)}@forceOrder" for symbol in self.symbols
        )
        return f"{FUTURES_WS_BASE}?streams={streams}"

    async def connect(self) -> None:
        self._running = True
        failures = 0
        while self._running:
            try:
                self._session = aiohttp.ClientSession()
                self._ws = await self._session.ws_connect(self._url(), heartbeat=180)
                self.connected = True
                failures = 0
                logger.info(
                    "Binance liquidation WS connected — %d symbols", len(self.symbols)
                )
                await self._read_loop()
                if self._running:
                    raise ConnectionError("liquidation stream closed")
            except asyncio.CancelledError:
                break
            except Exception as exc:
                self.connected = False
                failures += 1
                delay = min(2 ** (failures - 1), BACKOFF_MAX)
                logger.warning(
                    "Liquidation WS disconnected, reconnecting in %.1fs: %s",
                    delay,
                    exc,
                )
                await self._cleanup()
                if self._running:
                    await asyncio.sleep(delay)
        await self._cleanup()

    async def _read_loop(self) -> None:
        while self._running and self._ws and not self._ws.closed:
            message = await self._ws.receive(timeout=240)
            if message.type == aiohttp.WSMsgType.TEXT:
                await self._dispatch(json.loads(message.data))
            elif message.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                break

    async def _dispatch(self, message: dict) -> None:
        data = message.get("data", message)
        if data.get("e") != "forceOrder":
            return
        order = data.get("o", {})
        raw_symbol = str(order.get("s", ""))
        if not raw_symbol:
            return
        signature = (
            int(order.get("T", data.get("E", 0)) or 0),
            order.get("S"),
            order.get("q"),
            order.get("ap"),
        )
        if self._last_event.get(raw_symbol) == signature:
            return
        self._last_event[raw_symbol] = signature

        price = float(order.get("ap", 0) or order.get("p", 0) or 0)
        quantity = float(
            order.get("z", 0) or order.get("l", 0) or order.get("q", 0) or 0
        )
        order_side = str(order.get("S", "")).upper()
        liquidation_side = "long" if order_side == "SELL" else "short"
        event = {
            "timestamp": signature[0],
            "side": liquidation_side,
            "price": price,
            "quantity": quantity,
            "notional_usdt": price * quantity,
        }
        if self.on_liquidation and event["notional_usdt"] > 0:
            await self.on_liquidation(self._to_display(raw_symbol), event)

    async def _cleanup(self) -> None:
        self.connected = False
        if self._ws and not self._ws.closed:
            await self._ws.close()
        if self._session and not self._session.closed:
            await self._session.close()
        self._ws = None
        self._session = None

    async def disconnect(self) -> None:
        self._running = False
        await self._cleanup()
        logger.info("Binance liquidation WS disconnected")
