"""Memory 工具函数 - 供 LLM 调用查询记忆（已优化：三次查询合并为一次）"""

from __future__ import annotations

import sqlite3

from langchain_core.tools import tool

from writing_langgraph.memory.chapter_memory import get_recent_chapters
from writing_langgraph.memory.global_memory import load_global_memory


@tool
def get_full_context(novel_id: int) -> str:
    """
    获取小说的完整上下文（已合并 pending_plot_threads 和 chapters_summary）。

    在进行情节插入分析前，必须先调用此工具获取：
    - 全局记忆（世界观、战力体系、人物模板）
    - 人物状态表
    - 人物关系网
    - 活跃伏笔列表
    - 待处理伏笔（未来10章）
    - 前后章节摘要

    Args:
        novel_id: 小说ID

    Returns:
        格式化的完整上下文文本
    """
    from writing_langgraph.db import get_db

    # 全局记忆
    mem = load_global_memory(novel_id)
    global_ctx = mem.content if mem else "（暂无全局记忆）"

    # 一次性查询所有 DB 数据（合并 3 次独立查询）
    try:
        with get_db(novel_id) as conn:
            # 人物状态
            char_rows = conn.execute(
                """
                SELECT name, role_type, current_power_level, current_location
                FROM character
                WHERE novel_id = ? AND is_active = 1
                ORDER BY first_appearance_chapter
                """,
                (novel_id,),
            ).fetchall()

            # 人物关系
            rel_rows = conn.execute(
                """
                SELECT a.name as char_a, b.name as char_b, cr.relationship_type
                FROM character_relationship cr
                JOIN character a ON cr.char_a_id = a.id
                JOIN character b ON cr.char_b_id = b.id
                WHERE cr.novel_id = ? AND cr.is_active = 1
                """,
                (novel_id,),
            ).fetchall()

            # 活跃伏笔
            pt_rows = conn.execute(
                """
                SELECT thread_code, title, content_summary, planted_chapter, status
                FROM plot_thread
                WHERE novel_id = ? AND status IN ('planted', 'foreshadowed')
                ORDER BY planted_chapter
                """,
                (novel_id,),
            ).fetchall()

            # 获取最新章节号
            latest_ch = conn.execute(
                "SELECT MAX(chapter_order) as max_ch FROM chapter WHERE novel_id = ?",
                (novel_id,),
            ).fetchone()
            current_ch = latest_ch["max_ch"] or 1

            # 即将回收的伏笔
            pt_resolve = conn.execute(
                """
                SELECT thread_code, title, content_summary, planted_chapter,
                       planned_resolution_chapter, status
                FROM plot_thread
                WHERE novel_id = ?
                  AND status = 'planted'
                  AND planned_resolution_chapter IS NOT NULL
                  AND planned_resolution_chapter BETWEEN ? AND ?
                ORDER BY planned_resolution_chapter
                """,
                (novel_id, current_ch, current_ch + 10),
            ).fetchall()

            # 长期未回收伏笔
            pt_overdue = conn.execute(
                """
                SELECT thread_code, title, content_summary, planted_chapter,
                       planned_resolution_chapter, status
                FROM plot_thread
                WHERE novel_id = ?
                  AND status = 'planted'
                  AND (planned_resolution_chapter IS NULL OR planned_resolution_chapter < ?)
                ORDER BY planted_chapter DESC
                LIMIT 5
                """,
                (novel_id, current_ch),
            ).fetchall()

            # 前后章节摘要（当前章前后各3章）
            ch_rows = conn.execute(
                """
                SELECT chapter_order, brief, draft, title
                FROM chapter
                WHERE novel_id = ? AND status = 'finalized'
                  AND chapter_order BETWEEN ? AND ?
                ORDER BY chapter_order
                """,
                (novel_id, max(1, current_ch - 3), current_ch + 2),
            ).fetchall()

    except sqlite3.Error:
        char_rows = rel_rows = pt_rows = pt_resolve = pt_overdue = ch_rows = []
        current_ch = 1

    # 构建人物状态文本
    char_lines = ["## 人物状态\n"]
    if char_rows:
        for r in char_rows:
            char_lines.append(
                f"- **{r['name']}** | {r['role_type']} | "
                f"{r['current_power_level'] or '未知'} | {r['current_location'] or '未知'}"
            )
    else:
        char_lines.append("（暂无人物数据）")

    # 构建人物关系文本
    rel_lines = ["## 人物关系\n"]
    if rel_rows:
        for r in rel_rows:
            rel_lines.append(f"- **{r['char_a']}** —[{r['relationship_type']}]→ **{r['char_b']}**")
    else:
        rel_lines.append("（暂无人物关系数据）")

    # 构建伏笔文本
    pt_lines = ["## 活跃伏笔\n"]
    if pt_rows:
        for r in pt_rows:
            pt_lines.append(
                f"- **{r['thread_code']}** {r['title'] or ''} "
                f"(埋于第{r['planted_chapter']}章)"
            )
    else:
        pt_lines.append("（暂无活跃伏笔）")

    # 构建待处理伏笔文本
    pending_lines = ["## 待处理伏笔\n"]
    if pt_resolve:
        pending_lines.append("\n### 🔄 即将回收\n")
        for r in pt_resolve:
            pending_lines.append(
                f"- **{r['thread_code']}** {r['title'] or ''}\n"
                f"  埋于第{r['planted_chapter']}章，计划第{r['planned_resolution_chapter']}章回收\n"
                f"  内容：{(r['content_summary'] or '')[:50]}..."
            )
    else:
        pending_lines.append("\n### 🔄 即将回收\n（无）")

    if pt_overdue:
        pending_lines.append("\n### ⚠️ 长期未回收（可能被遗忘）\n")
        for r in pt_overdue:
            planned = r['planned_resolution_chapter'] or '未计划'
            pending_lines.append(
                f"- **{r['thread_code']}** {r['title'] or ''}\n"
                f"  埋于第{r['planted_chapter']}章，计划第{planned}章回收\n"
                f"  内容：{(r['content_summary'] or '')[:50]}..."
            )

    # 构建章节摘要文本
    summary_lines = ["## 前后章节摘要\n"]
    if ch_rows:
        for r in ch_rows:
            title = r['title'] or f"第{r['chapter_order']}章"
            brief = r['brief'] or "（无章节任务描述）"
            preview = (r['draft'] or '')[:200].replace("\n", " ") if r['draft'] else ""
            summary_lines.append(f"### {title}")
            summary_lines.append(f"章节任务：{brief}")
            if preview:
                summary_lines.append(f"正文预览：{preview}...")
            summary_lines.append("")
    else:
        summary_lines.append(f"（第{max(1, current_ch-3)}-{current_ch+2}章暂无内容）")

    return f"""{'='*50}
## 全局记忆
{'='*50}
{global_ctx}

{'='*50}
## 人物状态
{'='*50}
{chr(10).join(char_lines)}

{'='*50}
## 人物关系
{'='*50}
{chr(10).join(rel_lines)}

{'='*50}
## 活跃伏笔
{'='*50}
{chr(10).join(pt_lines)}

{chr(10).join(pending_lines)}

{''.join(summary_lines)}"""


