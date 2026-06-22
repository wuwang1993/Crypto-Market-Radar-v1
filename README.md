# Crypto Market Radar v1

一个使用 Python 构建的 24×7 加密市场监控与 Telegram 提醒机器人。它从 Binance 获取现货与合约市场数据，计算成交量、主动买卖、CVD、VWAP、均线、RSI、盘口和衍生品指标，并在市场出现明显异动时发送提醒。

> 本仓库是第一版公开版本，只提供行情监控和风险提醒，不会自动下单，也不构成投资建议。

## 主要功能

- 默认监控 BTC、ETH、SOL、BNB、DOGE、XRP 的 USDT 币对。
- WebSocket 接收 ticker、聚合成交、盘口和强平数据。
- REST 负责历史预热、K 线补充、资金费率与持仓量更新。
- 计算涨跌幅、成交量放大、买卖量比、CVD、VWAP、EMA、RSI 和盘口深度。
- 识别快速涨跌、买卖盘增强、放量突破、背离、合约拥挤和异常波动。
- Telegram 实时告警、15 分钟摘要、小时异动榜和系统状态消息。
- SQLite 告警冷却与去重，避免重复刷屏。
- WebSocket 断线重连、REST 降级、数据延迟检查和 systemd 常驻运行。

## 工作流程

```text
Binance WebSocket / REST
          ↓
Exchange Adapter
          ↓
行情缓存与指标计算
          ↓
市场状态与告警规则
          ↓
冷却、去重与合并
          ↓
Telegram 推送
```

## 环境要求

- Python 3.10 或更高版本
- Telegram Bot Token 与目标 Chat ID
- 可访问 Binance 和 Telegram API 的网络环境
- Linux 部署建议使用 systemd

## 快速开始

```bash
git clone https://github.com/wuwang1993/Crypto-Market-Radar-v1.git
cd Crypto-Market-Radar-v1

python -m venv .venv
source .venv/bin/activate
pip install -e .
```

Windows PowerShell 激活虚拟环境：

```powershell
.\.venv\Scripts\Activate.ps1
```

将 Telegram Bot Token 单独保存到文件，禁止提交到 Git：

```bash
mkdir -p data
printf '%s\n' 'YOUR_TELEGRAM_BOT_TOKEN' > data/tg_bot_token.txt
chmod 600 data/tg_bot_token.txt
```

配置环境变量并启动：

```bash
export TG_CHAT_ID='YOUR_CHAT_ID'
export TG_BOT_TOKEN_FILE="$PWD/data/tg_bot_token.txt"
export RADAR_DB_PATH="$PWD/data/radar.db"

python -m src.main
```

可参考 [.env.example](.env.example)。当前第一版的监控币对和大部分告警阈值仍在代码中定义，YAML 配置模块尚未完整接入运行入口。

## Telegram 命令

| 命令 | 作用 |
|---|---|
| `/status` | 查看运行时间、WebSocket 和告警状态 |
| `/summary` | 获取当前市场摘要 |
| `/watch` | 查看监控币对 |
| `/alerts` | 查看最近告警 |
| `/reload` | 配置重载占位命令 |
| `/help` | 查看命令帮助 |

## 测试

```bash
pip install pytest
python -m pytest -q
python -m compileall -q src
```

公开版本上传前的测试结果：

```text
17 passed
```

## Linux 服务部署

仓库提供 [systemd/crypto-radar.service](systemd/crypto-radar.service)。服务默认使用：

- 项目目录：`/srv/crypto-market-radar`
- 配置环境文件：`/etc/crypto-market-radar/crypto-radar.env`
- Token 文件：`/etc/crypto-market-radar/tg_bot_token.txt`
- SQLite：`/var/lib/crypto-market-radar/radar.db`

生产环境应确保 Token 文件仅服务账号可读，并在启动前创建 `cryptoradar` 用户及可写数据库目录。

## 项目结构

```text
src/
├── exchange/     # Binance WebSocket / REST 适配
├── cache/        # K线、成交和衍生品窗口缓存
├── indicators/   # 技术指标与订单流指标
├── state/        # 市场状态评分
├── alerts/       # 告警规则、模板、去重和合并
├── scheduler/    # 摘要、榜单、日报与心跳
├── telegram/     # Telegram Bot 与命令
└── main.py       # 程序入口
```

## 风险与限制

- 提醒信号不等于确定的交易机会，不保证盈利。
- 盘口挂单可以撤销，不能单独作为交易依据。
- WebSocket 断线、REST 限流和网络延迟可能造成数据缺口。
- 阈值是通用初始值，不同币种和市场阶段可能需要重新校准。
- 本项目不包含自动下单、仓位管理、回测证明或生产收益承诺。

请先在模拟或观察模式下验证，并自行承担交易决策风险。
