import asyncio
from types import SimpleNamespace

import pytest

from src.alerts.engine import AlertType, evaluate_alerts
from src.alerts.templates import format_alert
from src.alerts.dedup import DB_PATH
from src.cache.kline_buffer import Kline, KlineBuffer
from src.cache.trade_buffer import Trade, TradeBuffer
from src.cache.derivatives_buffer import LiquidationBuffer, OpenInterestBuffer
from src.exchange.adapter import SymbolState
from src.exchange.binance_liquidation_ws import BinanceLiquidationWS
from src.indicators import IndicatorSnapshot, compute_all
from src.indicators.funding import compute_funding
from src.notifier import Notifier
from src.scheduler.jobs import SUMMARY_INTERVAL_MINUTES, SummaryScheduler
from src.state.state_types import MarketState
from src.telegram.bot import RadarBot
from src.telegram.commands import cmd_summary, setup_commands


def test_kline_buffer_refreshes_current_candle_without_duplicates() -> None:
    buffer = KlineBuffer()
    buffer.add_5m(Kline(1000, 1, 2, 0.5, 1.5, 10))
    buffer.add_5m(Kline(1000, 1, 3, 0.5, 2.5, 25))

    assert len(buffer.klines_5m) == 1
    assert buffer.latest_5m is not None
    assert buffer.latest_5m.close == 2.5
    assert buffer.latest_5m.volume == 25


def test_compute_all_copies_live_price_to_snapshot() -> None:
    state = SymbolState("BTC/USDT", price=62_500.0)
    snapshot = compute_all(state.symbol, state)

    assert snapshot.price == 62_500.0


def test_buy_pressure_can_trigger_with_live_price() -> None:
    snapshot = IndicatorSnapshot(
        symbol="BTC/USDT",
        price=101.0,
        vwap=100.0,
        buy_sell_ratio=2.0,
        cvd_direction="up",
    )

    alerts = evaluate_alerts(snapshot, MarketState.NORMAL)

    assert AlertType.BUY_PRESSURE in {alert.alert_type for alert in alerts}


def test_alert_template_contains_trigger_evidence_and_guidance() -> None:
    snapshot = IndicatorSnapshot(
        symbol="BTC/USDT",
        price=104_800.0,
        ret_5m=1.24,
        ret_15m=2.08,
        volume_amplify=2.3,
        buy_sell_ratio=1.86,
        cvd_direction="up",
        depth_ratio=1.7,
    )

    alert = evaluate_alerts(snapshot, MarketState.STRONG_UP)[0]
    message = format_alert(alert)

    assert "快速上涨提醒" in message
    assert "15m涨跌" in message
    assert "成交量" in message
    assert "买卖量比" in message
    assert "系统判断" in message
    assert "操作提示" in message
    assert alert.snapshot is snapshot
    assert alert.market_state is MarketState.STRONG_UP


def test_summary_interval_matches_design_document() -> None:
    assert SUMMARY_INTERVAL_MINUTES == 15


def test_funding_thresholds_use_binance_decimal_units() -> None:
    state = SymbolState("BTC/USDT", funding_rate=0.0011)
    result = compute_funding(state)

    assert result["funding_is_high"] is True
    assert result["funding_is_extreme"] is True


def test_open_interest_buffer_calculates_rolling_changes() -> None:
    buffer = OpenInterestBuffer()
    base = 1_700_000_000_000
    for index, value in enumerate((100.0, 102.0, 104.0, 106.0, 110.0)):
        buffer.add(base + index * 5 * 60_000, value)

    assert buffer.change_pct(5) == pytest.approx((110 / 106 - 1) * 100)
    assert buffer.change_pct(15) == pytest.approx((110 / 102 - 1) * 100)
    assert buffer.change_pct(60) is None


def test_liquidation_buffer_aggregates_sides_and_expires_old_buckets() -> None:
    buffer = LiquidationBuffer()
    now = 1_700_000_000_000
    buffer.add(now - 4 * 60_000, "long", 600_000)
    buffer.add(now - 2 * 60_000, "short", 100_000)
    buffer.add(now - 20 * 60_000, "long", 900_000)

    assert buffer.totals(5, now) == pytest.approx((600_000, 100_000))
    assert buffer.totals(15, now) == pytest.approx((600_000, 100_000))


