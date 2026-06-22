# 交易所突破二次确认交易信号 Bot：方案设计与开发任务文档

> 版本：v1.0  
> 目标：将现有“行情监听 / 突破提醒 Bot”升级为“只推送突破后二次确认交易链路”的 Telegram 信号 Bot。  
> 范围：不做后台、不做市场摘要、不做普通涨跌提醒、不做自动下单，只做突破后的二次确认、入场计划、止损止盈、信号失效和信号结束跟踪。

---

## 1. 项目背景

当前系统已经完成：

- 交易所行情监听。
- WebSocket 行情接入。
- REST K线轮询。
- Telegram 推送已打通。
- 突破信号可以正常推送。

当前问题：

```text
系统发现突破后，只推送“突破信号”。
但没有继续监听这个突破是否成立。
没有判断是否需要二次确认。
没有给出入场区间。
没有给出止损、止盈。
没有跟踪 TP / SL。
没有判断假突破、涨太远不追、信号过期。
```

本次改造目标：

```text
突破信号 ≠ 入场信号

突破信号只代表：
“这个币出现异动，进入二次确认观察池。”

只有完成二次确认后，系统才推送：
“入场参考 + 止损 + 止盈 + 风险提示。”
```

---

## 2. 新版本产品定位

本系统从“行情信息推送 Bot”调整为：

```text
突破交易辅助信号 Bot
```

最终只服务一条链路：

```text
发现突破
    ↓
进入二次确认监听
    ↓
判断回踩确认 / 横盘稳住 / 假突破 / 涨太远不追
    ↓
确认后推送入场计划
    ↓
继续跟踪 TP / SL
    ↓
信号结束
```

---

## 3. 本次明确删除 / 禁用的信号

以下信号全部关闭，不再推送到 Telegram。

| 信号类型 | 处理方式 |
|---|---|
| 市场摘要 | 关闭 |
| 每15分钟行情摘要 | 关闭 |
| 每小时异动榜 | 关闭 |
| 普通涨跌幅提醒 | 关闭 |
| 普通震荡状态提醒 | 关闭 |
| 买盘略强提醒 | 关闭 |
| 卖盘略强提醒 | 关闭 |
| 成交量普通变化 | 关闭 |
| CVD 普通变化 | 关闭 |
| 盘口普通变化 | 关闭 |
| RSI 超买 / 超卖单独提醒 | 关闭 |
| 没有后续跟踪的单次突破重复提醒 | 关闭 |

保留原则：

```text
不直接影响交易动作的提醒，全部不推送。
```

---

## 4. 新版本只保留的 Telegram 推送

最终只保留以下推送：

| 推送类型 | 是否保留 | 说明 |
|---|---|---|
| Bot 启动提醒 | 保留 | 系统运维 |
| 系统异常提醒 | 保留 | 断线、数据延迟、推送失败 |
| 突破发现 | 保留 | 进入二次确认监听 |
| 回踩监听中 | 可选保留 | 价格接近突破位，仅提醒一次 |
| 二次确认入场 | 必须保留 | 核心交易信号 |
| 假突破失效 | 必须保留 | 取消观察 |
| 涨太远不追 | 必须保留 | 防止追高 |
| 信号过期 | 保留 | 观察结束 |
| TP1 触发 | 必须保留 | 第一止盈提醒 |
| TP2 触发 | 必须保留 | 第二止盈提醒 |
| TP3 触发 | 必须保留 | 第三止盈提醒 |
| 止损触发 | 必须保留 | 风险结束 |
| 信号完成 | 保留 | 全部 TP 或 SL 后结束 |

---

## 5. 核心设计原则

### 5.1 突破只进入观察，不直接入场

系统第一次发现突破时，只推送：

```text
发现突破，进入二次确认监听。
```

不推送“买入”。

---

### 5.2 只有二次确认成功才推送入场计划

入场计划必须包含：

- 币对
- 方向
- 突破位
- 当前价格
- 入场区间
- 止损位
- TP1
- TP2
- TP3
- 盈亏比
- 确认原因
- 风险提示

---

### 5.3 只保留一个 active signal

同一个币对、同一个方向，只允许存在一个活跃信号。

例如：

```text
BTC/USDT 当前已有多头突破信号在观察中。
在该信号未失效 / 未完成前，不再创建新的 BTC/USDT 多头突破信号。
```

允许例外：

- 原信号已经失效。
- 原信号已经完成。
- 新突破级别更高。
- 新突破位距离旧突破位超过配置阈值。

---

### 5.4 所有信号必须有生命周期

每一个突破信号都必须有状态，不允许“一次性推送后丢弃”。

---

### 5.5 所有交易信号都要可追踪

只要推送了入场计划，就必须继续监听：

