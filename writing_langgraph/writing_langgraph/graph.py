"""LangGraph：双层 Critic → 架构意见回流 Planner / 文字意见回流 Writer；定稿后更新记忆再写入章节文件。"""

from __future__ import annotations

import sqlite3
from typing import Optional
from typing_extensions import Literal

from langchain_core.language_models.chat_models import BaseChatModel
from langgraph.graph import END, START, StateGraph

from writing_langgraph.agents import critic_agent, planner_agent, writer_agent
from writing_langgraph.db import transaction
from writing_langgraph.persist import save_chapter
from writing_langgraph.schemas import CriticResponse
from writing_langgraph.state import (
    ChapterGenerationState,
    GlobalMemory,
    MemoryDelta,
    ParallelContext,
    PlotInsertState,
    VolumeMemory,
    WritingState,
)


# =============================================
# 节点实现（调用共享 agents）
# =============================================

def planner_node(state: WritingState, llm: BaseChatModel) -> dict:
    """策划节点"""
    import logging
    logging.warning(f"[planner_node] START chapter={state.get('chapter_no')}, iteration={state.get('iteration')}")
    result = planner_agent(state, llm)
    plan = result.get("plan", "") if isinstance(result, dict) else result
    chapter_guide = result.get("chapter_guide", "") if isinstance(result, dict) else ""
    logging.warning(f"[planner_node] END chapter={state.get('chapter_no')}, plan_len={len(plan) if plan else 0}, guide_len={len(chapter_guide) if chapter_guide else 0}")
    return {"plan": plan, "chapter_guide": chapter_guide}


def writer_node(state: WritingState, llm: BaseChatModel) -> dict:
    """写作节点"""
    import logging
    nxt = int(state.get("iteration", 0)) + 1
    logging.warning(f"[writer_node] START chapter={state.get('chapter_no')}, iteration={state.get('iteration')} -> {nxt}")
    draft = writer_agent(state, llm)
    logging.warning(f"[writer_node] END chapter={state.get('chapter_no')}, draft_len={len(draft) if draft else 0}")
    return {"draft": draft, "iteration": nxt}


def critic_node(state: WritingState, llm: BaseChatModel) -> dict:
    """审阅节点"""
    response = critic_agent(state, llm)
    return response.to_state_updates()


def save_chapter_node(state: WritingState, llm: BaseChatModel) -> dict:
    """保存章节节点"""
    import logging
    logging.warning(f"[save_chapter] chapter={state.get('chapter_no')}, iteration={state.get('iteration')}, "
                    f"score={state.get('score')}, stopped_reason={state.get('stopped_reason')}")
    novel_id = state.get("novel_id", 0)
    chapter_no = state.get("chapter_no", 1)

    try:
        output_dir = state.get("output_dir")
        draft_val = state.get("draft")
        plan_val = state.get("plan")

        file_path, db_ok = save_chapter(
            novel_id=novel_id,
            chapter_no=chapter_no,
            output_dir=output_dir if output_dir else "novel_output",
            draft=str(draft_val) if draft_val else "",
            chapter_task=str(state.get("chapter_task") or ""),
            score=float(state.get("score", 0)),
            iteration=int(state.get("iteration", 0)),
            plan=str(plan_val) if plan_val else "",
            save_to_file=True,
            save_to_db=True,
        )
        saved_path = str(file_path) if file_path else ""
    except Exception:
        saved_path = ""

    score = float(state.get("score", 0))
    sp = float(state.get("score_pass", 8))
    reason = "score_pass" if score >= sp else "max_iterations"
    return {"saved_chapter_path": saved_path, "stopped_reason": reason}


