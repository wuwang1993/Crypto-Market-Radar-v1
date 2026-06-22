"""Scheduled market summary, movers, daily status, and heartbeat jobs."""

import asyncio
import logging
import time
from datetime import datetime, timedelta

from src.exchange.adapter import ExchangeAdapter
from src.indicators import IndicatorSnapshot, compute_all
from src.state.engine import evaluate_state
from src.state.state_types import MarketState
from src.telegram.formatter import escape_markdown, format_pct

logger = logging.getLogger(__name__)
SUMMARY_INTERVAL_MINUTES = 15

STATE_LABELS: dict[MarketState, str] = {
    MarketState.STRONG_UP: "强势上涨",
    MarketState.WEAK_UP: "弱势上涨",
    MarketState.RANGE_BIAS_UP: "震荡偏多",
    MarketState.RANGE: "震荡",
    MarketState.RANGE_BIAS_DOWN: "震荡偏空",
    MarketState.WEAK_DOWN: "弱势下跌",
    MarketState.STRONG_DOWN: "强势下跌",
    MarketState.BREAKOUT_UP: "放量突破",
    MarketState.BREAKDOWN: "放量下破",
    MarketState.TOP_STALL: "高位滞涨",
    MarketState.BOTTOM_STABILIZE: "低位止跌",
    MarketState.BUY_STRENGTHEN: "买盘增强",
    MarketState.SELL_STRENGTHEN: "卖盘增强",
    MarketState.ABNORMAL: "异常波动",
    MarketState.NORMAL: "正常波动",
}


