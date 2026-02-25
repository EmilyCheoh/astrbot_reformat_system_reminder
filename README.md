# 历史时间标签整理

**AstrBot 插件** — 将历史对话轮次中 AstrBot 自动附加的 `<system_reminder>` 时间标签重写为更简洁的 `<date_and_time>` 格式。

## 问题

AstrBot 会在每条用户消息后自动附加一个系统提醒标签：

```xml
<system_reminder>Current datetime: 2026-02-25 01:24 (CST)</system_reminder>
```

这个标签在对话历史中大量重复出现，占用上下文空间，视觉上也令人不适。

## 解决方案

本插件在每次 LLM 请求前，自动扫描对话历史中的**历史轮次**（不包括当前轮次），将：

```xml
<system_reminder>Current datetime: 2026-02-25 01:24 (CST)</system_reminder>
```

替换为：

```xml
<date_and_time>2026-02-25 01:24 (CST)</date_and_time>
```

### 设计要点

- **只处理历史轮次**：当前轮次（`req.contexts` 中最后一条 `role=user` 的消息）完全不动
- **提取纯时间**：去掉 `Current datetime: ` 前缀，只保留时间字符串本身
- **全格式覆盖**：支持 AstrBot 的三种 content 格式——
  - 纯字符串
  - 字典 + 字符串 `content`
  - 字典 + 列表 `content`（多模态，`[{"type": "text", "text": "..."}]`）
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
