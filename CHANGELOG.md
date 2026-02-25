# CHANGELOG

## 1.0.2 — 2026-02-25

### 修复

- 不再跳过「当前轮次」的用户消息——改为处理 `req.contexts` 中的所有消息
- 原因：被跳过的消息在持久化后，下一轮已经无法再被修改，导致部分 `<system_reminder>` 标签永久残留
- AstrBot 每次都会为当前用户消息重新附加新的 `<system_reminder>`，因此替换 contexts 中的旧标签不会导致信息丢失

## 1.0.1 — 2026-02-25

### 修复

- 移除 `__init__` 中多余的 `config` 参数——本插件无配置项，AstrBot 不会传递该参数

## 1.0.0 — 2026-02-25

### 新增

- 初始版本发布
- 在每次 LLM 请求前，自动将对话上下文中的 `<system_reminder>Current datetime: ...</system_reminder>` 替换为 `<date_and_time>...</date_and_time>`
- 支持三种 content 格式：纯字符串、字典/字符串、字典/列表（多模态）
- 替换时去掉 `Current datetime: ` 前缀，只保留时间字符串本身
