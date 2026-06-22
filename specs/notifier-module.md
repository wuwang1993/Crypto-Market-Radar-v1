# SPEC: 统一通知模块 notifier.py

## 日期
2026-06-19

## 目标
创建 `src/notifier.py` 统一封装所有 Telegram 推送，消除散落在 `main.py` 和 `jobs.py` 中的裸 `bot.send_message()` 调用。

## 设计原则
- **单一通道**: 仅 Telegram（飞书不做）
- **薄封装层**: 不改变格式化逻辑，只统一发送入口
- **类型安全**: 每个通知类型一个方法，参数明确
- **依赖注入**: Notifier 通过构造函数接收 send_fn

---

## 新建文件: `src/notifier.py`

```python
class Notifier:
    def __init__(self, send_fn: Callable) -> None
```

### 方法清单

| 方法 | 参数 | 用途 | 替换位置 |
|------|------|------|----------|
| `send_startup(symbol_count)` | int | 启动通知 | main.py:84 |
| `send_warmup_done(symbol_count, warmup_seconds)` | int, float | 预热完成 | main.py:106 |
| `send_alert(alert)` | AlertEvent | 单条告警 | main.py:159 |
| `send_system_error(symbol, error)` | str, str | 系统错误 | main.py:166 |
| `send_summary(text)` | str | 30分钟摘要 | jobs.py:85 |
| `send_heatmap(text_or_none)` | str\|None | 小时热力图 | jobs.py:124 |
| `send_daily(text)` | str | 日报 | jobs.py:156 |
| `send_heartbeat(text)` | str | 心跳 | jobs.py:181 |

### 不封装的内容（红线）
- `commands.py` 中的 `update.message.reply_text()` — 交互式命令响应，非推送
- `startup_message()` / `warmup_done_message()` / `format_alert()` — 格式化函数留在 `formatter.py`
- `_build_summary()` / `_build_heatmap()` / `_build_daily()` — 构建逻辑留在 `jobs.py`

---

## 修改文件

### 1. `src/main.py`
- 导入: `from src.notifier import Notifier`
- 创建: `notifier = Notifier(bot.send_message)`
- 替换所有 `bot.send_message(...)` 为 `notifier.send_xxx(...)`
- `SummaryScheduler` 不再传 `bot.send_message`，改传 `notifier`

### 2. `src/scheduler/jobs.py`
- `__init__` 参数 `send_fn` → `notifier`
- `self._send(msg)` → `self._notifier.send_summary(msg)` 等
- `self._send(msg, parse_mode=None)` → `self._notifier.send_heartbeat(text)`
- 移除对 `bot` 的直接依赖（如果当前只在 record_alert 中用 bot.alert_count）

### 3. `src/__init__.py`
- 无需改动

---

## 红线（禁止修改）
- `telegram/formatter.py` — 格式化函数不动
- `telegram/commands.py` — 命令处理器不动
- `telegram/bot.py` — Bot 类不动
- `state/` — 状态机不动
- `indicators/` — 指标计算不动
- `alerts/engine.py` — 告警引擎不动
- `alerts/templates.py` — 告警模板不动

## 验收标准
1. `python3 -m py_compile` 全部通过
2. `grep -rn "bot.send_message" src/` 仅 `notifier.py` 和 `bot.py` 内部有
3. `grep -rn "_send(msg" src/` 仅 `notifier.py` 内部有
4. main.py 不直接 import `startup_message` / `warmup_done_message`（通过 notifier）
5. jobs.py 不直接持有 `send_fn` 裸函数引用
