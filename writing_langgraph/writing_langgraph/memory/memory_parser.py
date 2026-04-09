"""记忆文本解析器：将自然语言记忆解析为结构化数据"""

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class MemoryDelta:
    """记忆增量（章节写作后产生的变化）"""
    character_updates: list[dict] = field(default_factory=list)
    new_characters: list[dict] = field(default_factory=list)
    power_breakthroughs: list[dict] = field(default_factory=list)
    item_changes: list[dict] = field(default_factory=list)
    plot_threads_updated: list[dict] = field(default_factory=list)
    new_constraints: list[str] = field(default_factory=list)
    location_changes: list[dict] = field(default_factory=list)

    # 特殊触发标记
    new_character_appearance: bool = False
    major_realm_breakthrough: bool = False
    main_thread_resolution: bool = False

    def to_dict(self) -> dict:
        return {
            "character_updates": self.character_updates,
            "new_characters": self.new_characters,
            "power_breakthroughs": self.power_breakthroughs,
            "item_changes": self.item_changes,
            "plot_threads_updated": self.plot_threads_updated,
            "new_constraints": self.new_constraints,
            "location_changes": self.location_changes,
            "new_character_appearance": self.new_character_appearance,
            "major_realm_breakthrough": self.major_realm_breakthrough,
            "main_thread_resolution": self.main_thread_resolution,
        }


def parse_structured_json_from_memory(memory_text: str) -> Optional[dict]:
    """
    从记忆文本末尾提取 JSON 结构化数据。

    记忆文本格式通常是：
    [Markdown 记忆内容]
    ```json
    { "character_changes": [...], ... }
    ```
    """
    if not memory_text:
        return None

    # 尝试匹配 ```json ... ``` 块
    pattern = r"```json\s*([\s\S]*?)\s*```"
    match = re.search(pattern, memory_text)

    if not match:
        return None

    json_str = match.group(1).strip()
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        return None


def parse_memory_delta(memory_text: str) -> MemoryDelta:
    """
    解析记忆文本，提取结构化增量信息。

    主要是从 LLM 输出的 JSON 块中解析。
    如果没有 JSON 块，返回空的 MemoryDelta。
    """
    delta = MemoryDelta()

    structured = parse_structured_json_from_memory(memory_text)
    if not structured:
        return delta

    # 解析人物更新
    if "character_changes" in structured:
        delta.character_updates = structured["character_changes"]

    if "new_characters" in structured:
        delta.new_characters = structured["new_characters"]
        delta.new_character_appearance = True

    # 解析战力突破
    if "power_breakthroughs" in structured:
        delta.power_breakthroughs = structured["power_breakthroughs"]
        # 检查是否是大境界突破
        for pb in structured["power_breakthroughs"]:
            if pb.get("is_major", False):
                delta.major_realm_breakthrough = True
                break

    # 解析道具变化
    if "item_changes" in structured:
        delta.item_changes = structured["item_changes"]

    # 解析伏笔更新
    if "plot_threads_updated" in structured:
        delta.plot_threads_updated = structured["plot_threads_updated"]
        for pt in structured["plot_threads_updated"]:
            if pt.get("action") == "resolved" and pt.get("is_main", False):
                delta.main_thread_resolution = True

    # 解析新约束
    if "new_constraints" in structured:
        delta.new_constraints = structured["new_constraints"]

    # 解析位置变化
    if "location_changes" in structured:
        delta.location_changes = structured["location_changes"]

    return delta


def parse_character_states(memory_text: str) -> list[dict]:
    """从记忆文本中解析人物状态表"""
    delta = parse_memory_delta(memory_text)
    if delta.character_updates:
        return delta.character_updates

    # 备用：从 Markdown 表格中解析（如果 LLM 没有输出 JSON）
    states = []
    pattern = r"\|\s*(\S+)\s*\|\s*([^|]+)\s*\|\s*([^|]+)\s*\|"
    matches = re.findall(pattern, memory_text)

    for name, location, power in matches:
        if name not in ("角色", "人物", "名称"):  # 跳过表头
            states.append({
                "name": name.strip(),
                "location": location.strip(),
                "power": power.strip(),
            })

    return states


def parse_power_breakthroughs(memory_text: str) -> list[dict]:
    """从记忆文本中解析战力突破记录"""
    delta = parse_memory_delta(memory_text)
    return delta.power_breakthroughs


def parse_plot_threads(memory_text: str) -> list[dict]:
    """从记忆文本中解析伏笔列表"""
    delta = parse_memory_delta(memory_text)
    if delta.plot_threads_updated:
        return delta.plot_threads_updated

    # 备用：从 Markdown 表格解析
    threads = []
    pattern = r"([A-Z]\d+)[^\n]*\|\s*([^\n]+)"
    matches = re.findall(pattern, memory_text)

    for code, desc in matches:
        threads.append({
            "code": code.strip(),
            "description": desc.strip(),
        })

    return threads


