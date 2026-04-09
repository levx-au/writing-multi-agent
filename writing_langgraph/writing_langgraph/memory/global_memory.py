"""全局记忆管理器"""

from __future__ import annotations

from typing import Optional, Protocol

from writing_langgraph.db import (
    Character,
    MemoryGlobal,
    NovelMetadata,
    get_db,
    json_dumps,
)


class LLMInvoker(Protocol):
    """LLM 调用协议"""
    def invoke(self, messages: list) -> str: ...


def create_initial_global_memory(
    novel_id: int,
    plan: str,
    world_rules: str,
    llm: Optional[LLMInvoker] = None,
) -> str:
    """
    根据策划方案和世界观规则生成初始全局记忆。

    Args:
        novel_id: 小说 ID
        plan: 策划方案文本
        world_rules: 世界规则 JSON 字符串
        llm: 可选的 LLM 调用器（用于从策划提取信息）

    Returns:
        全局记忆文本
    """
    from writing_langgraph.prompts import GLOBAL_MEMORY_SYSTEM
    from langchain_core.messages import HumanMessage, SystemMessage

    if llm is None:
        # 无 LLM 时生成基础结构
        return _generate_basic_global_memory(plan, world_rules)

    user = (
        f"【世界观规则】\n{world_rules}\n\n"
        f"【策划方案】\n{plan}"
    )

    response = llm.invoke([SystemMessage(content=GLOBAL_MEMORY_SYSTEM), HumanMessage(content=user)])
    content = response.content if hasattr(response, "content") else str(response)
    return content if isinstance(content, str) else str(content)


def _generate_basic_global_memory(plan: str, world_rules: str) -> str:
    """生成基础全局记忆（无 LLM 时）"""
    import json

    rules = json.loads(world_rules) if world_rules and world_rules != "{}" else {}

    sections = ["# 全局记忆\n"]

    sections.append("## 世界规则\n")
    if rules:
        for key, value in rules.items():
            sections.append(f"- **{key}**: {value}\n")
    else:
        sections.append("（待从策划方案填充）\n")

    sections.append("\n## 人物模板\n")
    sections.append("（待从策划方案填充）\n")

    sections.append("\n## 主线伏笔\n")
    sections.append("（待从策划方案填充）\n")

    sections.append("\n## 核心约束\n")
    sections.append("（待从策划方案填充）\n")

    return "".join(sections)


def load_global_memory(novel_id: int) -> Optional[MemoryGlobal]:
    """加载最新版本的全局记忆"""
    with get_db(novel_id) as conn:
        row = conn.execute(
            """
            SELECT * FROM memory_global
            WHERE novel_id = ?
            ORDER BY version DESC
            LIMIT 1
            """,
            (novel_id,),
        ).fetchone()

        if row is None:
            return None
        return MemoryGlobal.from_row(row)


def save_global_memory(
    novel_id: int,
    content: str,
) -> MemoryGlobal:
    """
    保存新版全局记忆（自动递增版本号）。

    Returns:
        保存的 MemoryGlobal 对象
    """
    with get_db(novel_id) as conn:
        # 获取当前最大版本号
        row = conn.execute(
            "SELECT MAX(version) as max_ver FROM memory_global WHERE novel_id = ?",
            (novel_id,),
        ).fetchone()
        max_ver = row["max_ver"] or 0

        cursor = conn.execute(
            """
            INSERT INTO memory_global (novel_id, content, version)
            VALUES (?, ?, ?)
            """,
            (novel_id, content, max_ver + 1),
        )

        return MemoryGlobal(
            id=cursor.lastrowid,
            novel_id=novel_id,
            content=content,
            version=max_ver + 1,
        )


def get_global_memory_content(novel_id: int) -> str:
    """获取全局记忆内容文本（不存在返回空）"""
    mem = load_global_memory(novel_id)
    return mem.content if mem else ""


def get_novel_metadata(novel_id: int) -> Optional[NovelMetadata]:
    """获取小说元数据"""
    with get_db(novel_id) as conn:
        row = conn.execute(
            "SELECT * FROM novel_metadata WHERE id = ?",
            (novel_id,),
        ).fetchone()

        if row is None:
            return None
        return NovelMetadata.from_row(row)


def should_update_global_memory(memory_delta: dict) -> bool:
    """
    根据记忆增量判断是否需要更新全局记忆。

    全局记忆只在关键节点更新：
    - 新人物首次登场
    - 大境界突破
    - 主线伏笔回收
    - 新卷开始
    """
    triggers = [
        "new_character_appearance",
        "major_realm_breakthrough",
        "main_thread_resolution",
        "new_volume_start",
    ]
    return any(key in memory_delta for key in triggers)
