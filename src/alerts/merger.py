"""Alert merger — combine ≥3 L2 alerts into one summary batch."""

from typing import List

from src.alerts.engine import AlertEvent, AlertLevel


_LABELS = {
    "fast_up": "快速上涨",
    "fast_down": "快速下跌",
    "buy_pressure": "买盘增强",
    "sell_pressure": "卖盘增强",
    "breakout_up": "放量突破",
    "breakdown": "放量下破",
}


def merge_l2_alerts(alerts: List[AlertEvent]) -> List[AlertEvent]:
    """If ≥3 L2 alerts in the same batch, merge into a single summary event.

    L3/L4 alerts always pass through.  Individual L2 alerts with <3 total
    are returned unchanged.
    """
    l2 = [a for a in alerts if a.level == AlertLevel.L2]
    others = [a for a in alerts if a.level != AlertLevel.L2]

    if len(l2) < 3:
        return alerts

    details = []
    for alert in l2:
        label = _LABELS.get(alert.alert_type.value, alert.alert_type.value)
        details.append(f"{alert.symbol}｜{label}｜{alert.message}")
    msg = "\n".join(details + [f"共 {len(l2)} 个币对触发重要提醒"])
    merged = AlertEvent(
        symbol="MULTI",
        alert_type=None,
        level=AlertLevel.L2,
        price=0.0,
        message=msg,
        cooldown_seconds=60,
    )
    return [merged] + others
