# SPEC: Crypto Market Radar Bot v1.1 — 全量修复

## 版本
- 目标版本: v1.1.0 → v1.1.1
- 父 SPEC: 无（修复性版本）
- 创建日期: 2026-06-19

## 修复目标（6 个问题，3 文件，~80 行）

### P0-1: 主循环异常保护 + 心跳日志
**文件**: `src/main.py`
**改动**:
- `except asyncio.CancelledError` → 改为 `except asyncio.CancelledError` + `except Exception`
- 每个 30s 循环末尾加 `logger.debug("Main loop tick — N symbols, M alerts")` 级别 INFO
- Exception handler 内 logger.exception + system_error_alert 推送
**不改**: 不改变主循环业务逻辑，不新增状态机

### P0-2: K线轮询去重
**文件**: `src/exchange/adapter.py` (_kline_poller)
**改动**:
- 维护 `_last_kline_ts: dict[str, dict[str, int]]` 记录每个 symbol+tf 最后处理的时间戳
- 只添加 timestamp > 上次记录的新 K 线
**不改**: binance_rest.py 不碰，poll_klines 行为不变

### P1-3: 资金费率/OI 定期更新
**文件**: `src/exchange/adapter.py` (_kline_poller 内追加)
**改动**:
- 每 30 次 kline 轮询（150s）调一次 `fetch_funding_rate` + `fetch_open_interest`
- 更新 `state.funding_rate` 和 `state.open_interest`
**不改**: binance_rest.py warmup 逻辑不变

### P2-4: TradeBuffer 增量维护
**文件**: `src/cache/trade_buffer.py`
**改动**:
- 新增 `_buy_volume` `_sell_volume` 内部累计字段
- `add()` 方法增量更新两个累计值
- `buy_volume` / `sell_volume` property 改为直接返回累计值
- deque 移除旧元素时从累计值中减去
**不改**: Trade 数据类定义不变，TradeBuffer 接口不变

### P2-5: Telegram polling 启用
**文件**: `src/telegram/bot.py` + `src/telegram/commands.py`
**改动**:
- `RadarBot.start()` 内启动 `app.run_polling()` 作为 background task
- `RadarBot.stop()` 内正确停止 polling
**不改**: 命令处理逻辑不变

### P3-6: 内存排查（非代码修复，运行时检查）
不修改代码，仅在部署后监控：systemd service 加 `MemoryHigh=300M MemoryMax=400M`

## 红线（禁止修改）
- ❌ 不碰 12 个告警 checker 的阈值
- ❌ 不碰 14 个 state scorer 的评分逻辑
- ❌ 不碰 binance_ws.py（WS 已稳定）
- ❌ 不碰 binance_rest.py（poll 逻辑已正确）
- ❌ 不碰 indicators/*.py（计算逻辑不变）
- ❌ 不碰 scheduler/jobs.py（定时逻辑不变）
- ❌ 不碰 alerts/engine.py, dedup.py, merger.py, templates.py
- ❌ 不碰 config/*, state/*, exchange/orderbook.py

## 验收标准
1. 主循环崩溃后系统不退出，发送 system_error 告警到 TG
2. 日志每 30s 出现 "Main loop tick"
3. K线 buffer 中不出现同一 timestamp 的重复蜡烛
4. 资金费率每 150s 更新一次
5. TradeBuffer buy_volume/sell_volume O(1) 返回
6. `/status` 命令在 TG 中可响应
7. systemd MemoryHigh 生效

## 变更摘要
| 文件 | 新增行 | 删除行 | 净变化 |
|------|--------|--------|--------|
| src/main.py | +15 | -5 | +10 |
| src/exchange/adapter.py | +25 | -5 | +20 |
| src/cache/trade_buffer.py | +20 | -10 | +10 |
| src/telegram/bot.py | +15 | -5 | +10 |
| systemd/crypto-radar.service | +2 | -0 | +2 |
| **合计** | **~77** | **~25** | **~52** |
