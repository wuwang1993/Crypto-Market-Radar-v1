#!/bin/bash
cd /srv/crypto-market-radar
export TG_CHAT_ID=5915093313
export TG_BOT_TOKEN_FILE=/etc/crypto-market-radar/tg_bot_token.txt
export RADAR_DB_PATH=/var/lib/crypto-market-radar/radar.db
exec .venv/bin/python -m src.main
