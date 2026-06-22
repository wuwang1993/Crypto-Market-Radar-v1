# SPEC: 用轻量 aiohttp WebSocket 替代 ccxt.pro（内存降至 150MB）

## 目标
替换 ccxt.pro 为 aiohttp 直连 Binance WebSocket + REST，内存从 ~680MB 降至 ~150MB。

## 技术方案

### 1. WS 架构：单连接 Multiplex
Binance 支持单 WebSocket 连接承载多 stream：
```
wss://stream.binance.com:9443/stream?streams=btcusdt@ticker/btcusdt@aggTrade/btcusdt@depth20@100ms/ethusdt@ticker/...
```
6 symbols × 3 streams = 18+ 流，全在 **1 个 WebSocket 连接** 中（之前 ccxt 可能创建多个连接）。

### 2. REST 替换
用 aiohttp 直接调 Binance REST API 替代 ccxt.py REST：
- K 线历史: `GET /api/v3/klines?symbol=BTCUSDT&interval=5m&limit=20`
- 24h Ticker: `GET /api/v3/ticker/24hr?symbol=BTCUSDT`
- 资金费率: `GET /fapi/v1/fundingRate?symbol=BTCUSDT`（合约）
- 持仓量: `GET /fapi/v1/openInterest?symbol=BTCUSDT`（合约）

### 3. 保持对外接口不变
- `ExchangeAdapter` 的 `.cache`, `.start()`, `.stop()`, `.warmup()`, `.fallback_mode` — 不变
- `BinanceWS` 的 `.on_ticker`, `.on_trade`, `.on_depth`, `.connected`, `.connect()`, `.disconnect()` — 签名不变
- `BinanceREST` 的 `.warmup()`, `.poll()`, `.poll_klines()` — 签名不变
- `SymbolState`, `KlineBuffer`, `TradeBuffer`, `OrderBook` — 完全不改

## 涉及文件

### 需重写的文件（2个）
1. `src/exchange/binance_ws.py` — ccxt.pro → aiohttp WebSocket
2. `src/exchange/binance_rest.py` — ccxt REST → aiohttp REST

### 需适配的文件（1个）
3. `src/exchange/adapter.py` — 去掉 ccxt.pro import，适配新 WS/REST 接口

## 红线
- ❌ 不修改 `src/indicators/` 任何文件
- ❌ 不修改 `src/state/` 任何文件
- ❌ 不修改 `src/alerts/` 任何文件
- ❌ 不修改 `src/telegram/` 任何文件
- ❌ 不修改 `src/scheduler/` 任何文件
- ❌ 不修改 `src/cache/` 任何文件
- ❌ 不修改 `src/exchange/orderbook.py` 
- ❌ 不修改 `SymbolState`、`KlineBuffer`、`TradeBuffer`、`Kline`、`Trade` 数据结构
- ❌ 不改变对外接口签名

## 验收标准
1. 启动后 5 分钟内 RSS < 200MB
2. 所有 6 个币对数据正常推送
3. 30 分钟摘要正常发送（无 MarkdownV2 错误）
4. WS 断开后自动重连 + fallback REST
5. 告警逻辑正常工作
