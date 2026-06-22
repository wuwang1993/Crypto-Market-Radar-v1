"""Alert engine — evaluate, dedup, merge, and format alerts."""

from src.alerts.engine import (
    AlertEvent,
    AlertLevel,
    AlertType,
    evaluate_alerts,
    system_error_alert,
    COOLDOWNS,
)
from src.alerts.dedup import is_in_cooldown, record_alert
from src.alerts.merger import merge_l2_alerts
from src.alerts.templates import format_alert

__all__ = [
    "AlertEvent",
    "AlertLevel",
    "AlertType",
    "evaluate_alerts",
    "system_error_alert",
    "COOLDOWNS",
    "is_in_cooldown",
    "record_alert",
    "merge_l2_alerts",
    "format_alert",
]
