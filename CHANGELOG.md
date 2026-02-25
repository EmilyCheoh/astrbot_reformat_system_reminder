# CHANGELOG

## 1.0.0 — 2026-02-25

### 新增

- 初始版本发布
- 在每次 LLM 请求前，自动将历史轮次中的 `<system_reminder>Current datetime: ...</system_reminder>` 替换为 `<date_and_time>...</date_and_time>`
- 当前轮次（最后一条 `role=user` 的消息）不做修改
- 支持三种 content 格式：纯字符串、字典/字符串、字典/列表（多模态）
- 替换时去掉 `Current datetime: ` 前缀，只保留时间字符串本身
