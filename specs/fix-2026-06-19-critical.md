# SPEC: Crypto Market Radar — 关键修复 v1.1

## 问题汇总
1. 🔴 30分钟摘要消息因 MarkdownV2 `+`/`-` 未转义，全部发送失败（连续 24 次）
2. 🔴 内存泄漏：6 个币对占用 759MB（正常 < 80MB）
3. 🟡 资金费率 API 在现货市场静默失败
4. 🟡 告警阈值对低波动市场过于保守

## 修复方案

### P0-1: 修复 MarkdownV2 转义（scheduler/jobs.py）
- 原因: `format_pct()` 返回的 `+`/`-` 未经过 `escape_markdown()`
- 修复: 在 `_build_summary()` 中，将 `ret_str` 也用 `escape_markdown()` 包裹
- 文件: `src/scheduler/jobs.py`，约 3 行
- 避免碰: 不修改 formatter.py 的其他函数，不修改 format_alert

### P0-2: 内存泄漏根因修复（exchange/adapter.py）
- 原因: ccxt.pro 默认 `watch_order_book()` 缓存全量订单簿（数千价格档位）
- 修复: 创建 exchange 时传入 `{'options': {'defaultType': 'spot', 'watchOrderBook': {'limit': 20}}}`
- 关键: 限制订单簿深度到 20 档（告警本身不需要全深度）
- 文件: `src/exchange/binance_ws.py`，约 3 行
- 附加: 在 main loop 每 60 个 tick 执行一次 `gc.collect()`
- 避免碰: 不修改 WS 连接逻辑，不修改 ccxt 版本

### P1-3: 资金费率切换到合约市场
- 原因: Binance 现货不支持 fetch_funding_rate
- 修复: 在 _kline_poller 中捕获 NotSupported，改为查永续合约
- 文件: `src/exchange/adapter.py`，约 8 行
- 避免碰: 不改变 Symbols 定义，不修改指标计算

### P1-4: 增加系统活跃心跳
- 原因: 无告警时用户看不到任何消息（感知不到系统在工作）
- 修复: 每 2 小时发送一次 `"🟢 系统正常 | 监控6币对 | 今日告警0"` 
- 文件: `src/scheduler/jobs.py`，约 10 行
- 避免碰: 不改变现有 scheduler 循环结构

## 红线
- 不修改核心指标算法 (indicators/)
- 不修改状态机 (state/)
- 不修改 WS 连接与重连逻辑
- 不修改 Telegram bot 基础架构
- 不修改 SymbolState 数据结构

## 验证方式
1. 启动后 30 分钟内应收到市场摘要
2. `systemctl status` 显示内存应 < 100MB
3. 不应再有 `Can't parse entities` 错误
4. 每 2 小时收到心跳消息