class SummaryScheduler:
    """Manage periodic summary, movers, daily-report, and heartbeat tasks."""

    def __init__(self, exchange: ExchangeAdapter, notifier, bot) -> None:
        self._exchange = exchange
        self._notifier = notifier
        self._bot = bot
        self._today_alerts = 0
        self._alert_counter: dict[str, int] = {}
        self._summary_task: asyncio.Task | None = None
        self._heatmap_task: asyncio.Task | None = None
        self._daily_task: asyncio.Task | None = None
        self._heartbeat_task: asyncio.Task | None = None
        self._running = False
        self._started_at = time.monotonic()

    def record_alert(self, symbol: str) -> None:
        self._today_alerts += 1
        self._alert_counter[symbol] = self._alert_counter.get(symbol, 0) + 1
        if hasattr(self._bot, "alert_count"):
            self._bot.alert_count = self._today_alerts

    async def start(self) -> None:
        self._running = True
        self._summary_task = asyncio.create_task(self._summary_loop())
        self._heatmap_task = asyncio.create_task(self._heatmap_loop())
        self._daily_task = asyncio.create_task(self._daily_loop())
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        logger.info("Scheduler started (summary/movers/daily/heartbeat)")

    async def stop(self) -> None:
        self._running = False
        tasks = (
            self._summary_task,
            self._heatmap_task,
            self._daily_task,
            self._heartbeat_task,
        )
        for task in tasks:
            if task:
                task.cancel()
        active = [task for task in tasks if task]
        if active:
            await asyncio.gather(*active, return_exceptions=True)
        logger.info("Scheduler stopped")

    async def _summary_loop(self) -> None:
        while self._running:
            await asyncio.sleep(SUMMARY_INTERVAL_MINUTES * 60)
            if not self._running:
                break
            try:
                await self._notifier.send_summary(self._build_summary())
            except Exception:
                logger.exception("Summary generation failed")

    def _snapshots(self) -> list[tuple[str, IndicatorSnapshot, MarketState]]:
        snapshots = []
        for symbol, state in self._exchange.cache.items():
            snap = compute_all(symbol, state)
            market_state, _ = evaluate_state(snap)
            snapshots.append((symbol, snap, market_state))
        return snapshots

    def _build_summary(self) -> str:
        now = datetime.now().strftime("%H:%M")
        lines = [f"📊 *市场摘要* {now}", ""]
        snapshots = self._snapshots()
        snapshots.sort(key=lambda item: abs(item[1].ret_5m or 0), reverse=True)

        for symbol, snap, market_state in snapshots:
            lines.extend([
                f"*{escape_markdown(symbol)}*",
                escape_markdown(f"价格：{self._format_price(snap.price)}"),
                escape_markdown(
                    f"5m：{format_pct(snap.ret_5m or 0)} | "
                    f"15m：{format_pct(snap.ret_15m or 0)} | "
                    f"1h：{format_pct(snap.ret_1h or 0)}"
                ),
                escape_markdown(f"成交量：{self._volume_label(snap.volume_amplify)}"),
                escape_markdown(f"买卖量比：{snap.buy_sell_ratio:.2f}"),
                escape_markdown(f"状态：{STATE_LABELS.get(market_state, '未知')}"),
                "",
            ])

        lines.extend(["*整体判断*", escape_markdown(self._overall_view(snapshots))])
        return "\n".join(lines)

    @staticmethod
    def _format_price(price: float) -> str:
        if price <= 0:
            return "暂无数据"
        if price >= 100:
            return f"{price:,.2f}"
        if price >= 1:
            return f"{price:,.4f}".rstrip("0").rstrip(".")
        return f"{price:.8f}".rstrip("0").rstrip(".")

    @staticmethod
    def _volume_label(amplify: float | None) -> str:
        if amplify is None:
            return "数据不足"
        if amplify < 0.8:
            return f"缩量 {amplify:.1f} 倍"
        if amplify <= 1.2:
            return f"正常 {amplify:.1f} 倍"
        return f"放大 {amplify:.1f} 倍"

    @staticmethod
    def _overall_view(
        snapshots: list[tuple[str, IndicatorSnapshot, MarketState]],
    ) -> str:
        if not snapshots:
            return "实时行情尚未就绪。"
        bullish = {
            MarketState.STRONG_UP,
            MarketState.WEAK_UP,
            MarketState.RANGE_BIAS_UP,
            MarketState.BREAKOUT_UP,
            MarketState.BUY_STRENGTHEN,
        }
        bearish = {
            MarketState.STRONG_DOWN,
            MarketState.WEAK_DOWN,
            MarketState.RANGE_BIAS_DOWN,
            MarketState.BREAKDOWN,
            MarketState.SELL_STRENGTHEN,
        }
        parts = []
        for symbol, _snap, market_state in snapshots:
            name = symbol.split("/")[0]
            if market_state in bullish:
                view = "偏强"
            elif market_state in bearish:
                view = "偏弱"
            else:
                view = STATE_LABELS.get(market_state, "方向不明")
            parts.append(f"{name} {view}")
        return "，".join(parts) + "。"

    async def _heatmap_loop(self) -> None:
        while self._running:
            await asyncio.sleep(60 * 60)
            if not self._running:
                break
            try:
                message = self._build_heatmap()
                if message:
                    await self._notifier.send_heatmap(message)
            except Exception:
                logger.exception("Movers generation failed")
            self._alert_counter.clear()

    def _build_heatmap(self) -> str | None:
        snapshots = [(symbol, snap) for symbol, snap, _state in self._snapshots()]
        if not snapshots:
            return None
        now = datetime.now().strftime("%H:%M")
        lines = [f"🔥 *1小时市场异动榜* {now}", ""]
        gainers = sorted(snapshots, key=lambda item: item[1].ret_1h or 0, reverse=True)[:3]
        losers = sorted(snapshots, key=lambda item: item[1].ret_1h or 0)[:3]
        buyers = sorted(snapshots, key=lambda item: item[1].buy_sell_ratio, reverse=True)[:3]
        sellers = sorted(snapshots, key=lambda item: item[1].buy_sell_ratio)[:3]
        lines.extend(self._rank_lines("涨幅较强", gainers, show_return=True))
        lines.extend(self._rank_lines("跌幅较强", losers, show_return=True))
        lines.extend(self._rank_lines("买盘增强", buyers, show_return=False))
        lines.extend(self._rank_lines("卖盘增强", sellers, show_return=False))
        return "\n".join(lines).rstrip()

    @staticmethod
    def _rank_lines(
        title: str,
        items: list[tuple[str, IndicatorSnapshot]],
        *,
        show_return: bool,
    ) -> list[str]:
        lines = [f"*{escape_markdown(title)}*"]
        for index, (symbol, snap) in enumerate(items, 1):
            if show_return:
                value = f"{format_pct(snap.ret_1h or 0)} | 买卖比 {snap.buy_sell_ratio:.2f}"
            else:
                value = f"买卖比 {snap.buy_sell_ratio:.2f} | 1h {format_pct(snap.ret_1h or 0)}"
            lines.append(escape_markdown(f"{index}. {symbol} {value}"))
        lines.append("")
        return lines

    async def _daily_loop(self) -> None:
        while self._running:
            now = datetime.now()
            target = now.replace(hour=9, minute=0, second=0, microsecond=0)
            if now >= target:
                target += timedelta(days=1)
            await asyncio.sleep((target - now).total_seconds())
            if not self._running:
                break
            try:
                await self._notifier.send_daily(self._build_daily())
            except Exception:
                logger.exception("Daily report failed")
            self._today_alerts = 0
            self._bot.alert_count = 0

    def _build_daily(self) -> str:
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        uptime_seconds = max(0, int(time.monotonic() - self._started_at))
        hours, remainder = divmod(uptime_seconds, 3600)
        minutes = remainder // 60
        connected = bool(getattr(self._exchange, "connected", False))
        derivatives_connected = bool(
            getattr(self._exchange, "derivatives_connected", False)
        )
        fallback = bool(getattr(self._exchange, "fallback_mode", False))
        connection = "正常" if connected else ("REST 降级" if fallback else "断开")
        current = time.monotonic()
        delays = [
            max(0.0, current - state.last_update)
            for _symbol, state in self._exchange.cache.items()
            if getattr(state, "last_update", 0.0) > 0
        ]
        delay_text = f"{max(delays):.1f} 秒" if delays else "暂无数据"
        status = "正常" if connected or fallback else "连接异常"
        return "\n".join([
            f"🧭 *系统状态日报* {escape_markdown(now)}",
            "",
            escape_markdown(f"运行状态：{status}"),
            escape_markdown(f"运行时长：{hours}小时{minutes}分钟"),
            f"监控币对: `{len(list(self._exchange.cache.keys()))}`",
            f"今日告警总数: `{self._today_alerts}`",
            f"TG推送失败: `{getattr(self._notifier, 'failure_count', 0)}`",
            escape_markdown(f"交易所连接：{connection}"),
            escape_markdown(
                f"合约强平流：{'正常' if derivatives_connected else '断开'}"
            ),
            escape_markdown(f"最大数据延迟：{delay_text}"),
            r"系统版本: `v1\.0\.0`",
        ])

    async def _heartbeat_loop(self) -> None:
        while self._running:
            await asyncio.sleep(2 * 60 * 60)
            if not self._running:
                break
            try:
                message = (
                    f"🟢 系统正常 · 监控 {len(list(self._exchange.cache.keys()))} 币对 · "
                    f"今日告警 {self._today_alerts}"
                )
                await self._notifier.send_heartbeat(message)
            except Exception:
                logger.exception("Heartbeat failed")
