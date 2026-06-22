"""Market state enum definition."""

from enum import Enum


class MarketState(Enum):
    STRONG_UP = "强势上涨"
    WEAK_UP = "弱势上涨"
    RANGE_BIAS_UP = "震荡偏多"
    RANGE = "震荡"
    RANGE_BIAS_DOWN = "震荡偏空"
    WEAK_DOWN = "弱势下跌"
    STRONG_DOWN = "强势下跌"
    BREAKOUT_UP = "放量突破"
    BREAKDOWN = "放量下破"
    TOP_STALL = "高位滞涨"
    BOTTOM_STABILIZE = "低位止跌"
    BUY_STRENGTHEN = "买盘增强"
    SELL_STRENGTHEN = "卖盘增强"
    ABNORMAL = "异常波动"
    NORMAL = "正常波动"