- 是否触发 TP1。
- 是否触发 TP2。
- 是否触发 TP3。
- 是否触发止损。
- 是否需要结束信号。

---

## 6. 信号生命周期状态机

### 6.1 状态列表

```text
BREAKOUT_DETECTED        已发现突破
WAIT_CONFIRMATION        等待二次确认
WAIT_PULLBACK            等待回踩
RETESTING                正在回踩确认
CONSOLIDATING            突破后横盘稳住
ENTRY_CONFIRMED          入场确认
POSITION_TRACKING        入场后跟踪
TP1_HIT                  止盈1触发
TP2_HIT                  止盈2触发
TP3_HIT                  止盈3触发
STOP_LOSS_HIT            止损触发
FAKE_BREAKOUT            假突破
ENTRY_MISSED             涨太远不追
SIGNAL_EXPIRED           信号过期
SIGNAL_CLOSED            信号结束
```

---

### 6.2 状态流转图

```text
BREAKOUT_DETECTED
        ↓
WAIT_CONFIRMATION
        ↓
 ┌───────────────┬─────────────────┬─────────────────┐
 ↓               ↓                 ↓                 ↓
WAIT_PULLBACK    CONSOLIDATING     ENTRY_MISSED       FAKE_BREAKOUT
 ↓               ↓                 ↓                 ↓
RETESTING        ENTRY_CONFIRMED   SIGNAL_CLOSED      SIGNAL_CLOSED
 ↓               ↓
ENTRY_CONFIRMED  POSITION_TRACKING
        ↓
POSITION_TRACKING
        ↓
 ┌───────────────┬───────────────┬───────────────┬────────────────┐
 ↓               ↓               ↓               ↓
TP1_HIT          TP2_HIT          TP3_HIT          STOP_LOSS_HIT
 ↓               ↓               ↓               ↓
POSITION_TRACKING POSITION_TRACKING SIGNAL_CLOSED  SIGNAL_CLOSED
```

---

## 7. 信号方向

第一版建议只做多头突破信号。

```text
direction = LONG
```

暂时不做空头信号，原因：

- 当前目标是现货 / 小资金交易辅助。
- 空头涉及合约风险。
- 先把多头突破确认链路跑稳定。

后续版本再增加：

```text
direction = SHORT
```

---

## 8. 突破信号定义

### 8.1 多头突破基础条件

一个币对触发多头突破，需要满足：

```text
1. 当前价格突破最近 N 根 K线高点。
2. 当前成交量明显放大。
3. 突破时买卖量比偏强。
4. CVD 同步上升或至少不明显转弱。
5. 价格不处于极端追高状态。
```

推荐第一版使用 5m 周期。

默认条件：

```text
timeframe = 5m
lookback_bars = 20
volume_multiplier >= 1.8
buy_sell_ratio >= 1.5
price_breaks_high = true
```

---

### 8.2 突破位定义

突破位：

```text
breakout_level = 最近 20 根 5m K线最高点
```

突破价：

```text
breakout_price = 触发突破时的当前价格
```

---

### 8.3 突破后推送内容

突破发现后推送：

```text
📈 发现放量突破，进入二次确认监听

币对：BTC/USDT
方向：多头
当前价：104800
突破位：104500
突破周期：5m
成交量：放大 2.3 倍
买卖量比：1.82
CVD：上升

系统判断：
突破信号成立，但不直接追入。
已进入二次确认监听。

后续等待：
1. 回踩突破位后重新站上。
2. 或突破位上方横盘稳住。
3. 如果跌回突破位下方，将判定为假突破。
```

---

## 9. 二次确认模型

突破后系统进入二次监听。二次确认分为三种模型：

1. 回踩突破位确认。
2. 横盘稳住确认。
3. 二次放量拉升确认。

第一版建议优先做前两种。

---

## 10. 模型一：回踩突破位确认

### 10.1 逻辑说明

最稳的突破入场方式不是突破瞬间追，而是等价格突破后回踩突破位，回踩不破，再次站上时确认。

---

### 10.2 回踩区间

回踩区间定义：

```text
retest_zone_low  = breakout_level × (1 - retest_tolerance_pct)
retest_zone_high = breakout_level × (1 + reclaim_pct)
```

默认参数：

```text
retest_tolerance_pct = 0.005   # 0.5%
reclaim_pct = 0.0015           # 0.15%
```

示例：

```text
突破位：100
回踩容忍下沿：99.50
重新站上确认线：100.15
```

---

### 10.3 进入 RETESTING 状态条件

满足以下任意情况：

```text
1. 当前价格回落到突破位上方 0.15% 附近。
2. 当前价格进入 retest_zone。
3. 最低价接近 breakout_level。
```

状态变化：

