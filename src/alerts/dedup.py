"""SQLite-based alert deduplication with cooldown window."""

import sqlite3
from pathlib import Path

from src.alerts.engine import AlertEvent, AlertType

import os
DB_PATH = Path(os.environ.get("RADAR_DB_PATH", str(Path(__file__).resolve().parent.parent.parent / "data" / "radar.db")))


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_table(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS alert_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            alert_type TEXT NOT NULL,
            level TEXT NOT NULL,
            price REAL,
            message TEXT,
            triggered_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_alert_dedup "
        "ON alert_log(symbol, alert_type, triggered_at)"
    )
    conn.commit()


def is_in_cooldown(symbol: str, alert_type: AlertType, cooldown_seconds: int) -> bool:
    """True if same symbol+type alert fired within cooldown window."""
    if alert_type is None:
        return False
    conn = _get_conn()
    _ensure_table(conn)
    cur = conn.execute(
        "SELECT 1 FROM alert_log "
        "WHERE symbol=? AND alert_type=? "
        "AND triggered_at > datetime('now', ?) LIMIT 1",
        (symbol, alert_type.value, f"-{cooldown_seconds} seconds"),
    )
    exists = cur.fetchone() is not None
    conn.close()
    return exists


def record_alert(event: AlertEvent) -> None:
    """Persist an alert event for dedup tracking."""
    conn = _get_conn()
    _ensure_table(conn)
    conn.execute(
        "INSERT INTO alert_log (symbol, alert_type, level, price, message) "
        "VALUES (?,?,?,?,?)",
        (event.symbol, event.alert_type.value if event.alert_type else "",
         event.level.value, event.price, event.message),
    )
    conn.commit()
    conn.close()
