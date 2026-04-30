# 时间标签整理

**AstrBot 插件** — 将对话中 AstrBot 自动附加的 `<system_reminder>` 时间标签重写为语义更清晰的格式，区分历史轮次和当前轮次。

## 问题

AstrBot 会在每条用户消息后自动附加一个系统提醒标签：

```xml
<system_reminder>Current datetime: 2026-02-25 01:24 (CST)</system_reminder>
```

这个标签在对话历史中大量重复出现，标签名含义模糊，容易令 LLM 混淆。

## 解决方案

本插件在每次 LLM 请求前，自动扫描并替换所有 `<system_reminder>` 标签：

**历史轮次**（`req.contexts`）：

```xml
<system_reminder>Current datetime: 2026-02-25 01:24 (CST)</system_reminder>
  ↓
<date_and_time>2026-02-25 01:24 (CST)</date_and_time>
```

**当前轮次**（`req.extra_user_content_parts`）：

```xml
<system_reminder>Current datetime: 2026-02-25 01:24 (CST)</system_reminder>
  ↓
<current_date_and_time>2026-02-25 01:24 (CST)</current_date_and_time>
```

### 设计要点

- **双标签区分时序**：历史轮次用 `<date_and_time>`，当前轮次用 `<current_date_and_time>`，LLM 可以通过标签名直接分辨
- **提取纯时间**：去掉 `Current datetime: ` 前缀，只保留时间字符串本身
- **全格式覆盖**：支持 AstrBot 的多种 content 格式——
  - 纯字符串
  - 字典 + 字符串 `content`
  - 字典 + 列表 `content`（多模态，`[{"type": "text", "text": "..."}]`）
  - `ContentPart` 对象（带 `.type` 和 `.text` 属性）
- **安全降级**：如果 `<current_date_and_time>` 意外出现在历史轮次中，会自动降级为 `<date_and_time>`
- **无配置需求**：安装即用，不需要任何额外配置

## 安装

将整个 `reformat_system_reminder` 文件夹放入 AstrBot 的插件目录，重启 AstrBot 即可。

## 文件结构

```
reformat_system_reminder/
├── main.py          # 插件主体
├── metadata.yaml    # AstrBot 插件元数据
├── README.md        # 本文件
└── CHANGELOG.md     # 变更日志
```

## 作者

Felis Abyssalis

## 许可证

F(A) = A(F)