```text
WAIT_CONFIRMATION → WAIT_PULLBACK → RETESTING
```

---

### 10.4 回踩有效条件

回踩有效需要满足：

```text
1. 回踩最低价没有跌破突破位 0.5% 以上。
2. 回踩过程中没有放量砸盘。
3. 回踩过程中 CVD 没有明显转弱。
4. 买卖量比没有持续低于 0.8。
5. 盘口买盘没有明显消失。
```

---

### 10.5 回踩后二次确认条件

当价格回踩后重新站上突破位，满足以下条件后推送入场信号：

```text
1. 当前价格重新站上 breakout_level × (1 + reclaim_pct)。
2. 买卖量比重新大于 1.2。
3. CVD 未明显转弱。
4. 当前价格高于 VWAP 或重新收回短周期 EMA。
5. 当前价格距离突破位不能超过 max_entry_distance_pct。
```

默认参数：

```text
min_reconfirm_buy_sell_ratio = 1.2
max_entry_distance_pct = 0.01  # 1%
```

---

## 11. 模型二：横盘稳住确认

### 11.1 逻辑说明

有些强势币突破后不会回踩，而是在突破位上方横盘。  
如果持续站稳突破位，并且买盘没有明显衰退，可以视为强势确认。

---

### 11.2 横盘稳住条件

突破后进入观察，满足以下条件：

```text
1. 突破后至少经过 2 - 3 根 5m K线。
2. 价格始终没有跌回突破位下方超过 0.3%。
3. 收盘价持续在突破位上方。
4. CVD 没有明显下降。
5. 买卖量比维持在 1.1 以上。
6. 成交量没有明显放量下跌。
```

默认参数：

```text
consolidation_bars = 3
max_below_breakout_pct = 0.003
min_consolidation_buy_sell_ratio = 1.1
```

---

### 11.3 横盘确认入场

满足横盘稳住后推送：

```text
🟢 横盘稳住入场信号

币对：BTC/USDT
突破位：104500
当前价：105000
确认方式：突破位上方横盘稳住
横盘时间：15分钟
买卖量比：1.32
CVD：未转弱

参考计划：
入场区间：104850 - 105100
止损：103950
TP1：105950
TP2：106800
TP3：107650
```

---

## 12. 模型三：二次放量拉升确认

### 12.1 逻辑说明

这是偏激进模型。  
突破后不回踩，继续放量突破小级别高点，可以给出激进入场提醒。

第一版可以先不启用，后续作为可选配置。

---

### 12.2 触发条件

```text
1. 突破后没有明显回踩。
2. 当前价格再次突破突破后的局部高点。
3. 成交量再次放大。
4. 买卖量比 > 1.5。
5. CVD 同步上升。
6. 当前价格距离突破位不超过 2%。
```

推送时必须标注：

```text
激进入场，追高风险较高。
```

---

## 13. 假突破判断

### 13.1 假突破条件

突破后满足以下条件，判定为假突破：

```text
1. 当前价格跌回突破位下方超过 fake_break_pct。
2. 买卖量比低于 0.8。
3. CVD 明显转弱。
4. 下跌成交量放大。
```

默认参数：

```text
fake_break_pct = 0.005
fake_break_sell_ratio = 0.8
```

---

### 13.2 假突破推送模板

```text
🔴 突破失败 / 假突破

币对：BTC/USDT
突破位：104500
当前价：103900
跌破幅度：-0.57%
买卖量比：0.62
CVD：转弱

系统判断：
价格跌回突破位下方，突破结构失败。
本次观察取消。

状态：
FAKE_BREAKOUT → SIGNAL_CLOSED
```

---

## 14. 涨太远不追判断

### 14.1 逻辑说明

如果突破后价格一路拉升，但没有回踩，也没有横盘确认，且距离突破位过远，则不要追入。

---

### 14.2 触发条件

```text
1. 当前价格距离突破位超过 max_chase_distance_pct。
2. 尚未出现回踩确认。
3. RSI 高于 max_chase_rsi。
```

默认参数：

```text
max_chase_distance_pct = 0.02  # 2%
max_chase_rsi = 75
```

---

### 14.3 推送模板

```text
⚠️ 已远离突破位，不再追入

币对：BTC/USDT
突破位：104500
当前价：106800
距离突破位：+2.20%
RSI：78

系统判断：
价格已经远离突破位，追入风险过高。
本次信号不再给入场计划。

状态：
ENTRY_MISSED → SIGNAL_CLOSED
```

---

## 15. 信号过期判断

### 15.1 有效期

不同周期突破监听时间不同。

| 周期 | 监听时间 |
|---|---:|
| 1m | 10 - 15 分钟 |
| 5m | 30 - 60 分钟 |
| 15m | 90 - 180 分钟 |
| 1h | 4 - 12 小时 |