@tool
def get_chapters_summary(novel_id: int, start_chapter: int, end_chapter: int) -> str:
    """
    获取指定章节范围的摘要。

    注意：此工具已在 get_full_context 中被调用，
    如需单独使用可调用本函数。

    Args:
        novel_id: 小说ID
        start_chapter: 起始章节号
        end_chapter: 结束章节号

    Returns:
        格式化的章节摘要
    """
    chapters = get_recent_chapters(novel_id, limit=999)
    filtered = [c for c in chapters if start_chapter <= c.chapter_order <= end_chapter]
    filtered.sort(key=lambda x: x.chapter_order)

    if not filtered:
        return f"（第{start_chapter}-{end_chapter}章暂无内容）"

    lines = [f"## 第{start_chapter}-{end_chapter}章摘要\n"]
    for ch in filtered:
        brief = ch.brief or "（无章节任务描述）"
        title = ch.title or f"第{ch.chapter_order}章"
        lines.append(f"### {title}")
        lines.append(f"章节任务：{brief}")
        if ch.draft:
            preview = ch.draft[:200].replace("\n", " ")
            lines.append(f"正文预览：{preview}...")
        lines.append("")

    return "\n".join(lines)


@tool
def get_character_power_history(novel_id: int, character_name: str) -> str:
    """查询某人物的战力变化历史"""
    try:
        from writing_langgraph.db import get_db
        with get_db(novel_id) as conn:
            row = conn.execute(
                "SELECT id FROM character WHERE novel_id = ? AND name LIKE ?",
                (novel_id, f"%{character_name}%"),
            ).fetchone()

            if not row:
                return f"未找到角色：{character_name}"

            char_id = row["id"]
            rows = conn.execute(
                """
                SELECT from_level, to_level, chapter_no, cause, created_at
                FROM power_change_log
                WHERE character_id = ?
                ORDER BY chapter_no DESC
                """,
                (char_id,),
            ).fetchall()

            if not rows:
                return f"角色 {character_name} 暂无战力变化记录"

            lines = [f"## {character_name} 战力变化历史\n"]
            for r in rows:
                lines.append(
                    f"- 第{r['chapter_no']}章：{r['from_level']} → {r['to_level']} "
                    f"(原因：{r['cause'] or '未知'})"
                )
            return "\n".join(lines)
    except Exception as e:
        return f"查询失败：{e}"


