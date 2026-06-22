# SPEC: 审计关键问题修复 v1.1

## 范围
修复二次审计发现的 3 个关键问题

## 问题清单

### #1 main.py:149 — break 导致服务崩溃
- 位置: `src/main.py` 主循环 try/except 块
- 当前: 任何异常触发 `break` 退出主循环，服务彻底停止
- 目标: 改为 `continue`，记录日志后继续运行

### #2 main.py:131-138 — 单条告警无错误隔离
- 位置: `src/main.py` 告警发送循环
- 当前: `bot.send_message(msg)` 无 try/except，一条消息 MarkdownV2 失败 → 整个 tick 崩溃
- 目标: 每个 alert 发送包裹 try/except，失败只记日志继续下一条

### #3 telegram/bot.py — 返回值未检查 + heartbeat 误用 MarkdownV2
- 位置: `src/telegram/bot.py` send_message 方法
- 位置: `src/scheduler/jobs.py` _heartbeat_loop
- 当前: send_message 始终传 parse_mode="MarkdownV2"，心跳消息是纯文本也走 MarkdownV2
- 目标: 心跳消息显式传 parse_mode=None

## 不改动
- alerts/ 模块
- exchange/ 模块
- indicators/ 模块
- state/ 模块
- config/ 模块

## 修改范围
- src/main.py: 2 处改动（break→continue + per-alert try/except）
- src/scheduler/jobs.py: 1 处改动（心跳 parse_mode=None）