第一版默认：

```text
5m 突破监听 30 分钟
15m 突破监听 90 分钟
```

---

### 15.2 过期条件

```text
当前时间 > watch_until
且没有 ENTRY_CONFIRMED
且没有 FAKE_BREAKOUT
```

推送：

```text
⌛ 突破观察过期

币对：BTC/USDT
突破位：104500
观察时间：30分钟
当前价：104700

系统判断：
突破后没有出现有效二次确认。
本次信号取消观察。

状态：
SIGNAL_EXPIRED → SIGNAL_CLOSED
```

---

## 16. 入场计划生成规则

### 16.1 入场价 / 入场区间

#### 回踩确认入场

```text
entry_price = 当前确认价格
entry_zone_low  = breakout_level × (1 + 0.001)
entry_zone_high = 当前确认价格 × (1 + 0.0015)
```

解释：

- 不建议市价追。
- 给一个入场区间。
- 让用户根据实际滑点判断。

---

#### 横盘确认入场

```text
entry_zone_low = 横盘区间中位价
entry_zone_high = 横盘区间上沿附近
```

---

### 16.2 止损规则

止损可采用两种方式，取更合理的一个。

#### 方式 A：突破位下方止损

```text
stop_loss = breakout_level × (1 - stop_loss_below_breakout_pct)
```

默认：

```text
stop_loss_below_breakout_pct = 0.008  # 0.8%
```

#### 方式 B：回踩低点下方止损

```text
stop_loss = retest_low × (1 - stop_loss_below_retest_low_pct)
```

默认：

```text
stop_loss_below_retest_low_pct = 0.005  # 0.5%
```

推荐：

```text
优先使用回踩低点下方。
如果没有明确回踩低点，则使用突破位下方。
```

---

### 16.3 止盈规则

使用 R 倍止盈。

```text
R = entry_price - stop_loss
TP1 = entry_price + 1R
TP2 = entry_price + 2R
TP3 = entry_price + 3R
```

---

### 16.4 风险过滤

入场计划生成前必须检查：

```text
1. entry_price > stop_loss。
2. R 不能太小。
3. TP1 至少覆盖交易成本和滑点。
4. 当前价格距离入场价不能太远。
5. 当前价格不能已经超过 TP1。
```

如果当前价格已经超过 TP1，不推入场，推：

```text
已错过合理入场区间，不再追入。
```

---

## 17. 入场信号推送模板

```text
🟢 二次确认入场信号

币对：BTC/USDT
方向：多头
确认方式：回踩突破位后重新站上

关键价格：
突破位：104500
当前价：104850
入场区间：104750 - 105000
止损：103950

止盈计划：
TP1：105750
TP2：106650
TP3：107550

风险收益：
单笔风险 R：约 0.86%
TP1 盈亏比：1R
TP2 盈亏比：2R
TP3 盈亏比：3R

确认条件：
- 回踩未跌破突破位有效范围
- 价格重新站上突破位
- 买卖量比：1.48
- CVD：未转弱
- 成交量：未出现放量砸盘

提示：
这是交易辅助信号，不保证盈利。
请根据自己的仓位和风险承受能力操作。
```

---

## 18. 入场后跟踪逻辑

当推送入场计划后，信号进入：

```text
POSITION_TRACKING
```

系统继续监听价格是否触发：

- TP1
- TP2
- TP3
- Stop Loss

---

### 18.1 TP1 触发

条件：

```text
current_price >= TP1
```

推送：

```text
✅ TP1 已触发

币对：BTC/USDT
入场参考：104850
当前价：105750
TP1：105750

建议：
可考虑止盈部分仓位。
剩余仓位可将止损上移到入场价附近。
```

状态：

```text
POSITION_TRACKING → TP1_HIT → POSITION_TRACKING
```

注意：

```text
TP1 只推送一次。
```

---

### 18.2 TP2 触发

条件：

```text
current_price >= TP2
```

推送：

```text
✅ TP2 已触发

币对：BTC/USDT
入场参考：104850
当前价：106650
TP2：106650

建议：
可继续降低仓位风险。
剩余仓位可用移动止盈跟踪。
```

---

### 18.3 TP3 触发

条件：

```text
current_price >= TP3
```

推送：

```text
🎯 TP3 已触发，信号完成

币对：BTC/USDT
入场参考：104850
当前价：107550
TP3：107550

系统判断：
完整止盈目标已达到。
本次信号结束。
```

状态：

```text
TP3_HIT → SIGNAL_CLOSED
```

---

### 18.4 止损触发

条件：

```text
current_price <= stop_loss
```

推送：