def test_liquidation_stream_maps_sell_force_order_to_long_liquidation() -> None:
    received = []
    stream = BinanceLiquidationWS(["BTC/USDT"])

    async def capture(symbol: str, event: dict) -> None:
        received.append((symbol, event))

    stream.on_liquidation = capture
    asyncio.run(stream._dispatch({
        "data": {
            "e": "forceOrder",
            "E": 1_700_000_000_100,
            "o": {
                "s": "BTCUSDT", "S": "SELL", "q": "2", "z": "1.5",
                "p": "100", "ap": "101", "T": 1_700_000_000_000,
            },
        }
    }))

    assert received[0][0] == "BTC/USDT"
    assert received[0][1]["side"] == "long"
    assert received[0][1]["notional_usdt"] == pytest.approx(151.5)


def test_contract_alert_uses_oi_change_and_liquidation_evidence() -> None:
    snapshot = IndicatorSnapshot(
        symbol="BTC/USDT",
        price=100_000,
        ret_15m=1.8,
        funding_rate=0.00085,
        oi=100_000,
        oi_change_15m=6.4,
        liquidation_short_5m=800_000,
        liquidation_short_15m=1_200_000,
        liquidation_short_1h=2_000_000,
    )

    alerts = evaluate_alerts(snapshot, MarketState.STRONG_UP)
    alert_types = {alert.alert_type for alert in alerts}

    assert AlertType.LONG_CROWDED in alert_types
    assert AlertType.SHORT_LIQUIDATION in alert_types
    crowded = next(alert for alert in alerts if alert.alert_type is AlertType.LONG_CROWDED)
    message = format_alert(crowded)
    assert "15m OI变化" in message
    assert "已观测空单强平" in message


def test_trade_buffer_builds_cvd_direction_from_minute_buckets() -> None:
    buffer = TradeBuffer()
    for minute, quantity in ((100, 1.0), (101, 2.0), (102, 3.0), (103, 1.0)):
        buffer.add(Trade(minute * 60_000, 100.0, quantity, False))

    assert buffer.cvd_direction == "up"


def test_scheduler_escapes_markdown_v2_reserved_characters() -> None:
    state = SymbolState("BTC/USDT", price=100.0)
    cache = SimpleNamespace(
        items=lambda: [(state.symbol, state)],
        keys=lambda: [state.symbol],
    )
    scheduler = SummaryScheduler(
        SimpleNamespace(cache=cache),
        SimpleNamespace(),
        SimpleNamespace(alert_count=0),
    )

    assert "\\|" in scheduler._build_summary()
    assert "\\-" in scheduler._build_daily()


def test_notifier_raises_when_sender_returns_false() -> None:
    async def rejected(*args: object, **kwargs: object) -> bool:
        return False

    with pytest.raises(RuntimeError, match="rejected"):
        asyncio.run(Notifier(rejected).send_summary("test"))


def test_radar_bot_starts_and_stops_real_updater() -> None:
    calls: list[str] = []

    class Updater:
        running = False

        async def start_polling(self) -> None:
            calls.append("updater.start")
            self.running = True

        async def stop(self) -> None:
            calls.append("updater.stop")
            self.running = False

    class App:
        updater = Updater()

        async def start(self) -> None:
            calls.append("app.start")

        async def stop(self) -> None:
            calls.append("app.stop")

        async def shutdown(self) -> None:
            calls.append("app.shutdown")

    bot = RadarBot.__new__(RadarBot)
    bot._app = App()

    async def lifecycle() -> None:
        await bot.start_polling()
        await bot.stop()

    asyncio.run(lifecycle())

    assert calls == [
        "updater.start",
        "app.start",
        "updater.stop",
        "app.stop",
        "app.shutdown",
    ]


def test_summary_command_uses_live_provider() -> None:
    replies: list[str] = []

    class Message:
        async def reply_text(self, text: str, **kwargs: object) -> None:
            replies.append(text)

    update = SimpleNamespace(message=Message())
    context = SimpleNamespace(
        application=SimpleNamespace(bot_data={"summary_provider": lambda: "live summary"})
    )

    asyncio.run(cmd_summary(update, context))

    assert replies == ["live summary"]


def test_command_handlers_reject_other_chat_ids() -> None:
    handlers: list[object] = []
    app = SimpleNamespace(bot_data={}, add_handler=handlers.append)
    setup_commands(app, "123")
    callback = handlers[0].callback
    update = SimpleNamespace(effective_chat=SimpleNamespace(id=999))
    context = SimpleNamespace(application=app)

    asyncio.run(callback(update, context))

    assert app.bot_data["allowed_chat_id"] == "123"


def test_alert_command_uses_configured_database_path() -> None:
    assert str(DB_PATH)
