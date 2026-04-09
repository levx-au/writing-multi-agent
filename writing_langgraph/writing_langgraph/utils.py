from __future__ import annotations

import json
import re
from typing import Any, Optional


def parse_score(text: str) -> float:
    """
    从审阅文本中解析评分。支持多种宽松格式。

    Returns:
        0.0~10.0 的浮点数，或 -1.0 表示解析失败（需要调用方兜底）。
    """
    if not text:
        return -1.0
    # 标准格式: SCORE: 8.5 或 SCORE：8.5（兼容中英文冒号）
    m = re.search(r"SCORE[：:]\s*([0-9]+(?:\.[0-9]+)?)", text, re.I)
    if m:
        try:
            return max(0.0, min(10.0, float(m.group(1))))
        except ValueError:
            pass
    # 备选格式: 8.5/10 或 8/10 或 8.55/10（支持多位小数）
    m = re.search(r"\b([0-9]+(?:\.[0-9]+)?)\s*/\s*10\b", text)
    if m:
        try:
            return max(0.0, min(10.0, float(m.group(1))))
        except ValueError:
            pass
    # 备选格式: 评分 8.5 或 评分：8.5
    m = re.search(r"评分[：:\s]*([0-9]+(?:\.[0-9]+)?)", text, re.I)
    if m:
        try:
            return max(0.0, min(10.0, float(m.group(1))))
        except ValueError:
            pass
    # 备选格式: 8.5分
    m = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*分", text)
    if m:
        try:
            return max(0.0, min(10.0, float(m.group(1))))
        except ValueError:
            pass
    # 备选格式: 综合评分 8.0 或 给予本章评分 8.0
    m = re.search(r"评分[^\d]*([0-9]+(?:\.[0-9]+)?)", text, re.I)
    if m:
        try:
            v = float(m.group(1))
            if v <= 10:
                return v
        except ValueError:
            pass
    # 兜底：全文中第一个 0~10 的小数/整数
    candidates = re.findall(r"(?<![.\d])([0-9]+(?:\.[0-9]+)?)(?![.\d]|\s*/\s*10)", text)
    for c in candidates:
        try:
            v = float(c)
            if 0 <= v <= 10:
                return v
        except ValueError:
            pass
    return -1.0  # 解析失败，调用方负责兜底


def safe_temperature(t: float) -> float:
    """MiniMax 等接口要求 temperature ∈ (0, 1]。"""
    return max(0.01, min(1.0, t))