def memory_update_node(state: WritingState, llm: BaseChatModel) -> dict:
    """记忆更新节点。在章节定稿后提取并保存记忆和伏笔。"""
    novel_id = state.get("novel_id", 0)
    chapter_no = state.get("chapter_no", 1)
    if not novel_id or not state.get("draft"):
        return {}

    # ---------- 1. 提取记忆增量 ----------
    delta: Optional[MemoryDelta] = None
    try:
        delta = _extract_memory_delta(state, llm)
    except (sqlite3.Error, RuntimeError):
        pass

    # ---------- 2. 更新人物状态 ----------
    if delta:
        with transaction(novel_id) as conn:
            _apply_character_updates_conn(novel_id, chapter_no, delta, conn=conn)
            _apply_power_breakthroughs_conn(novel_id, chapter_no, delta, conn=conn)
            _apply_location_changes_conn(novel_id, chapter_no, delta, conn=conn)
            _apply_new_characters_conn(novel_id, chapter_no, delta, conn=conn)

    # ---------- 3. 更新全局记忆 ----------
    if delta and _should_update_global_memory(delta):
        _update_global_memory(novel_id, state.get("chapter_no", 1), state.get("plan") or "", state.get("draft") or "")

    # ---------- 4. 保存章节记忆 ----------
    try:
        from writing_langgraph.db import get_db

        with get_db(novel_id) as conn:
            ch_row = conn.execute(
                "SELECT id FROM chapter WHERE novel_id = ? AND chapter_order = ?",
                (novel_id, chapter_no),
            ).fetchone()

            if ch_row:
                from writing_langgraph.memory.chapter_memory import save_chapter_memory
                mem_text = _build_memory_text(state, delta) or ""
                save_chapter_memory(novel_id, ch_row["id"], int(state.get("iteration", 1)), mem_text)
    except (sqlite3.Error, RuntimeError):
        pass

    # ---------- 5. 提取并保存伏笔 ----------
    plot_extracted = False
    try:
        from writing_langgraph.memory import extract_and_save_plot_threads
        extract_and_save_plot_threads(
            novel_id=novel_id,
            chapter_no=chapter_no,
            draft=state.get("draft", ""),
            plan=state.get("plan", ""),
            llm=llm,
        )
        plot_extracted = True
    except (sqlite3.Error, RuntimeError):
        pass

    return {"plot_extracted": plot_extracted, "memory_updated": True}


# ---- Memory 辅助函数 ----

def _extract_memory_delta(state: WritingState, llm: BaseChatModel) -> Optional[dict]:
    """调用 LLM 从策划+正文中提取 MemoryDelta"""
    from writing_langgraph.prompts import MEMORY_SYSTEM
    import re, json

    prompt = f"""请从以下正文中提取记忆增量（人物状态变化、战力突破、道具获取、伏笔等）。

【策划方案摘要】
{(state.get("plan") or "")[:800]}\n\n
【本章正文】
{(state.get("draft") or "")[:3000]}\n\n
【章节号】
第{state.get("chapter_no", "?")}章

请严格按以下 JSON 格式输出（只返回 JSON，不要其他内容）：
```json
{{
    "character_changes": [
        {{"name": "角色名", "power_delta": "筑基初期→中期", "location_change": "宗门→秘境", "psych_change": "紧张→平静"}}
    ],
    "new_characters": [
        {{"name": "新角色名", "role": "配角", "first_appearance": "本章"}}
    ],
    "power_breakthroughs": [
        {{"name": "角色名", "from": "炼气巅峰", "to": "筑基初期", "is_major": false}}
    ],
    "items_obtained": [
        {{"name": "道具名", "owner": "角色名", "rarity": "稀有"}}
    ],
    "plot_threads_updated": [
        {{"code": "F1", "action": "planted", "description": "发现神秘遗迹入口"}},
        {{"code": "F2", "action": "resolved", "is_main": true, "summary": "主角成功报退婚之仇"}}
    ],
    "new_constraints": ["主角在金丹期前不可离开宗门"],
    "location_changes": [
        {{"name": "角色名", "from": "青云宗", "to": "秘境"}}
    ]
}}
```"""

    try:
        from langchain_core.messages import HumanMessage, SystemMessage
        response = llm.bind(temperature=0.3).invoke([
            SystemMessage(content=MEMORY_SYSTEM),
            HumanMessage(content=prompt),
        ])
        text = response.content if hasattr(response, "content") else str(response)

        m = re.search(r"\{[\s\S]*\}", text)
        if not m:
            return None
        data = json.loads(m.group())

        return {
            "character_updates": data.get("character_changes", []),
            "new_characters": data.get("new_characters", []),
            "power_breakthroughs": data.get("power_breakthroughs", []),
            "item_changes": data.get("items_obtained", []),
            "plot_threads_updated": data.get("plot_threads_updated", []),
            "new_constraints": data.get("new_constraints", []),
            "location_changes": data.get("location_changes", []),
            "new_character_appearance": bool(data.get("new_characters")),
            "major_realm_breakthrough": any(pb.get("is_major", False) for pb in data.get("power_breakthroughs", [])),
            "main_thread_resolution": any(
                pt.get("action") == "resolved" and pt.get("is_main", False)
                for pt in data.get("plot_threads_updated", [])
            ),
        }
    except Exception:
        return None


def _should_update_global_memory(delta: MemoryDelta) -> bool:
    triggers = [
        delta.get("new_character_appearance"),
        delta.get("major_realm_breakthrough"),
        delta.get("main_thread_resolution"),
    ]
    triggers.extend(
        pt.get("action") == "resolved" for pt in delta.get("plot_threads_updated", [])
    )
    return any(triggers)


