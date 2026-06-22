from collections.abc import Callable, Awaitable

from src.alerts.engine import AlertEvent, system_error_alert
from src.alerts.templates import format_alert
from src.telegram.formatter import startup_message, warmup_done_message

SendFn = Callable[..., Awaitable[object]]


class Notifier:
    def __init__(self, send_fn: SendFn) -> None:
        self._send = send_fn
        self.failure_count = 0

    async def _send_checked(self, text: str, **kwargs: object) -> None:
        try:
            result = await self._send(text, **kwargs)
            if result is False:
                raise RuntimeError("Telegram rejected the message after all retries")
        except Exception:
            self.failure_count += 1
            raise

    async def send_startup(self, symbol_count: int) -> None:
        await self._send_checked(startup_message())

    async def send_warmup_done(self, symbol_count: int, warmup_seconds: float) -> None:
        await self._send_checked(warmup_done_message(symbol_count, warmup_seconds))

    async def send_alert(self, alert: AlertEvent) -> None:
        await self._send_checked(format_alert(alert))

    async def send_system_error(self, symbol: str, error_msg: str) -> None:
        await self._send_checked(format_alert(system_error_alert(symbol, error_msg)))

    async def send_summary(self, text: str) -> None:
        await self._send_checked(text)

    async def send_heatmap(self, text: str | None) -> None:
        if text is not None:
            await self._send_checked(text)

    async def send_daily(self, text: str) -> None:
        await self._send_checked(text)

    async def send_heartbeat(self, text: str) -> None:
        await self._send_checked(text, parse_mode=None)
