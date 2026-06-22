"""Binance REST API using aiohttp — lightweight replacement for ccxt REST."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

import aiohttp

from src.cache.kline_buffer import Kline

logger = logging.getLogger(__name__)

BASE_URL = "https://api.binance.com"
FAPI_URL = "https://fapi.binance.com"


class BinanceREST:
    def __init__(
        self,
        symbols: list[str],
        poll_interval: float = 5.0,
        warmup_kline_count: int = 20,
    ) -> None:
        self.symbols = symbols
        self._poll_interval = poll_interval
        self.warmup_kline_count = warmup_kline_count
        self._session: Optional[aiohttp.ClientSession] = None
        self._consecutive_rate_limits = 0

    @property
    def poll_interval(self) -> float:
        if self._consecutive_rate_limits > 0:
            return min(self._poll_interval * (2 ** self._consecutive_rate_limits), 60.0)
        return self._poll_interval

    @poll_interval.setter
    def poll_interval(self, v: float) -> None:
        self._poll_interval = v

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()
        self._session = None

    @staticmethod
    def _spot_symbol(symbol: str) -> str:
        """BTC/USDT → BTCUSDT"""
        return symbol.replace("/", "")

    async def _get_json(self, url: str) -> Any:
        session = await self._get_session()
        async with session.get(url) as resp:
            if resp.status == 429:
                self._consecutive_rate_limits += 1
                logger.warning("REST 429 rate limited on %s", url)
                return None
            if resp.status != 200:
                logger.warning("REST %s → %d", url, resp.status)
                return None
            self._consecutive_rate_limits = 0
            return await resp.json()

    # ── warmup ────────────────────────────────────────────────

    async def warmup(self) -> dict[str, dict]:
        results: dict[str, dict] = {}

        async def _fetch_one(symbol: str) -> None:
            data: dict[str, Any] = {
                "ticker": {},
                "klines_5m": [],
                "funding_rate": 0.0,
                "open_interest": 0.0,
                "oi_history": [],
            }
            try:
                s = self._spot_symbol(symbol)

                # 24h ticker
                ticker = await self._get_json(f"{BASE_URL}/api/v3/ticker/24hr?symbol={s}")
                if ticker:
                    data["ticker"] = {
                        "symbol": symbol,
                        "last": float(ticker.get("lastPrice", 0)),
                        "high": float(ticker.get("highPrice", 0)),
                        "low": float(ticker.get("lowPrice", 0)),
                        "baseVolume": float(ticker.get("volume", 0)),
                    }

                # 5m klines
                klines = await self._get_json(
                    f"{BASE_URL}/api/v3/klines?symbol={s}&interval=5m&limit={self.warmup_kline_count}"
                )
                if klines:
                    data["klines_5m"] = [
                        Kline(
                            timestamp=int(k[0]), open=float(k[1]), high=float(k[2]),
                            low=float(k[3]), close=float(k[4]), volume=float(k[5]),
                        )
                        for k in klines
                    ]

                # funding rate (futures)
                fr = await self._get_json(f"{FAPI_URL}/fapi/v1/fundingRate?symbol={s}&limit=1")
                if fr and isinstance(fr, list) and len(fr) > 0:
                    data["funding_rate"] = float(fr[0].get("fundingRate", 0))

                # open interest (futures)
                oi = await self._get_json(f"{FAPI_URL}/fapi/v1/openInterest?symbol={s}")
                if oi:
                    data["open_interest"] = float(oi.get("openInterest", 0))

                data["oi_history"] = await self.fetch_open_interest_history(symbol, limit=14)
            except Exception:
                logger.exception("Warmup failed for %s", symbol)
            results[symbol] = data

        await asyncio.gather(*[_fetch_one(s) for s in self.symbols])
        return results

    # ── poll tickers ──────────────────────────────────────────

    async def poll(self) -> dict[str, dict]:
        results: dict[str, dict] = {}

        async def _poll_one(symbol: str) -> None:
            s = self._spot_symbol(symbol)
            ticker = await self._get_json(f"{BASE_URL}/api/v3/ticker/24hr?symbol={s}")
            if ticker:
                results[symbol] = {
                    "symbol": symbol,
                    "last": float(ticker.get("lastPrice", 0)),
                    "high": float(ticker.get("highPrice", 0)),
                    "low": float(ticker.get("lowPrice", 0)),
                    "baseVolume": float(ticker.get("volume", 0)),
                }

        await asyncio.gather(*[_poll_one(s) for s in self.symbols])
        return results

    # ── poll klines ───────────────────────────────────────────

    async def poll_klines(self) -> dict[str, dict[str, list[Kline]]]:
        results: dict[str, dict[str, list[Kline]]] = {}

        async def _poll_one(symbol: str) -> None:
            s = self._spot_symbol(symbol)
            try:
                k1m_raw = await self._get_json(f"{BASE_URL}/api/v3/klines?symbol={s}&interval=1m&limit=2")
                k5m_raw = await self._get_json(f"{BASE_URL}/api/v3/klines?symbol={s}&interval=5m&limit=2")
                if k1m_raw is None or k5m_raw is None:
                    return
                results[symbol] = {
                    "1m": [
                        Kline(timestamp=int(k[0]), open=float(k[1]), high=float(k[2]),
                              low=float(k[3]), close=float(k[4]), volume=float(k[5]))
                        for k in k1m_raw
                    ] if k1m_raw else [],
                    "5m": [
                        Kline(timestamp=int(k[0]), open=float(k[1]), high=float(k[2]),
                              low=float(k[3]), close=float(k[4]), volume=float(k[5]))
                        for k in k5m_raw
                    ] if k5m_raw else [],
                }
                self._consecutive_rate_limits = 0
            except Exception:
                logger.exception("Kline poll failed for %s", symbol)

        await asyncio.gather(*[_poll_one(s) for s in self.symbols])
        return results

    # ── public API ────────────────────────────────────────────

    async def fetch_funding_rate(self, symbol: str) -> Optional[dict]:
        """替代 ccxt exchange.fetch_funding_rate()"""
        s = self._spot_symbol(symbol)
        data = await self._get_json(f"{FAPI_URL}/fapi/v1/fundingRate?symbol={s}&limit=1")
        if data and isinstance(data, list) and len(data) > 0:
            return {"fundingRate": data[0].get("fundingRate", "0")}
        return None

    async def fetch_open_interest(self, symbol: str) -> Optional[dict]:
        """替代 ccxt exchange.fetch_open_interest()"""
        s = self._spot_symbol(symbol)
        data = await self._get_json(f"{FAPI_URL}/fapi/v1/openInterest?symbol={s}")
        if data:
            return {
                "openInterestAmount": data.get("openInterest", "0"),
                "timestamp": data.get("time", 0),
            }
        return None

    async def fetch_open_interest_history(
        self, symbol: str, limit: int = 14
    ) -> list[dict]:
        """Fetch Binance 5-minute OI statistics for rolling change calculations."""
        s = self._spot_symbol(symbol)
        data = await self._get_json(
            f"{FAPI_URL}/futures/data/openInterestHist?symbol={s}&period=5m&limit={limit}"
        )
        if not isinstance(data, list):
            return []
        return [
            {
                "timestamp": int(item.get("timestamp", 0) or 0),
                "openInterest": float(item.get("sumOpenInterest", 0) or 0),
                "openInterestValue": float(item.get("sumOpenInterestValue", 0) or 0),
            }
            for item in data
            if item.get("timestamp") and item.get("sumOpenInterest")
        ]