```text
🔴 止损触发，信号结束

币对：BTC/USDT
入场参考：104850
当前价：103950
止损位：103950

系统判断：
突破回踩结构失败。
本次信号结束。
```

状态：

```text
STOP_LOSS_HIT → SIGNAL_CLOSED
```

---

## 19. 是否需要真实入场确认

由于系统不自动下单，存在一个问题：

```text
系统不知道用户是否真的入场。
```

第一版建议采用“参考入场跟踪模式”：

```text
只要推送了 ENTRY_CONFIRMED，就默认进入 POSITION_TRACKING。
TP / SL 按入场参考价格跟踪。
```

后续第二版可以增加 Telegram 命令：

```text
/enter BTCUSDT
/skip BTCUSDT
/close BTCUSDT
```

第一版不做命令交互，避免复杂化。

---

## 20. 信号数据结构设计

每个信号需要保存成一条记录。

### 20.1 Signal 对象字段

```text
signal_id
symbol
exchange
market_type
direction
timeframe

signal_type
status

breakout_level
breakout_price
breakout_time
breakout_volume_multiplier
breakout_buy_sell_ratio
breakout_cvd_value

watch_started_at
watch_until

retest_zone_low
retest_zone_high
retest_low
retest_time

confirmation_type
confirmation_price
confirmation_time

entry_zone_low
entry_zone_high
entry_price_ref
stop_loss
take_profit_1
take_profit_2
take_profit_3
risk_r

highest_price_after_signal
lowest_price_after_signal

tp1_hit
tp2_hit
tp3_hit
stop_loss_hit

last_notify_type
last_notify_time
notify_count

invalid_reason
closed_reason
created_at
updated_at
```

---

### 20.2 状态字段说明

| 字段 | 说明 |
|---|---|
| signal_id | 唯一信号 ID |
| symbol | 币对 |
| direction | LONG / SHORT |
| status | 当前状态 |
| breakout_level | 突破位 |
| breakout_price | 突破时价格 |
| watch_until | 监听截止时间 |
| confirmation_type | 回踩确认 / 横盘确认 / 二次拉升 |
| entry_price_ref | 参考入场价 |
| stop_loss | 止损价 |
| take_profit_1 | TP1 |
| take_profit_2 | TP2 |
| take_profit_3 | TP3 |
| invalid_reason | 失效原因 |
| closed_reason | 关闭原因 |

---

## 21. 存储设计

第一版可以使用 SQLite 或 JSON 文件持久化 active signals。

推荐使用 SQLite。

### 21.1 表：signals

保存所有信号。

核心字段：

```text
id
symbol
direction
timeframe
status
breakout_level
breakout_price
entry_price_ref
stop_loss
tp1
tp2
tp3
watch_until
created_at
updated_at
closed_at
```

---

### 21.2 表：signal_events

保存信号状态变化记录。

字段：

```text
id
signal_id
event_type
old_status
new_status
event_price
message
created_at
```

作用：

```text
1. 防止重复推送。
2. 方便排查信号为什么失效。
3. 后续可统计信号效果。
```

---

## 22. 去重与防刷屏规则

### 22.1 突破发现去重

同一 symbol + direction 在 active 状态下，不再创建重复信号。

active 状态包括：

```text
BREAKOUT_DETECTED
WAIT_CONFIRMATION
WAIT_PULLBACK
RETESTING
CONSOLIDATING
ENTRY_CONFIRMED
POSITION_TRACKING
TP1_HIT
TP2_HIT
```

---

### 22.2 状态变化才推送

只有状态发生变化才推送。

例如：

```text
WAIT_CONFIRMATION → RETESTING
RETESTING → ENTRY_CONFIRMED
WAIT_CONFIRMATION → FAKE_BREAKOUT
POSITION_TRACKING → TP1_HIT
```

同一状态不重复推送。

---

### 22.3 TP / SL 只推一次

每个目标只能推送一次：

```text
tp1_hit = false → true 时推送
tp2_hit = false → true 时推送
tp3_hit = false → true 时推送
stop_loss_hit = false → true 时推送
```

---

## 23. 配置文件设计

建议新增配置：