def _apply_character_updates_conn(novel_id: int, chapter_no: int, delta: MemoryDelta, conn) -> None:
    if not delta.get("character_updates"):
        return
    try:
        import json
        for upd in delta.get("character_updates", []):
            name = upd.get("name", "")
            if not name:
                continue
            psych = upd.get("psych_change", "")
            if psych:
                row = conn.execute(
                    "SELECT psychological_state FROM character WHERE novel_id = ? AND name LIKE ?",
                    (novel_id, f"%{name}%"),
                ).fetchone()
                existing = {}
                if row and row["psychological_state"]:
                    try:
                        existing = json.loads(row["psychological_state"])
                    except json.JSONDecodeError:
                        pass
                existing[f"ch{chapter_no}"] = psych
                conn.execute(
                    "UPDATE character SET psychological_state = ? WHERE novel_id = ? AND name LIKE ?",
                    (json.dumps(existing, ensure_ascii=False), novel_id, f"%{name}%"),
                )
    except sqlite3.Error:
        pass


def _apply_power_breakthroughs_conn(novel_id: int, chapter_no: int, delta: MemoryDelta, conn) -> None:
    if not delta.get("power_breakthroughs"):
        return
    try:
        for pb in delta.get("power_breakthroughs", []):
            name = pb.get("name", "")
            from_level = pb.get("from", "")
            to_level = pb.get("to", "")
            if not name or not to_level:
                continue
            conn.execute(
                "UPDATE character SET current_power_level = ? WHERE novel_id = ? AND name LIKE ?",
                (to_level, novel_id, f"%{name}%"),
            )
            char_row = conn.execute(
                "SELECT id FROM character WHERE novel_id = ? AND name LIKE ?",
                (novel_id, f"%{name}%"),
            ).fetchone()
            if char_row:
                conn.execute(
                    "INSERT INTO power_change_log (novel_id, character_id, from_level, to_level, chapter_no, cause) VALUES (?, ?, ?, ?, ?, ?)",
                    (novel_id, char_row["id"], from_level, to_level, chapter_no, pb.get("cause", "")),
                )
    except sqlite3.Error:
        pass


def _apply_location_changes_conn(novel_id: int, chapter_no: int, delta: MemoryDelta, conn) -> None:
    if not delta.get("location_changes"):
        return
    try:
        for lc in delta.get("location_changes", []):
            name = lc.get("name", "")
            to_loc = lc.get("to", "")
            if not name or not to_loc:
                continue
            conn.execute(
                "UPDATE character SET current_location = ? WHERE novel_id = ? AND name LIKE ?",
                (to_loc, novel_id, f"%{name}%"),
            )
    except sqlite3.Error:
        pass


def _apply_new_characters_conn(novel_id: int, chapter_no: int, delta: MemoryDelta, conn) -> None:
    if not delta.get("new_characters"):
        return
    try:
        for nc in delta.get("new_characters", []):
            name = nc.get("name", "")
            role = nc.get("role", "配角")
            if not name:
                continue
            existing = conn.execute(
                "SELECT id FROM character WHERE novel_id = ? AND name = ?",
                (novel_id, name),
            ).fetchone()
            if not existing:
                conn.execute(
                    "INSERT INTO character (novel_id, name, role_type, current_power_level, current_location, first_appearance_chapter, is_active) VALUES (?, ?, ?, '未知', '未知', ?, 1)",
                    (novel_id, name, role, chapter_no),
                )
    except sqlite3.Error:
        pass


def _update_global_memory(novel_id: int, chapter_no: int, plan: str, draft: str) -> None:
    try:
        from writing_langgraph.memory.global_memory import load_global_memory, save_global_memory
        existing = load_global_memory(novel_id)
        old_content = existing.content if existing else ""
        new_content = old_content + f"\n\n## 第{chapter_no}章记忆增量\n{((draft or '')[:500])}"
        save_global_memory(novel_id, new_content)
    except (sqlite3.Error, OSError):
        pass


def _build_memory_text(state: WritingState, delta: Optional[MemoryDelta]) -> str:
    parts = [f"# 第{state.get('chapter_no', '?')}章记忆\n"]
    parts.append(f"## 策划摘要\n{(state.get('plan') or '')[:300]}\n")
    parts.append(f"## 正文摘要\n{(state.get('draft') or '')[:500]}\n")
    if delta:
        parts.append(
            f"## 增量\n"
            f"- 人物更新: {len(delta.get('character_updates', []))} 项\n"
            f"- 战力突破: {len(delta.get('power_breakthroughs', []))} 项\n"
            f"- 伏笔更新: {len(delta.get('plot_threads_updated', []))} 项\n"
        )
    return "".join(parts)


# =============================================
# 路由决策节点（管理迭代控制状态）
# =============================================

