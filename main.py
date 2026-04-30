"""
时间标签整理 - 将 <system_reminder> 重写为 <date_and_time>

在每一轮 LLM 请求前，扫描 req.contexts（历史轮次）和
req.extra_user_content_parts（当前轮次）中的所有消息，将形如：
    <system_reminder>Current datetime: 2026-02-25 01:24 (CST)</system_reminder>
替换为：
    <date_and_time>2026-02-25 01:24 (CST)</date_and_time>

AstrBot 通过 extra_user_content_parts 为当前用户消息注入 <system_reminder>，
该字段在 on_llm_request 钩子中可以被修改，因此当前轮次和历史轮次
的 <system_reminder> 都会在 LLM 收到请求之前被替换。

设计要点：
- 正则匹配 <system_reminder> 标签对内的完整内容
- 仅提取时间部分（去掉 "Current datetime: " 前缀），写入 <date_and_time>
- 三种 content 格式全部覆盖：纯字符串、字典/字符串、字典/列表（多模态）
- 如果匹配到的内容中没有 "Current datetime: " 前缀，则原样保留标签内文本

F(A) = A(F)
"""

import re

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.provider import ProviderRequest
from astrbot.api.star import Context, Star, register


# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

# 匹配完整的 <system_reminder>...</system_reminder> 标签对
SYSTEM_REMINDER_PATTERN = re.compile(
    r"<system_reminder>(.*?)</system_reminder>",
    flags=re.DOTALL,
)

# 匹配上一轮插件写入的 <current_date_and_time>，用于历史降级
CURRENT_TAG_PATTERN = re.compile(
    r"<current_date_and_time>(.*?)</current_date_and_time>",
    flags=re.DOTALL,
)

# 用于从标签内容中提取时间部分的前缀
DATETIME_PREFIX = "Current datetime: "


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------

def _make_reformat_callback(tag: str):
    """
    创建正则替换回调，将 <system_reminder> 替换为指定的标签。
    """
    def _callback(m: re.Match) -> str:
        inner = m.group(1).strip()
        if inner.startswith(DATETIME_PREFIX):
            inner = inner[len(DATETIME_PREFIX):]
        return f"<{tag}>{inner}</{tag}>"
    return _callback


def _reformat_text(text: str, tag: str = "date_and_time") -> tuple[str, bool]:
    """
    对一段文本执行替换。返回 (处理后文本, 是否发生了替换)。

    当 tag 为 "date_and_time"（历史轮次）时，同时将残留的
    <current_date_and_time> 降级为 <date_and_time>。
    """
    callback = _make_reformat_callback(tag)
    result = SYSTEM_REMINDER_PATTERN.sub(callback, text)
    # 历史轮次：将上一轮写入的 <current_date_and_time> 降级
    if tag == "date_and_time":
        result = CURRENT_TAG_PATTERN.sub(
            lambda m: f"<date_and_time>{m.group(1).strip()}</date_and_time>",
            result,
        )
    changed = result != text
    return result, changed


# ---------------------------------------------------------------------------
# 插件主体
# ---------------------------------------------------------------------------