```yaml
signal_tracker:
  enabled: true

  allowed_signals:
    breakout_lifecycle_only: true
    market_summary: false
    normal_price_alert: false
    buy_pressure_alert: false
    sell_pressure_alert: false
    volume_only_alert: false
    rsi_alert: false
    cvd_only_alert: false

  breakout:
    timeframe: "5m"
    lookback_bars: 20
    min_volume_multiplier: 1.8
    min_buy_sell_ratio: 1.5
    watch_minutes: 30
    max_active_signals_per_symbol: 1

  retest_confirm:
    enabled: true
    retest_tolerance_pct: 0.005
    reclaim_pct: 0.0015
    min_reconfirm_buy_sell_ratio: 1.2
    cvd_must_not_drop: true
    max_entry_distance_pct: 0.01

  consolidation_confirm:
    enabled: true
    bars: 3
    max_below_breakout_pct: 0.003
    min_buy_sell_ratio: 1.1

  second_push_confirm:
    enabled: false
    min_volume_multiplier: 1.5
    min_buy_sell_ratio: 1.5
    max_distance_from_breakout_pct: 0.02

  fake_breakout:
    break_below_level_pct: 0.005
    max_buy_sell_ratio: 0.8
    require_cvd_weak: true

  entry_missed:
    max_chase_distance_pct: 0.02
    max_rsi: 75

  risk_plan:
    stop_loss_below_breakout_pct: 0.008
    stop_loss_below_retest_low_pct: 0.005
    tp1_r: 1.0
    tp2_r: 2.0
    tp3_r: 3.0

  notifications:
    breakout_detected: true
    retesting: true
    entry_confirmed: true
    fake_breakout: true
    entry_missed: true
    signal_expired: true
    tp1_hit: true
    tp2_hit: true
    tp3_hit: true
    stop_loss_hit: true
    system_error: true
```

---

## 24. 模块设计

### 24.1 SignalDetector

职责：

```text
1. 从指标引擎接收 K线、成交量、买卖量比、CVD。
2. 判断是否出现突破。
3. 如果出现突破，创建 Signal。
4. 推送“突破发现”。
```

---

### 24.2 SignalTracker / PendingSignalManager

职责：

```text
1. 管理所有 active signals。
2. 每次行情更新时检查每个信号状态。
3. 判断回踩、横盘、假突破、涨太远、过期。
4. 触发状态变化。
5. 调用 Telegram 推送模块。
```

---

### 24.3 EntryPlanBuilder

职责：

```text
1. 根据突破位、确认价、回踩低点生成入场区间。
2. 计算止损。
3. 计算 R。
4. 计算 TP1 / TP2 / TP3。
5. 检查风险收益是否合理。
```

---

### 24.4 PositionTracker

职责：

```text
1. 入场信号推送后，跟踪 TP / SL。
2. 当前价达到 TP1、TP2、TP3 时推送。
3. 当前价跌破 stop_loss 时推送。
4. TP3 或 SL 后关闭信号。
```

---

### 24.5 NotificationRouter

职责：

```text
1. 只允许白名单类型推送。
2. 禁止市场摘要、普通涨跌、弱信号推送。
3. 对状态变化推送做去重。
4. 根据模板生成 TG 内容。
```

---

## 25. 开发任务拆分

---

### 阶段一：关闭旧推送

目标：

```text
关闭市场摘要和所有非交易链路信号。
```

任务：

- [ ] 关闭 market_summary。
- [ ] 关闭 hourly_ranking。
- [ ] 关闭 normal_price_alert。
- [ ] 关闭 buy_pressure_alert。
- [ ] 关闭 sell_pressure_alert。
- [ ] 关闭 volume_only_alert。
- [ ] 关闭 rsi_alert。
- [ ] 关闭 cvd_only_alert。
- [ ] 确认 TG 不再收到普通行情摘要。
- [ ] 保留 system_error 和 bot_started。

验收标准：

```text
TG 不再出现市场摘要、普通涨跌、普通买卖盘提醒。
```

---

### 阶段二：新增 Signal 数据结构

目标：

```text
系统可以创建、保存、更新信号对象。
```

任务：

- [ ] 新增 Signal 实体。
- [ ] 新增 SignalStatus 枚举。
- [ ] 新增 SignalDirection 枚举。
- [ ] 新增 SignalType 枚举。
- [ ] 新增 signals 存储表或 JSON 持久化。
- [ ] 新增 signal_events 记录。
- [ ] 新增 active signal 查询方法。
- [ ] 新增 close signal 方法。
- [ ] 新增 update status 方法。

验收标准：

```text
触发突破后，系统可以创建一条 active signal。
重启后 active signal 不丢失。
```

---

### 阶段三：突破信号接入 SignalTracker

目标：

```text
突破信号不再只是推送，而是创建生命周期信号。
```

任务：

- [ ] 修改原 Breakout Alert 逻辑。
- [ ] 突破后创建 Signal。
- [ ] 设置 status = BREAKOUT_DETECTED。
- [ ] 设置 watch_until。
- [ ] 设置 breakout_level / breakout_price。
- [ ] 检查同 symbol 同 direction 是否已有 active signal。
- [ ] 有 active signal 时不重复创建。
- [ ] 推送“突破发现，进入二次确认监听”。

验收标准：

```text
一次突破只创建一个 active signal。
TG 提醒内容包含“进入二次确认监听”。
```