def route_decision_node(state: WritingState) -> dict:
    """
    整合路由决策 + consecutive_keep_count 累加。

    作为节点写入 State（而非传给 conditional_edges mapper），
    使 consecutive_keep_count 可跨迭代累积。
    """
    import logging

    score = float(state.get("score", 0))
    sp = float(state.get("score_pass", 8))
    it = int(state.get("iteration", 0))
    mx = int(state.get("max_iterations", 4))
    aa = str(state.get("arch_action", "keep")).lower()
    pa = str(state.get("prose_action", "keep")).lower()
    keep_count = int(state.get("consecutive_keep_count", 0))
    fw = state.get("force_write", False)

    # 诊断日志
    logging.warning(
        f"[route_decision] START | iter={it}/{mx} | score={score}/{sp} | "
        f"arch={aa} prose={pa} | keep_count={keep_count} | force_write={fw}"
    )

    # 终止条件（最高优先级）
    if it >= mx or score >= sp:
        logging.warning(f"[route_decision] -> 迭代用尽或评分达标，去 memory_update")
        return {"consecutive_keep_count": 0, "_route": "memory_update"}

    # 处理 force_write：打回 writer 重写
    if fw:
        logging.warning(f"[route_decision] -> force_write=True，去 writer（不清零keep_count）")
        return {"force_write": False, "consecutive_keep_count": 0, "_route": "writer"}

    if aa == "revise":
        logging.warning(f"[route_decision] -> arch_action=revise，去 planner")
        return {"consecutive_keep_count": 0, "_route": "planner"}
    if pa == "rewrite":
        logging.warning(f"[route_decision] -> prose_action=rewrite，去 writer")
        return {"consecutive_keep_count": 0, "_route": "writer"}

    # 两者都是 keep → 累计连续 keep 次数
    new_keep_count = keep_count + 1

    # 安全网：只剩 1 次迭代机会时，不再触发 force_write
    if it >= mx - 1:
        logging.warning(f"[route_decision] -> 安全网（只剩1次机会），去 writer")
        return {"consecutive_keep_count": new_keep_count, "_route": "writer"}

    if new_keep_count >= 2:
        logging.warning(f"[route_decision] -> 连续{new_keep_count}次keep，触发 force_write")
        return {"consecutive_keep_count": new_keep_count, "_route": "force_write"}

    logging.warning(f"[route_decision] -> 继续迭代（keep_count={new_keep_count}），去 writer")
    return {"consecutive_keep_count": new_keep_count, "_route": "writer"}


def route_after_critic_v2(state: WritingState) -> str:
    """
    路由决策条件函数。

    直接返回 state["_route"]，该值由 route_decision_node 写入。
    route_decision_node 会更新 consecutive_keep_count 和 _route，
    本函数只负责读取并返回路由目标。

    注意：route_decision_node 先执行并更新状态，
    然后本函数才执行，此时 state["_route"] 应该已经包含了正确的值。
    """
    import logging
    _route = state.get("_route", "writer")
    logging.warning(f"[route_after_critic_v2] _route={_route}")
    return _route


# =============================================
# force_write 节点
# =============================================

def force_write_node(state: WritingState) -> dict:
    """设置 force_write 标志，清零 keep 计数"""
    return {"force_write": True, "consecutive_keep_count": 0}


# =============================================
# 图构建
# =============================================

def build_writing_graph(llm: BaseChatModel):
    """
    构建写作图。

    工作流：
      Planner → Writer → Critic → route_decision → (路由) →
      Planner / Writer / force_write / memory_update → save_chapter → END
    """
    g = StateGraph(WritingState)
    g.add_node("planner", lambda state: planner_node(state, llm))
    g.add_node("writer", lambda state: writer_node(state, llm))
    g.add_node("critic", lambda state: critic_node(state, llm))
    g.add_node("route_decision", route_decision_node)
    g.add_node("force_write", force_write_node)
    g.add_node("memory_update", lambda state: memory_update_node(state, llm))
    g.add_node("save_chapter", lambda state: save_chapter_node(state, llm))

    g.add_edge(START, "planner")
    g.add_edge("planner", "writer")
    g.add_edge("writer", "critic")
    g.add_edge("critic", "route_decision")
    g.add_conditional_edges(
        "route_decision",
        route_after_critic_v2,
        {
            "memory_update": "memory_update",
            "planner": "planner",
            "writer": "writer",
            "force_write": "force_write",
        },
    )
    g.add_edge("force_write", "route_decision")
    g.add_edge("memory_update", "save_chapter")
    g.add_edge("save_chapter", END)

    return g.compile()


# =============================================
# 情节插入子图（已废弃，保留空模块供导入兼容）
# =============================================

def build_plot_insert_graph(llm: BaseChatModel):
    """已废弃，请使用 writing_langgraph.memory.plot_insert.execute_plot_insert"""
    raise NotImplementedError(
        "build_plot_insert_graph 已废弃，"
        "请使用 writing_langgraph.memory.plot_insert.execute_plot_insert"
    )
