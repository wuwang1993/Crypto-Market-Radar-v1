"""Indicator calculation engine — one pure function per module."""

from dataclasses import dataclass, field
from typing import Optional

from src.exchange.adapter import SymbolState
from src.indicators.returns import compute_returns
from src.indicators.volume import compute_volume
from src.indicators.trades import compute_trades
from src.indicators.vwap import compute_vwap
from src.indicators.ma import compute_ma
from src.indicators.rsi import compute_rsi
from src.indicators.depth import compute_depth
from src.indicators.funding import compute_funding


@dataclass
class IndicatorSnapshot:
    symbol: str
    price: float = 0.0
    # returns
    ret_1m: Optional[float] = None
    ret_5m: Optional[float] = None
    ret_15m: Optional[float] = None
    ret_1h: Optional[float] = None
    # volume
    vol_5m_current: float = 0.0
    vol_5m_avg: Optional[float] = None
    volume_amplify: Optional[float] = None
    # trades
    buy_volume: float = 0.0
    sell_volume: float = 0.0
    buy_sell_ratio: float = 1.0
    cvd_1m: float = 0.0
    cvd_direction: str = "flat"
    # vwap
    vwap: Optional[float] = None
    # ma
    ema20: Optional[float] = None
    ema60: Optional[float] = None
    # rsi
    rsi6: Optional[float] = None
    rsi14: Optional[float] = None
    # depth
    depth_ratio: Optional[float] = None
    spread: Optional[float] = None
    spread_pct: Optional[float] = None
    bid_wall: Optional[float] = None
    ask_wall: Optional[float] = None
    # funding
    funding_rate: Optional[float] = None
    funding_is_high: bool = False
    funding_is_extreme: bool = False
    funding_is_negative_extreme: bool = False
    oi: Optional[float] = None
    oi_change_5m: Optional[float] = None
    oi_change_15m: Optional[float] = None
    oi_change_1h: Optional[float] = None
    liquidation_long_5m: float = 0.0
    liquidation_short_5m: float = 0.0
    liquidation_long_15m: float = 0.0
    liquidation_short_15m: float = 0.0
    liquidation_long_1h: float = 0.0
    liquidation_short_1h: float = 0.0


def get_indicator_value(snapshot: IndicatorSnapshot, field: str, default=0):
    """Return snapshot attribute value or default."""
    return getattr(snapshot, field, default)


def compute_all(symbol: str, state: SymbolState) -> IndicatorSnapshot:
    """Compute all indicators and return a snapshot."""
    snap = IndicatorSnapshot(symbol=symbol)
    snap.price = state.price
    snap.__dict__.update(compute_returns(state))
    snap.__dict__.update(compute_volume(state))
    snap.__dict__.update(compute_trades(state))
    snap.__dict__.update(compute_ma(state))
    snap.vwap = compute_vwap(state)
    rsi = compute_rsi(state)
    if rsi:
        snap.__dict__.update(rsi)
    depth = compute_depth(state)
    if depth:
        snap.__dict__.update(depth)
    funding = compute_funding(state)
    if funding:
        snap.__dict__.update(funding)
    return snap