---

### 阶段四：回踩确认逻辑

目标：

```text
系统能判断突破后是否回踩突破位，并在重新站上时推送入场信号。
```

任务：

- [ ] 新增 retest_zone 计算。
- [ ] 价格进入 retest_zone 时状态改为 RETESTING。
- [ ] 回踩过程中记录 retest_low。
- [ ] 判断回踩是否跌破容忍范围。
- [ ] 判断买卖量比是否恢复。
- [ ] 判断 CVD 是否未明显转弱。
- [ ] 判断价格是否重新站上突破位。
- [ ] 满足条件后生成 entry plan。
- [ ] 推送二次确认入场信号。
- [ ] 状态改为 POSITION_TRACKING。

验收标准：

```text
突破 → 回踩 → 重新站上后，TG 推送入场区间、止损、TP1/TP2/TP3。
```

---

### 阶段五：横盘稳住确认逻辑

目标：

```text
突破后不回踩但站稳突破位，也可以推送入场信号。
```

任务：

- [ ] 记录突破后的 K线数量。
- [ ] 判断连续 N 根 K线收盘在突破位上方。
- [ ] 判断没有跌破突破位超过阈值。
- [ ] 判断 CVD 未明显转弱。
- [ ] 判断买卖量比维持大于阈值。
- [ ] 满足条件后生成 entry plan。
- [ ] 推送横盘稳住入场信号。
- [ ] 状态改为 POSITION_TRACKING。

验收标准：

```text
突破后横盘 3 根 5m K线站稳，TG 推送横盘确认入场计划。
```

---

### 阶段六：假突破 / 涨太远 / 过期

目标：

```text
无效信号必须及时关闭，不再继续监听。
```

任务：

- [ ] 实现 fake_breakout 判断。
- [ ] 实现 entry_missed 判断。
- [ ] 实现 signal_expired 判断。
- [ ] 推送假突破失效。
- [ ] 推送涨太远不追。
- [ ] 推送信号过期。
- [ ] 状态改为 SIGNAL_CLOSED。
- [ ] 记录 closed_reason。

验收标准：

```text
跌回突破位下方后，TG 推送假突破。
价格涨太远后，TG 推送不追。
超过监听时间后，TG 推送过期。
```

---

### 阶段七：止损止盈跟踪

目标：

```text
入场信号推送后继续跟踪 TP / SL。
```

任务：

- [ ] ENTRY_CONFIRMED 后进入 POSITION_TRACKING。
- [ ] 当前价 >= TP1 推送 TP1。
- [ ] 当前价 >= TP2 推送 TP2。
- [ ] 当前价 >= TP3 推送 TP3 并关闭信号。
- [ ] 当前价 <= stop_loss 推送止损并关闭信号。
- [ ] TP1 / TP2 / TP3 / SL 均只推送一次。
- [ ] 记录每个 TP hit 状态。
- [ ] 记录信号最终结果。

验收标准：

```text
推送入场计划后，后续能收到 TP1 / TP2 / TP3 / SL 提醒。
不会重复推送同一个 TP。
```

---

### 阶段八：Telegram 模板调整

目标：

```text
所有推送都围绕突破生命周期。
```

任务：

- [ ] 新增突破发现模板。
- [ ] 新增回踩监听模板。
- [ ] 新增二次确认入场模板。
- [ ] 新增横盘确认入场模板。
- [ ] 新增假突破模板。
- [ ] 新增涨太远不追模板。
- [ ] 新增信号过期模板。
- [ ] 新增 TP1 模板。
- [ ] 新增 TP2 模板。
- [ ] 新增 TP3 模板。
- [ ] 新增止损模板。
- [ ] 删除 / 禁用市场摘要模板。

验收标准：

```text
TG 信息清晰，只出现突破交易链路相关内容。
```

---

### 阶段九：测试与验收

目标：

```text
确保新信号链路稳定，不刷屏，不漏推。
```

测试场景：

- [ ] 正常突破 → 回踩 → 二次确认 → TP1 → TP2 → TP3。
- [ ] 正常突破 → 回踩失败 → 假突破。
- [ ] 正常突破 → 不回踩 → 横盘稳住 → 入场。
- [ ] 正常突破 → 暴涨过远 → 不追。
- [ ] 正常突破 → 30分钟无确认 → 过期。
- [ ] 入场后先触发 TP1，再回落止损。
- [ ] 入场后直接触发止损。
- [ ] Bot 重启后 active signal 能恢复。
- [ ] 同一 symbol 不重复创建 active signal。
- [ ] TG 不再收到市场摘要。

验收标准：