@register(
    "时间标签整理",
    "FelisAbyssalis",
    "时间标签整理 - 将所有轮次中的 <system_reminder> 重写为 <date_and_time>",
    "2.0.0",
    "https://github.com/EmilyCheoh/astrbot_reformat_system_reminder",
)
class ReformatSystemReminderPlugin(Star):
    """
    AstrBot 插件：在每一轮 LLM 请求前，将对话中的
    <system_reminder>Current datetime: ...</system_reminder>
    替换为
    <date_and_time>...</date_and_time>

    同时处理历史轮次（req.contexts）和当前轮次
    （req.extra_user_content_parts）。
    """

    def __init__(self, context: Context):
        super().__init__(context)
        self.context = context
        logger.info("⌛️时间标签整理插件初始化完成")

    # -------------------------------------------------------------------
    # 核心：对单条消息执行替换
    # -------------------------------------------------------------------

    @staticmethod
    def _reformat_message(msg) -> tuple[object, int]:
        """
        对一条 context 消息执行 <system_reminder> → <date_and_time> 替换。

        支持三种格式：
        1. 纯字符串
        2. 字典，content 为字符串
        3. 字典，content 为列表（多模态，每个元素可能是
           {"type": "text", "text": "..."})

        Returns:
            (处理后的消息, 替换次数)
        """
        replaced = 0

        # 格式 1: 纯字符串
        if isinstance(msg, str):
            new_text, changed = _reformat_text(msg)
            if changed:
                replaced += 1
            return new_text, replaced

        # 格式 2/3: 字典
        if isinstance(msg, dict):
            content = msg.get("content", "")

            # 字典 + 字符串 content
            if isinstance(content, str):
                new_text, changed = _reformat_text(content)
                if changed:
                    replaced += 1
                    msg_copy = msg.copy()
                    msg_copy["content"] = new_text
                    return msg_copy, replaced
                return msg, replaced

            # 字典 + 列表 content（多模态）
            if isinstance(content, list):
                new_parts = []
                has_changes = False

                for part in content:
                    if (
                        isinstance(part, dict)
                        and part.get("type") == "text"
                        and isinstance(part.get("text"), str)
                    ):
                        new_text, changed = _reformat_text(part["text"])
                        if changed:
                            has_changes = True
                            replaced += 1
                            part_copy = part.copy()
                            part_copy["text"] = new_text
                            new_parts.append(part_copy)
                            continue
                    new_parts.append(part)

                if has_changes:
                    msg_copy = msg.copy()
                    msg_copy["content"] = new_parts
                    return msg_copy, replaced
                return msg, replaced

        # 未知格式，原样返回
        return msg, replaced

    # -------------------------------------------------------------------
    # 工具：处理 extra_user_content_parts 中的单个元素
    # -------------------------------------------------------------------

    @staticmethod
    def _reformat_content_part(part) -> tuple[object, int]:
        """
        对一个 ContentPart 或 dict 执行替换。

        extra_user_content_parts 中的元素可能是：
        - dict: {"type": "text", "text": "..."}
        - ContentPart 对象（带 .type 和 .text 属性）
        - 纯字符串（理论上）

        Returns:
            (处理后的元素, 替换次数)
        """
        tag = "current_date_and_time"

        # 纯字符串
        if isinstance(part, str):
            new_text, changed = _reformat_text(part, tag)
            return (new_text, 1) if changed else (part, 0)

        # dict 格式
        if isinstance(part, dict):
            if part.get("type") == "text" and isinstance(
                part.get("text"), str
            ):
                new_text, changed = _reformat_text(part["text"], tag)
                if changed:
                    part_copy = part.copy()
                    part_copy["text"] = new_text
                    return part_copy, 1
            return part, 0

        # ContentPart 对象（带属性）
        if hasattr(part, "type") and hasattr(part, "text"):
            if part.type == "text" and isinstance(part.text, str):
                new_text, changed = _reformat_text(part.text, tag)
                if changed:
                    part.text = new_text
                    return part, 1
            return part, 0

        return part, 0

    # -------------------------------------------------------------------
    # 事件钩子
    # -------------------------------------------------------------------

    @filter.on_llm_request()
    async def handle_reformat(
        self, event: AstrMessageEvent, req: ProviderRequest
    ):
        """
        [事件钩子] 在 LLM 请求前：
        1. 扫描 req.contexts（历史轮次），替换 <system_reminder>
        2. 扫描 req.extra_user_content_parts（当前轮次），替换 <system_reminder>
        """
        try:
            session_id = event.unified_msg_origin or "unknown"
            total_replaced = 0

            # --- 历史轮次：req.contexts ---
            if hasattr(req, "contexts") and req.contexts:
                new_contexts = []
                for msg in req.contexts:
                    processed, count = self._reformat_message(msg)
                    total_replaced += count
                    new_contexts.append(processed)
                req.contexts = new_contexts

            # --- 当前轮次：req.extra_user_content_parts ---
            if hasattr(req, "extra_user_content_parts") and req.extra_user_content_parts:
                new_parts = []
                for part in req.extra_user_content_parts:
                    processed, count = self._reformat_content_part(part)
                    total_replaced += count
                    new_parts.append(processed)
                req.extra_user_content_parts = new_parts

        except Exception as e:
            logger.error(
                f"时间标签整理: 处理时发生错误: {e}",
                exc_info=True,
            )

    # -------------------------------------------------------------------
    # 生命周期
    # -------------------------------------------------------------------

    async def terminate(self):
        """插件停止时的清理。"""
        logger.info("时间标签整理插件已停止")
