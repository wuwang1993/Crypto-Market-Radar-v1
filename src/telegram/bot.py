import asyncio
import logging
import os
from pathlib import Path

from telegram import Bot
from telegram.ext import Application
from telegram.error import TelegramError

logger = logging.getLogger(__name__)

TOKEN_PATH = Path(
    os.environ.get("TG_BOT_TOKEN_FILE", "/etc/crypto-market-radar/tg_bot_token.txt")
)
MAX_RETRIES = 2
RETRY_BASE_DELAY = 1.0  # seconds


def _read_token(token_path: Path) -> str:
    """Read bot token from file, stripping whitespace."""
    if not token_path.exists():
        raise FileNotFoundError(f"Token file not found: {token_path}")
    return token_path.read_text().strip()


class RadarBot:
    """Manages Telegram bot lifecycle and message sending."""

    def __init__(self) -> None:
        self._token: str = _read_token(TOKEN_PATH)
        self._chat_id: str = self._load_chat_id()
        self._app: Application | None = None
        self._bot: Bot | None = None
        self.alert_count: int = 0
        self.ws_connected: bool = False

    @staticmethod
    def _load_chat_id() -> str:
        import os
        chat_id = os.environ.get("TG_CHAT_ID", "")
        if not chat_id:
            raise RuntimeError("TG_CHAT_ID environment variable is not set")
        return chat_id

    @property
    def app(self) -> Application | None:
        return self._app

    @property
    def bot(self) -> Bot | None:
        return self._bot

    @property
    def chat_id(self) -> str:
        return self._chat_id

    async def start(self) -> None:
        """Build and initialize the Application (polling deferred to start_polling)."""
        self._app = (
            Application.builder()
            .token(self._token)
            .build()
        )
        self._bot = self._app.bot
        await self._app.initialize()
        logger.info("RadarBot initialized (chat_id=%s)", self._chat_id)

    async def start_polling(self) -> None:
        """Start Telegram polling (call after warmup to avoid PTB blocking warmup)."""
        if self._app is not None:
            if self._app.updater is None:
                raise RuntimeError("Telegram updater is not available")
            await self._app.updater.start_polling()
            await self._app.start()
            logger.info("RadarBot polling started")

    async def stop(self) -> None:
        """Shutdown the application gracefully."""
        if self._app is not None:
            try:
                if self._app.updater is not None and self._app.updater.running:
                    await self._app.updater.stop()
                await self._app.stop()
            except Exception:
                logger.exception("Failed to stop RadarBot cleanly")
            await self._app.shutdown()
            logger.info("RadarBot stopped")

    async def send_message(
        self,
        text: str,
        parse_mode: str = "MarkdownV2",
    ) -> bool:
        """Send a text message to the configured chat, with retries.

        Returns True on success, False after all retries exhausted.
        """
        if self._bot is None:
            logger.error("Bot not initialized; cannot send message")
            return False

        for attempt in range(MAX_RETRIES + 1):
            try:
                await self._bot.send_message(
                    chat_id=self._chat_id,
                    text=text,
                    parse_mode=parse_mode,
                )
                return True
            except TelegramError as exc:
                if attempt < MAX_RETRIES:
                    delay = RETRY_BASE_DELAY * (2 ** attempt)
                    logger.warning(
                        "send_message failed (attempt %d/%d), retrying in %.1fs: %s",
                        attempt + 1, MAX_RETRIES + 1, delay, exc,
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(
                        "send_message failed after %d retries: %s",
                        MAX_RETRIES + 1, exc,
                    )
        return False