def split_critic_layers(text: str) -> tuple[str, str]:
    """
    从 Critic 全文拆出架构层 / 文字层正文（不含「路由」段）。

    支持多种格式变体：
    - ### 架构层 / ### 架构层反馈 / ### 架构层审阅意见
    - ### 文字层 / ### 文字层反馈 / ### 文字层审阅意见
    - 架构层：... / 文字层：...
    如果正则无法匹配，返回空字符串，由调用方兜底处理。
    """
    arch = ""
    prose = ""
    t = text or ""

    # 尝试多种标题变体
    arch_patterns = [
        # Markdown 标题格式
        r"(?:###|##|#)\s*架构[层-]?[\u4e00-\u9fff]*[^\n]*\n([\s\S]*?)(?=(?:###|##|#)\s*文字)",
        r"(?:###|##|#)\s*架构层反馈[^\n]*\n([\s\S]*?)(?=(?:###|##|#)\s*文字)",
        # 中文冒号格式
        r"架构层[：:][^\n]*\n([\s\S]*?)(?=文字层)",
        # 简单冒号格式（前面没有标题标记）
        r"(?<!\S)架构层[：:]\s*\n?([\s\S]*?)(?=文字层)",
    ]
    prose_patterns = [
        # Markdown 标题格式
        r"(?:###|##|#)\s*文字[层-]?[\u4e00-\u9fff]*[^\n]*\n([\s\S]*?)(?=(?:###|##|#)\s*路由)",
        r"(?:###|##|#)\s*文字层反馈[^\n]*\n([\s\S]*?)(?=(?:###|##|#)\s*路由)",
        # 中文冒号格式
        r"文字层[：:][^\n]*\n([\s\S]*?)(?=路由)",
        # 简单冒号格式
        r"(?<!\S)文字层[：:]\s*\n?([\s\S]*?)(?=路由)",
    ]

    for pat in arch_patterns:
        m = re.search(pat, t, re.I | re.M)
        if m and m.group(1).strip():
            arch = m.group(1).strip()
            break

    for pat in prose_patterns:
        m = re.search(pat, t, re.I | re.M)
        if m and m.group(1).strip():
            prose = m.group(1).strip()
            break

    # 如果都匹配不到，尝试用前 2/3 和后 1/3 分割（fallback）
    if not arch and not prose:
        lines = t.split("\n")
        if len(lines) >= 6:
            # 尝试找到中间分割点（架构层和文字层之间）
            for i, line in enumerate(lines):
                if re.search(r"文字[层-]?[\u4e00-\u9fff]*[：:]", line, re.I):
                    arch = "\n".join(lines[:i]).strip()
                    prose = "\n".join(lines[i+1:]).strip()
                    break
            # 再试另一种常见格式
            if not arch:
                third = max(2, len(lines) // 3)
                arch = "\n".join(lines[:third]).strip()
                prose = "\n".join(lines[third:]).strip()

    return arch, prose


def parse_critic_actions(text: str) -> tuple[str, str]:
    """
    返回 (arch_action, prose_action)，取值 revise|keep / rewrite|keep。

    支持多种格式：
    - ARCH_ACTION: revise
    - 架构层动作：revise
    - [ARCH] revise
    - 架构层：revise
    """
    t = text or ""

    # 标准格式
    am = re.search(r"ARCH_ACTION:\s*(revise|keep)\b", t, re.I)
    pm = re.search(r"PROSE_ACTION:\s*(rewrite|keep)\b", t, re.I)

    # 备选：中文冒号格式
    if not am:
        am = re.search(r"架构[层-]?[\u4e00-\u9fff]*[：:]\s*(revise|keep)\b", t, re.I)
    if not pm:
        pm = re.search(r"文字[层-]?[\u4e00-\u9fff]*[：:]\s*(rewrite|keep)\b", t, re.I)

    # 备选：方括号格式
    if not am:
        am = re.search(r"\[ARCH\]\s*(revise|keep)\b", t, re.I)
    if not pm:
        pm = re.search(r"\[PROSE\]\s*(rewrite|keep)\b", t, re.I)

    # 备选：单独一行的 revise/keep
    if not am:
        am = re.search(r"ARCH[_\s]*(?:ACTION\s*)?[:：]?\s*(revise|keep)\b", t, re.I)
    if not pm:
        pm = re.search(r"PROSE[_\s]*(?:ACTION\s*)?[:：]?\s*(rewrite|keep)\b", t, re.I)

    aa = am.group(1).lower() if am else "keep"
    pa = pm.group(1).lower() if pm else "keep"
    return aa, pa


def default_actions_when_stuck(
    score: float,
    score_pass: float,
    arch_action: str,
    prose_action: str,
) -> tuple[str, str]:
    """未达标且模型未给出有效路由时，避免死循环：默认至少推动文字层重写。"""
    if score >= score_pass:
        return arch_action, prose_action
    if arch_action == "keep" and prose_action == "keep":
        return arch_action, "rewrite"
    return arch_action, prose_action


# =============================================
# 新增：结构化记忆解析
# =============================================

def parse_structured_json_from_text(text: str) -> Optional[dict]:
    """
    从文本末尾提取 JSON 结构化数据。

    匹配 ```json ... ``` 块。
    """
    if not text:
        return None

    pattern = r"```json\s*([\s\S]*?)\s*```"
    match = re.search(pattern, text)

    if not match:
        return None

    json_str = match.group(1).strip()
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        return None


def parse_memory_delta(text: str) -> dict:
    """
    从记忆文本中解析记忆增量。

    Returns:
        dict，包含 character_changes, power_breakthroughs, item_changes,
        plot_threads_updated, new_constraints 等字段
    """
    structured = parse_structured_json_from_text(text)
    if not structured:
        return {}

    return {
        "character_updates": structured.get("character_changes", []),
        "new_characters": structured.get("new_characters", []),
        "power_breakthroughs": structured.get("power_breakthroughs", []),
        "item_changes": structured.get("items_obtained", []),
        "plot_threads_updated": structured.get("plot_threads_updated", []),
        "new_constraints": structured.get("new_constraints", []),
        "location_changes": structured.get("location_changes", []),
        "new_character_appearance": bool(structured.get("new_characters")),
        "major_realm_breakthrough": any(
            pb.get("is_major", False)
            for pb in structured.get("power_breakthroughs", [])
        ),
        "main_thread_resolution": any(
            pt.get("action") == "resolved" and pt.get("is_main", False)
            for pt in structured.get("plot_threads_updated", [])
        ),
    }


def parse_character_states(text: str) -> list[dict]:
    """从记忆文本中解析人物状态列表。"""
    delta = parse_memory_delta(text)
    if delta.get("character_updates"):
        return delta["character_updates"]

    # 备用：从 Markdown 表格中解析
    states = []
    pattern = r"\|\s*(\S+)\s*\|\s*([^|]+)\s*\|\s*([^|]+)\s*\|"
    matches = re.findall(pattern, text)

    for name, location, power in matches:
        if name not in ("角色", "人物", "名称"):
            states.append({
                "name": name.strip(),
                "location": location.strip(),
                "power": power.strip(),
            })

    return states


def parse_power_breakthroughs(text: str) -> list[dict]:
    """从记忆文本中解析战力突破记录。"""
    delta = parse_memory_delta(text)
    return delta.get("power_breakthroughs", [])


def parse_plot_threads(text: str) -> list[dict]:
    """从记忆文本中解析伏笔列表。"""
    delta = parse_memory_delta(text)
    if delta.get("plot_threads_updated"):
        return delta["plot_threads_updated"]

    # 备用：从 Markdown 表格解析
    threads = []
    pattern = r"([A-Z]\d+)[^\n]*\|\s*([^\n]+)"
    matches = re.findall(pattern, text)

    for code, desc in matches:
        threads.append({
            "code": code.strip(),
            "description": desc.strip(),
        })

    return threads


def extract_memory_sections(text: str) -> dict[str, str]:
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

    pattern = r"(##\s+[^\n]+)\n([\s\S]*?)(?=##\s+|\Z)"
    matches = re.findall(pattern, text)

    for title, content in matches:
        section_name = re.sub(r"^##\s+", "", title).strip()
        sections[section_name] = content.strip()

    return sections


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
    ]
    return any(
        memory_delta.get(t) for t in triggers
    ) or any(
        pt.get("action") == "resolved"
        for pt in memory_delta.get("plot_threads_updated", [])
    )
