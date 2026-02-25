"""
历史时间标签整理 - 将历史轮次中的 <system_reminder> 重写为 <date_and_time>

在每一轮 LLM 请求前，扫描 req.contexts 中除最后一条用户消息以外的
所有历史轮次，将形如：
    <system_reminder>Current datetime: 2026-02-25 01:24 (CST)</system_reminder>
替换为：
    <date_and_time>2026-02-25 01:24 (CST)</date_and_time>

当前轮次（最后一条 role=user 的消息）不做任何修改。

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

# 用于从标签内容中提取时间部分的前缀
DATETIME_PREFIX = "Current datetime: "


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------

def _reformat_match(m: re.Match) -> str:
    """
    正则替换回调：将 <system_reminder> 标签替换为 <date_and_time>。
    如果标签内容以 "Current datetime: " 开头，则去掉该前缀，
    只保留时间字符串本身。
    """
    inner = m.group(1).strip()
    if inner.startswith(DATETIME_PREFIX):
        inner = inner[len(DATETIME_PREFIX):]
    return f"<date_and_time>{inner}</date_and_time>"


def _reformat_text(text: str) -> tuple[str, bool]:
    """
    对一段文本执行替换。返回 (处理后文本, 是否发生了替换)。
    """
    result = SYSTEM_REMINDER_PATTERN.sub(_reformat_match, text)
    changed = result != text
    return result, changed


# ---------------------------------------------------------------------------
# 插件主体
# ---------------------------------------------------------------------------

@register(
    "reformat_system_reminder",
    "FelisAbyssalis",
    "历史时间标签整理 - 将历史轮次中的 <system_reminder> 重写为 <date_and_time>",
    "1.0.0",
    "https://github.com/EmilyCheoh/astrbot_reformat_system_reminder",
)
class ReformatSystemReminderPlugin(Star):
    """
    AstrBot 插件：在每一轮 LLM 请求前，将历史对话中的
    <system_reminder>Current datetime: ...</system_reminder>
    替换为
    <date_and_time>...</date_and_time>

    只处理历史轮次，不触碰当前轮次（req.contexts 中最后一条
    role=user 的消息）。
    """

    def __init__(self, context: Context):
        super().__init__(context)
        self.context = context
        logger.info("历史时间标签整理插件初始化完成")

    # -------------------------------------------------------------------
    # 核心：定位"最后一条用户消息"的索引
    # -------------------------------------------------------------------

    @staticmethod
    def _find_last_user_index(contexts: list) -> int:
        """
        从后往前扫描 contexts，找到最后一条 role=user 的消息索引。
        如果找不到，返回 -1。
        """
        for i in range(len(contexts) - 1, -1, -1):
            msg = contexts[i]
            if isinstance(msg, dict) and msg.get("role") == "user":
                return i
        return -1

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
           {"type": "text", "text": "..."}）

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
    # 事件钩子
    # -------------------------------------------------------------------

    @filter.on_llm_request()
    async def handle_reformat(
        self, event: AstrMessageEvent, req: ProviderRequest
    ):
        """
        [事件钩子] 在 LLM 请求前：
        扫描 req.contexts 中除最后一条用户消息以外的所有历史轮次，
        将 <system_reminder> 替换为 <date_and_time>。
        """
        if not hasattr(req, "contexts") or not req.contexts:
            return

        try:
            session_id = event.unified_msg_origin or "unknown"
            contexts = req.contexts

            # 定位最后一条用户消息——这条不动
            last_user_idx = self._find_last_user_index(contexts)

            total_replaced = 0
            new_contexts = []

            for i, msg in enumerate(contexts):
                # 跳过当前轮次（最后一条用户消息）
                if i == last_user_idx:
                    new_contexts.append(msg)
                    continue

                processed, count = self._reformat_message(msg)
                total_replaced += count
                new_contexts.append(processed)

            req.contexts = new_contexts

            if total_replaced > 0:
                logger.info(
                    f"[{session_id}] 历史时间标签整理: "
                    f"已将 {total_replaced} 处 <system_reminder> "
                    f"替换为 <date_and_time>"
                )

        except Exception as e:
            logger.error(
                f"历史时间标签整理: 处理时发生错误: {e}",
                exc_info=True,
            )

    # -------------------------------------------------------------------
    # 生命周期
    # -------------------------------------------------------------------

    async def terminate(self):
        """插件停止时的清理。"""
        logger.info("历史时间标签整理插件已停止")
