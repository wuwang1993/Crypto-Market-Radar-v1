# SPEC: Code Review Bug Fixes

## 版本
- 日期: 2026-06-19
- 来源: Aider 全项目代码审查
- 范围: P0 + P1 + P2 修复

---

## P0 — Bug 修复（3 项）

### 1. WS depth 去重跳过首条消息 (binance_ws.py)
- **问题**: `_last_seq` 默认 0，depth 流 `lastUpdateId` 也可能为 0，`seq <= prev` 导致首条丢弃
- **修复**: 将 `_last_seq` 默认值改为 `None`，首次 `None` 时不判断去重
- **文件**: `src/exchange/binance_ws.py`
- **行数**: ~2 行改动

### 2. REST poll_klines None 迭代崩溃 (binance_rest.py)
- **问题**: 429 限速后 `_get_json` 返回 None，列表推导 `for k in k1m_raw` 报 TypeError
- **修复**: 在列表推导前加 `if k1m_raw is None or k5m_raw is None: return`
- **文件**: `src/exchange/binance_rest.py`
- **行数**: ~2 行改动

### 3. OrderBook 快照注释不一致 (orderbook.py)
- **问题**: 注释说增量更新需快照初始化，但 Binance depth20@100ms 实际是全量快照
- **修复**: 更新注释，明确说明 depth20@100ms 是全量快照，apply_update 可直接使用
- **文件**: `src/exchange/orderbook.py`
- **行数**: ~3 行注释改动

---

## P1 — 重要改进（3 项）

### 4. scheduler 跨层污染解耦 (jobs.py + commands.py)
- **问题**: scheduler/jobs.py 直接导入 telegram/commands.py 修改全局变量 set_alert_stats
- **修复**: 将 `_alert_count` 和 `_ws_status` 改为 command 模块内部通过回调更新，或合并到 bot 实例属性
- **文件**: `src/scheduler/jobs.py`, `src/telegram/bot.py`, `src/telegram/commands.py`, `src/main.py`
- **行数**: ~15 行改动

### 5. ExchangeAdapter 提供 ws_connected 公共属性 (adapter.py)
- **问题**: main.py 直接访问 exchange._ws.connected
- **修复**: 在 ExchangeAdapter 添加 `@property connected` 代理
- **文件**: `src/exchange/adapter.py`, `src/main.py`
- **行数**: ~5 行改动

### 6. 数据库路径可配置 (dedup.py)
- **问题**: `data/radar.db` 硬编码
- **修复**: 通过环境变量 `RADAR_DB_PATH` 或配置模型传递，默认保持 `data/radar.db`
- **文件**: `src/alerts/dedup.py`
- **行数**: ~3 行改动

---

## P2 — 代码质量（3 项）

### 7. 提取公共 _p 函数
- **问题**: `_p`/`_price` 在 state/rules.py、state/engine.py、alerts/engine.py 中重复定义
- **修复**: 在 `src/indicators/__init__.py` 导出公共 `get_price(snapshot, field)`，三处替换
- **文件**: `src/indicators/__init__.py`, `src/state/rules.py`, `src/state/engine.py`, `src/alerts/engine.py`
- **行数**: ~10 行改动

### 8. MarketState.HALTED 一致性
- **问题**: 枚举中有 HALTED，但无评分函数、无 STATE_LABELS 条目
- **修复**: 从枚举中移除 HALTED（如未使用），或添加评分函数和标签。当前无场景使用 → 移除
- **文件**: `src/state/state_types.py`, `src/scheduler/jobs.py`
- **行数**: ~2 行改动

---

## 红线（禁止修改）
- `src/state/engine.py` 状态机核心逻辑（滞后切换、评分权重）
- `src/alerts/engine.py` 告警检查器逻辑
- `src/exchange/binance_ws.py` 重连逻辑
- `src/telegram/formatter.py` MarkdownV2 转义逻辑
- 任何配置文件的 YAML 结构

## 验收标准
1. 所有 P0 bug 修复后代码不报错
2. `python -m py_compile` 通过全部文件
3. scheduler 不再直接 import telegram.commands
4. main.py 不访问私有 `_ws.connected`
5. `_p` 函数不再重复定义
