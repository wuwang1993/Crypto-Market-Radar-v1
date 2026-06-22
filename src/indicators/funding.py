"""Funding rate and open interest indicators."""

from src.exchange.adapter import SymbolState


def compute_funding(state: SymbolState) -> dict:
    fr = state.funding_rate
    oi = state.open_interest
    long_5m, short_5m = state.liquidation_buffer.totals(5)
    long_15m, short_15m = state.liquidation_buffer.totals(15)
    long_1h, short_1h = state.liquidation_buffer.totals(60)
    return {
        "funding_rate": fr if fr is not None else None,
        "funding_is_high": (fr > 0.0008) if fr is not None else False,
        "funding_is_extreme": (fr > 0.0010) if fr is not None else False,
        "funding_is_negative_extreme": (fr < -0.0005) if fr is not None else False,
        "oi": oi if oi is not None else None,
        "oi_change_5m": state.oi_buffer.change_pct(5),
        "oi_change_15m": state.oi_buffer.change_pct(15),
        "oi_change_1h": state.oi_buffer.change_pct(60),
        "liquidation_long_5m": long_5m,
        "liquidation_short_5m": short_5m,
        "liquidation_long_15m": long_15m,
        "liquidation_short_15m": short_15m,
        "liquidation_long_1h": long_1h,
        "liquidation_short_1h": short_1h,
    }