@tool
def get_plot_thread_detail(novel_id: int, thread_code: str) -> str:
    """查询指定伏笔的详细信息"""
    try:
        from writing_langgraph.db import get_db
        with get_db(novel_id) as conn:
            row = conn.execute(
                "SELECT * FROM plot_thread WHERE novel_id = ? AND thread_code = ?",
                (novel_id, thread_code),
            ).fetchone()

            if not row:
                return f"未找到伏笔：{thread_code}"

            lines = [
                f"## 伏笔 {thread_code}",
                f"**标题**：{row['title']}",
                f"**内容摘要**：{row['content_summary']}",
                f"**状态**：{row['status']}",
                f"**埋下章节**：第{row['planted_chapter']}章" if row['planted_chapter'] else "",
                f"**计划回收**：第{row['planned_resolution_chapter']}章" if row['planned_resolution_chapter'] else "",
                f"**实际回收**：第{row['actual_resolution_chapter']}章" if row['actual_resolution_chapter'] else "",
            ]
            if row['resolution_summary']:
                lines.append(f"**回收说明**：{row['resolution_summary']}")

            return "\n".join(filter(None, lines))
    except Exception as e:
        return f"查询失败：{e}"


@tool
def get_pending_plot_threads(novel_id: int, within_chapters: int = 10) -> str:
    """
    查询即将需要处理的伏笔。

    注意：此工具已在 get_full_context 中被调用，
    如需单独使用可调用本函数。

    Args:
        novel_id: 小说ID
        within_chapters: 范围（多少章以内）

    Returns:
        待处理伏笔列表
    """
    try:
        from writing_langgraph.db import get_db

        with get_db(novel_id) as conn:
            latest_ch = conn.execute(
                "SELECT MAX(chapter_order) as max_ch FROM chapter WHERE novel_id = ?",
                (novel_id,),
            ).fetchone()
            current_ch = latest_ch["max_ch"] or 1

            rows_resolve = conn.execute(
                """
                SELECT thread_code, title, content_summary, planted_chapter,
                       planned_resolution_chapter, status
                FROM plot_thread
                WHERE novel_id = ?
                  AND status = 'planted'
                  AND planned_resolution_chapter IS NOT NULL
                  AND planned_resolution_chapter BETWEEN ? AND ?
                ORDER BY planned_resolution_chapter
                """,
                (novel_id, current_ch, current_ch + within_chapters),
            ).fetchall()

            rows_overdue = conn.execute(
                """
                SELECT thread_code, title, content_summary, planted_chapter,
                       planned_resolution_chapter, status
                FROM plot_thread
                WHERE novel_id = ?
                  AND status = 'planted'
                  AND (planned_resolution_chapter IS NULL OR planned_resolution_chapter < ?)
                ORDER BY planted_chapter DESC
                LIMIT 5
                """,
                (novel_id, current_ch),
            ).fetchall()

            lines = ["## 待处理伏笔\n"]

            if rows_resolve:
                lines.append("\n### 🔄 即将回收\n")
                for r in rows_resolve:
                    lines.append(
                        f"- **{r['thread_code']}** {r['title'] or ''}\n"
                        f"  埋于第{r['planted_chapter']}章，计划第{r['planned_resolution_chapter']}章回收\n"
                        f"  内容：{(r['content_summary'] or '')[:50]}..."
                    )
            else:
                lines.append("\n### 🔄 即将回收\n（无）")

            if rows_overdue:
                lines.append("\n### ⚠️ 长期未回收（可能被遗忘）\n")
                for r in rows_overdue:
                    planned = r['planned_resolution_chapter'] or '未计划'
                    lines.append(
                        f"- **{r['thread_code']}** {r['title'] or ''}\n"
                        f"  埋于第{r['planted_chapter']}章，计划第{planned}章回收\n"
                        f"  内容：{(r['content_summary'] or '')[:50]}..."
                    )

            return "\n".join(lines)
    except Exception as e:
        return f"查询失败：{e}"


# =============================================
# 规划专用查询（非 @tool，供 Planner 内部调用）
# =============================================