def extract_memory_sections(memory_text: str) -> dict[str, str]:
    """
    将记忆文本按章节分割。

    常见章节标题：
    - 世界与规则快照
    - 人物状态表
    - 时间线
    - 情节线与悬念
    - 伏笔登记
    - 一致性备忘
    """
    sections = {}

    # 按一级标题分割
    pattern = r"(##\s+[^\n]+)\n([\s\S]*?)(?=##\s+|\Z)"
    matches = re.findall(pattern, memory_text)

    for title, content in matches:
        # 清理标题
        section_name = re.sub(r"^##\s+", "", title).strip()
        sections[section_name] = content.strip()

    return sections


# =============================================
# 伏笔自动提取与保存
# =============================================

def extract_and_save_plot_threads(
    novel_id: int,
    chapter_no: int,
    draft: str,
    plan: str,
    llm,
) -> dict:
    """
    从正文中自动提取伏笔并保存到数据库。

    调用 LLM 分析本章正文，识别：
    - 新埋下的伏笔
    - 回收的伏笔
    - 埋设的伏笔（如果 plan 中有提及）

    Args:
        novel_id: 小说 ID
        chapter_no: 当前章节号
        draft: 正文内容
        plan: 策划方案（可能包含伏笔计划）
        llm: LLM 实例

    Returns:
        提取结果 {"planted": N, "resolved": N}
    """
    from writing_langgraph.prompts import MEMORY_SYSTEM
    from writing_langgraph.db import get_db, transaction
    from langchain_core.messages import HumanMessage, SystemMessage

    result = {"planted": 0, "resolved": 0}

    if not draft or len(draft) < 100:
        return result

    # 调用 LLM 提取伏笔
    prompt = f"""分析以下正文，提取伏笔信息。

本章正文：
{(draft or '')[:3000]}...

【如果有策划方案，也请参考】
{plan[:1000] if plan else ''}

请返回 JSON 格式：
{{
    "planted": [
        {{"code": "F1", "title": "伏笔标题", "content": "伏笔内容摘要", "foreshadow": "伏笔在后续如何呈现"}}
    ],
    "resolved": [
        {{"code": "F1", "summary": "本回收的伏笔内容"}}
    ]
}}

- 如果有伏笔被回收，在 resolved 中标注
- 如果有新伏笔埋下，在 planted 中标注
- 伏笔代码格式：F开头（F1、F2...）表示主线伏笔，M开头表示辅线伏笔
- 只返回确实在本章中明确出现的内容，不要推测

只返回 JSON，不要其他内容。
"""

    try:
        response = llm.bind(temperature=0.3).invoke([
            SystemMessage(content="你是一个伏笔分析专家。"),
            HumanMessage(content=prompt),
        ])

        content = response.content if hasattr(response, "content") else str(response)

        # 提取 JSON
        import re
        json_match = re.search(r'\{[\s\S]*\}', content)
        if json_match:
            data = json.loads(json_match.group())
        else:
            return result

        with transaction(novel_id) as conn:
            # 处理新埋伏笔
            for thread in data.get("planted", []):
                code = thread.get("code", "")
                if not code:
                    continue

                # 检查是否已存在
                existing = conn.execute(
                    "SELECT id FROM plot_thread WHERE novel_id = ? AND thread_code = ?",
                    (novel_id, code),
                ).fetchone()

                if existing:
                    # 更新
                    conn.execute(
                        """
                        UPDATE plot_thread
                        SET content_summary = ?, planted_chapter = ?, status = 'planted',
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                        """,
                        ((thread.get("content") or "")[:200], chapter_no, existing["id"]),
                    )
                else:
                    # 新增
                    conn.execute(
                        """
                        INSERT INTO plot_thread
                        (novel_id, thread_code, title, content_summary, planted_chapter, status)
                        VALUES (?, ?, ?, ?, ?, 'planted')
                        """,
                        (
                            novel_id,
                            code,
                            (thread.get("title") or "")[:50],
                            (thread.get("content") or "")[:200],
                            chapter_no,
                        ),
                    )
                result["planted"] += 1

            # 处理回收伏笔
            for thread in data.get("resolved", []):
                code = thread.get("code", "")
                if not code:
                    continue

                conn.execute(
                    """
                    UPDATE plot_thread
                    SET status = 'resolved',
                        actual_resolution_chapter = ?,
                        resolution_summary = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE novel_id = ? AND thread_code = ?
                    """,
                    (
                        chapter_no,
                        (thread.get("summary") or "")[:200],
                        novel_id,
                        code,
                    ),
                )
                result["resolved"] += 1

    except (sqlite3.Error, json.JSONDecodeError, re.error, AttributeError) as e:
        import traceback
        traceback.print_exc()
        pass

    return result