```text
连续运行 24 小时：
1. 不推市场摘要。
2. 不推普通弱信号。
3. 每条突破信号都有后续结果。
4. 入场信号都有止损止盈。
5. TP / SL 不重复推送。
6. 没有明显内存增长。
7. 系统异常能推送。
```

---

## 26. MVP 范围

第一版只做：

```text
1. 多头突破。
2. 5m 周期。
3. 回踩确认。
4. 横盘确认。
5. 假突破。
6. 涨太远不追。
7. 监听过期。
8. 入场区间。
9. 止损。
10. TP1 / TP2 / TP3。
11. TP / SL 跟踪。
12. Telegram 推送。
```

第一版不做：

```text
1. 空头信号。
2. 自动下单。
3. Telegram 交互式确认。
4. 市场摘要。
5. 普通信号。
6. AI 预测。
7. 回测。
8. 网页后台。
```

---

## 27. 最终推送链路示例

### 27.1 突破发现

```text
📈 发现放量突破，进入二次确认监听

币对：BTC/USDT
方向：多头
突破位：104500
当前价：104800
成交量：放大 2.3 倍
买卖量比：1.82
CVD：上升

系统判断：
突破成立，但不直接追入。
等待回踩突破位或横盘稳住后，再推送入场计划。
```

---

### 27.2 回踩监听

```text
👀 回踩突破位监听中

币对：BTC/USDT
突破位：104500
当前价：104620
回踩区间：103980 - 104660

系统判断：
价格正在回踩突破位附近。
等待重新站上并确认买盘恢复。
```

---

### 27.3 二次确认入场

```text
🟢 二次确认入场信号

币对：BTC/USDT
方向：多头
确认方式：回踩突破位后重新站上

突破位：104500
当前价：104850
入场区间：104750 - 105000
止损：103950

TP1：105750
TP2：106650
TP3：107550

确认条件：
- 回踩未跌破有效范围
- 买卖量比恢复至 1.48
- CVD 未转弱
- 未出现放量砸盘

风险提示：
此为交易辅助信号，不保证盈利。
```

---

### 27.4 假突破

```text
🔴 突破失败 / 假突破

币对：BTC/USDT
突破位：104500
当前价：103900
跌破幅度：-0.57%
买卖量比：0.62
CVD：转弱

系统判断：
突破结构失败。
本次信号取消观察。
```

---

### 27.5 TP1

```text
✅ TP1 已触发

币对：BTC/USDT
入场参考：104850
当前价：105750
TP1：105750

建议：
可考虑止盈部分仓位。
剩余仓位可将止损上移至入场价附近。
```

---

### 27.6 止损

```text
🔴 止损触发，信号结束

币对：BTC/USDT
入场参考：104850
当前价：103950
止损位：103950

系统判断：
突破回踩结构失败。
本次信号结束。
```

---

## 28. 给开发 Agent 的执行指令

```md
# 开发任务：只保留突破生命周期交易信号，关闭其他信号

当前目标：
将现有行情 Bot 改造成只推送“突破 → 二次确认 → 入场 → 止损止盈 → 信号结束”的交易辅助 Bot。

必须关闭：
1. 市场摘要
2. 每小时异动榜
3. 普通涨跌提醒
4. 普通买盘增强
5. 普通卖盘增强
6. CVD 单独提醒
7. RSI 单独提醒
8. 成交量单独提醒

必须新增：
1. Signal 数据结构
2. Signal 状态机
3. SignalTracker / PendingSignalManager
4. 回踩确认
5. 横盘确认
6. 假突破判断
7. 涨太远不追判断
8. 信号过期判断
9. EntryPlanBuilder
10. TP / SL 跟踪
11. Telegram 生命周期模板

核心流程：
突破发现 → 创建 Signal → 等待二次确认 → 确认后推送入场计划 → 跟踪 TP / SL → 信号结束。

验收标准：
1. TG 不再出现市场摘要。
2. TG 不再出现普通弱信号。
3. 每个突破信号都有后续状态。
4. 二次确认后必须包含入场、止损、TP1、TP2、TP3。
5. TP / SL 触发后必须推送。
6. 同一个 symbol 同方向不能重复创建 active signal。
7. 重启后 active signal 不丢失。
```

---

## 29. 最终结论

当前系统已经完成“监听”和“突破发现”，下一步不应该继续加更多普通信号。

正确方向是：

```text
关闭所有普通推送。
只保留突破交易生命周期。
```

最终系统应该做到：

```text
1. 发现突破，但不追。
2. 自动等待二次确认。
3. 确认后给入场区间。
4. 同时给止损和三档止盈。
5. 后续自动跟踪 TP / SL。
6. 假突破、涨太远、过期都要结束信号。
7. Telegram 只推送交易动作相关提醒。
```

这才是从“行情提醒 Bot”升级为“交易辅助信号 Bot”的关键。