def get_planning_context(novel_id: int, chapter_no: int) -> dict:
    """
    供 Planner 生成 plan_phase 时查询的上下文。
    包含：人物当前状态、活跃伏笔、全局记忆。

    不包含章节摘要（那是 Writer 用的）。

    Returns:
        dict: {
            "character_states": str,   # 人物当前状态（用于规划新情节起点）
            "active_plot_threads": str, # 活跃伏笔列表（用于规划伏笔埋设/回收）
            "global_memory": str,       # 全局记忆（世界观/战力体系/核心约束）
        }
    """
    from writing_langgraph.db import get_db
    import json

    mem = load_global_memory(novel_id)
    global_ctx = mem.content if mem else "（暂无全局记忆）"

    try:
        with get_db(novel_id) as conn:
            char_rows = conn.execute(
                """
                SELECT name, role_type, current_power_level, current_location,
                       psychological_state
                FROM character
                WHERE novel_id = ? AND is_active = 1
                ORDER BY first_appearance_chapter
                """,
                (novel_id,),
            ).fetchall()

            pt_rows = conn.execute(
                """
                SELECT thread_code, title, content_summary, planted_chapter,
                       planned_resolution_chapter, status
                FROM plot_thread
                WHERE novel_id = ? AND status IN ('planted', 'foreshadowed')
                ORDER BY planted_chapter
                """,
                (novel_id,),
            ).fetchall()

    except sqlite3.Error:
        char_rows = []
        pt_rows = []

    char_lines = ["## 人物当前状态\n"]
    if char_rows:
        for r in char_rows:
            psych = ""
            if r['psychological_state']:
                try:
                    psych_dict = json.loads(r['psychological_state'])
                    if psych_dict:
                        latest = list(psych_dict.values())[-1]
                        psych = f"，心理：{latest}"
                except Exception:
                    pass
            char_lines.append(
                f"- **{r['name']}**（{r['role_type']}）"
                f" | 境界：{r['current_power_level'] or '未知'}"
                f" | 位置：{r['current_location'] or '未知'}{psych}"
            )
    else:
        char_lines.append("（暂无人物数据）")

    pt_lines = ["## 活跃伏笔\n"]
    if pt_rows:
        for r in pt_rows:
            planned = f"计划第{r['planned_resolution_chapter']}章回收" if r['planned_resolution_chapter'] else "未计划回收章节"
            pt_lines.append(
                f"- **{r['thread_code']}** {r['title'] or ''}"
                f"（{r['status']}，埋于第{r['planted_chapter']}章，{planned}）"
                f"\n  内容：{(r['content_summary'] or '')[:80]}"
            )
    else:
        pt_lines.append("（暂无活跃伏笔）")

    return {
        "character_states": "\n".join(char_lines),
        "active_plot_threads": "\n".join(pt_lines),
        "global_memory": global_ctx,
    }


def get_macro_context(novel_id: int) -> str:
    """
    供 Planner 生成 plan_macro 时查询的上下文。
    只包含：全局记忆（世界观/战力体系/人物模板）。

    不包含章节摘要、不包含当前人物状态。
    """
    mem = load_global_memory(novel_id)
    global_ctx = mem.content if mem else "（暂无全局记忆）"

    return f"""{'='*50}
## 全局记忆（世界观/战力体系/人物模板/主线伏笔）
{'='*50}
{global_ctx}
"""


# =============================================
# 小故事追踪持久化
# =============================================

def save_small_story_tracking(
    novel_id: int,
    small_story_index: int,
    phase_start_ch: int,
    phase_end_ch: int,
    plan_macro: str,
    plan_phase: str,
) -> bool:
    """
    保存当前小故事追踪状态到数据库。

    Returns:
        True if saved successfully, False otherwise.
    """
    try:
        from writing_langgraph.db import get_db
        with get_db(novel_id) as conn:
            conn.execute("""
                INSERT INTO small_story_tracking
                (novel_id, small_story_index, phase_start_ch, phase_end_ch, plan_macro, plan_phase)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (novel_id, small_story_index, phase_start_ch, phase_end_ch, plan_macro, plan_phase))
        return True
    except Exception:
        return False


def load_small_story_tracking(novel_id: int) -> dict | None:
    """
    从数据库加载最新的小故事追踪状态。

    Returns:
        dict: {
            "small_story_index": int,
            "phase_start_ch": int,
            "phase_end_ch": int,
            "plan_macro": str,
            "plan_phase": str,
            "next_chapter": int,  # 下一个要写的章节
        }
        None if no tracking found.
    """
    try:
        from writing_langgraph.db import get_db
        with get_db(novel_id) as conn:
            row = conn.execute(
                """
                SELECT small_story_index, phase_start_ch, phase_end_ch,
                       plan_macro, plan_phase
                FROM small_story_tracking
                WHERE novel_id = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (novel_id,),
            ).fetchone()

            if row:
                return {
                    "small_story_index": row["small_story_index"],
                    "phase_start_ch": row["phase_start_ch"],
                    "phase_end_ch": row["phase_end_ch"],
                    "plan_macro": row["plan_macro"] or "",
                    "plan_phase": row["plan_phase"] or "",
                    "next_chapter": row["phase_end_ch"] + 1,
                }
    except Exception:
        pass
    return None
