"""情节插入执行器"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from writing_langgraph.db import (
    Chapter,
    Character,
    CharacterRelationship,
    PlotThread,
    get_db,
    json_dumps,
)


@dataclass
class InsertPlan:
    """情节插入计划"""
    user_description: str
    insert_after_chapter: int
    estimated_chapters: int
    core_conflict: str
    main_characters: list[str]
    start_state: str
    end_state: str
    strong_impact_start: int
    strong_impact_end: int
    weak_impact_start: int
    weak_impact_end: int
    new_characters: list[dict]
    plot_thread_updates: list[dict]


# =============================================
# 1. 更新全局记忆
# =============================================

def update_memory_for_insert(novel_id: int, plan: InsertPlan) -> dict:
    """
    根据插入计划更新全局记忆。

    包括：
    1. 新增角色到 character 表
    2. 更新伏笔状态（修改/新增）
    3. 更新人物关系

    Returns:
        更新摘要 {"characters_added": N, "threads_updated": N}
    """
    result = {"characters_added": 0, "threads_updated": 0}

    with get_db(novel_id) as conn:
        # 1. 新增角色
        for char_data in plan.new_characters:
            try:
                conn.execute(
                    """
                    INSERT INTO character
                    (novel_id, name, alias, role_type, core_motivation, core_flaw,
                     arc_direction, current_power_level, first_appearance_chapter)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        novel_id,
                        char_data.get("name", ""),
                        char_data.get("alias", ""),
                        char_data.get("role_type", "supporting"),
                        char_data.get("motivation", ""),
                        char_data.get("flaw", ""),
                        char_data.get("arc_direction", ""),
                        char_data.get("power_level", ""),
                        plan.insert_after_chapter + 1,
                    ),
                )
                result["characters_added"] += 1
            except sqlite3.Error:
                pass  # 角色可能已存在

        # 2. 更新/新增伏笔
        for thread_data in plan.plot_thread_updates:
            action = thread_data.get("action", "update")
            thread_code = thread_data.get("code", "")

            if action == "new":
                # 新增伏笔
                try:
                    conn.execute(
                        """
                        INSERT INTO plot_thread
                        (novel_id, thread_code, title, content_summary,
                         planted_chapter, status)
                        VALUES (?, ?, ?, ?, ?, 'planted')
                        """,
                        (
                            novel_id,
                            thread_code,
                            thread_data.get("title", ""),
                            thread_data.get("content", ""),
                            plan.insert_after_chapter + 1,
                        ),
                    )
                    result["threads_updated"] += 1
                except sqlite3.Error:
                    pass
            elif action == "update" and thread_code:
                # 更新已有伏笔
                new_content = thread_data.get("new_content", "")
                new_status = thread_data.get("status", "")
                try:
                    if new_content:
                        conn.execute(
                            "UPDATE plot_thread SET content_summary = ? WHERE novel_id = ? AND thread_code = ?",
                            (new_content, novel_id, thread_code),
                        )
                    if new_status:
                        conn.execute(
                            "UPDATE plot_thread SET status = ? WHERE novel_id = ? AND thread_code = ?",
                            (new_status, novel_id, thread_code),
                        )
                    result["threads_updated"] += 1
                except sqlite3.Error:
                    pass

        # 3. 建立新人物关系
        for rel_data in plan.new_characters:
            # 如果新角色和主角有关系，建立关系
            if rel_data.get("relationship_to_protagonist"):
                # 获取主角 ID
                protagonist = conn.execute(
                    "SELECT id FROM character WHERE novel_id = ? AND role_type = 'protagonist' LIMIT 1",
                    (novel_id,),
                ).fetchone()

                new_char = conn.execute(
                    "SELECT id FROM character WHERE novel_id = ? AND name = ? LIMIT 1",
                    (novel_id, rel_data.get("name", "")),
                ).fetchone()

                if protagonist and new_char:
                    try:
                        conn.execute(
                            """
                            INSERT INTO character_relationship
                            (novel_id, char_a_id, char_b_id, relationship_type,
                             description, start_chapter)
                            VALUES (?, ?, ?, ?, ?, ?)
                            """,
                            (
                                novel_id,
                                protagonist["id"],
                                new_char["id"],
                                rel_data.get("relationship_to_protagonist"),
                                rel_data.get("relationship_desc", ""),
                                plan.insert_after_chapter + 1,
                            ),
                        )
                    except sqlite3.Error:
                        pass  # 关系可能已存在

    return result


# =============================================
# 2. 重新编号章节
# =============================================

def renumber_chapters(
    novel_id: int,
    start_from: int,
    offset: int,
) -> list[tuple[int, int]]:
    """
    将指定章节号之后的章节重新编号。

    Args:
        novel_id: 小说 ID
        start_from: 从哪章开始重新编号
        offset: 偏移量（通常是正数，表示向后插入）

    Returns:
        [(旧章节号, 新章节号), ...] 的列表
    """
    changes = []

    with get_db(novel_id) as conn:
        # 获取需要重新编号的章节
        rows = conn.execute(
            """
            SELECT id, chapter_order FROM chapter
            WHERE novel_id = ? AND chapter_order >= ?
            ORDER BY chapter_order DESC
            """,
            (novel_id, start_from),
        ).fetchall()

        for row in rows:
            old_order = row["chapter_order"]
            new_order = old_order + offset
            conn.execute(
                "UPDATE chapter SET chapter_order = ? WHERE id = ?",
                (new_order, row["id"]),
            )
            changes.append((old_order, new_order))

    return changes


# =============================================
# 3. 生成铺垫章节
# =============================================

def generate_setup_chapters(
    novel_id: int,
    plan: InsertPlan,
    llm,
    max_iterations: int = 4,
    score_pass: float = 8.0,
) -> list[int]:
    """
    生成铺垫章节（第31-34章）。

    这些章节需要在第30章结尾埋伏笔，为新情节做铺垫。

    Args:
        novel_id: 小说 ID
        plan: 插入计划
        llm: LLM 实例
        max_iterations: 最大迭代次数
        score_pass: 及格分数

    Returns:
        生成的章节号列表
    """
    from writing_langgraph.graph import build_writing_graph
    from writing_langgraph.memory.chapter_memory import create_chapter, update_chapter
    from writing_langgraph.memory.global_memory import load_global_memory

    generated = []
    global_mem = load_global_memory(novel_id)

    # 铺垫章节从 insert_after_chapter + 1 开始
    start_ch = plan.insert_after_chapter + 1
    setup_count = plan.strong_impact_start - start_ch  # 铺垫章节数量

    if setup_count <= 0:
        return generated

    for i in range(setup_count):
        chapter_no = start_ch + i

        # 创建章节
        chapter = create_chapter(
            novel_id=novel_id,
            chapter_order=chapter_no,
            brief=f"铺垫章节：为即将到来的{plan.core_conflict}做铺垫",
        )

        # 构建上下文
        context = f"""
【全局记忆】
{global_mem.content if global_mem else ''}

【本章任务】
在第{chapter_no}章，你需要：
1. 引入/铺垫新角色（{', '.join(c['name'] for c in plan.new_characters)}）
2. 为'{plan.core_conflict}'埋下伏笔
3. 保持与前文的连贯性

【用户描述的新情节】
{plan.user_description}
"""

        # 使用写作图生成章节
        from writing_langgraph.graph import planner_node, writer_node, critic_node
        from writing_langgraph.state import initial_state

        state = initial_state(
            story_idea=context,
            chapter_task=f"铺垫：为{plan.core_conflict}做铺垫",
            chapter_no=chapter_no,
            novel_id=novel_id,
            max_iterations=max_iterations,
            score_pass=score_pass,
            output_dir=f"novel_output/{novel_id}",
            plan=global_mem.content if global_mem else "",
        )

        # Planner
        plan_result = planner_node(state, llm)
        state["plan"] = plan_result.get("plan", "") if isinstance(plan_result, dict) else plan_result

        # Writer → Critic 迭代
        for _ in range(max_iterations):
            draft_result = writer_node(state, llm)
            state["draft"] = draft_result.get("draft", "") if isinstance(draft_result, dict) else draft_result
            result = critic_node(state, llm)
            state.update(result)
            if result.get("score", 0) >= score_pass:
                break

        # 更新章节
        update_chapter(
            novel_id=novel_id,
            chapter_id=chapter.id,
            draft=state.get("draft", ""),
            plan=state.get("plan", ""),
            score=state.get("score", 0),
            status="finalized",
        )
        generated.append(chapter_no)

    return generated


# =============================================
# 4. 生成新情节主体
# =============================================

def generate_inserted_plot(
    novel_id: int,
    plan: InsertPlan,
    llm,
    max_iterations: int = 4,
    score_pass: float = 8.0,
) -> list[int]:
    """
    生成新插入的情节主体章节（第35-85章）。

    Args:
        novel_id: 小说 ID
        plan: 插入计划
        llm: LLM 实例
        max_iterations: 最大迭代次数
        score_pass: 及格分数

    Returns:
        生成的章节号列表
    """
    from writing_langgraph.graph import build_writing_graph
    from writing_langgraph.memory.chapter_memory import create_chapter, update_chapter
    from writing_langgraph.memory.global_memory import load_global_memory

    generated = []

    # 情节主体章节范围
    start_ch = plan.strong_impact_start
    end_ch = plan.strong_impact_end

    global_mem = load_global_memory(novel_id)

    # 将新情节分成若干阶段
    # 例如：铺垫→冲突→高潮→转折→收尾
    stages = [
        ("引入阶段", "介绍新角色，建立冲突"),
        ("冲突升级", "主角与仇人/对手的对抗"),
        ("危机爆发", "主角陷入最大危机"),
        ("绝地反击", "神秘人出现，主角获救"),
        ("复仇完成", "主角成功复仇"),
        ("新的开始", "复仇后主角的改变和新目标"),
    ]

    chapters_per_stage = (end_ch - start_ch + 1) // len(stages)

    current_chapter = start_ch

    for stage_idx, (stage_name, stage_desc) in enumerate(stages):
        stage_start = current_chapter
        stage_end = min(current_chapter + chapters_per_stage - 1, end_ch)

        for ch in range(stage_start, stage_end + 1):
            # 创建章节
            chapter = create_chapter(
                novel_id=novel_id,
                chapter_order=ch,
                brief=f"{stage_name}：{stage_desc}",
            )

            # 构建上下文
            context = f"""
【全局记忆】
{global_mem.content if global_mem else ''}

【当前阶段】：{stage_name} - {stage_desc}

【情节概述】
{plan.user_description}

【本章任务】
写第{ch}章，属于"{stage_name}"阶段。
- 核心冲突：{plan.core_conflict}
- 主要角色：{', '.join(plan.main_characters)}
- 起始状态：{plan.start_state}
- 结尾状态：{plan.end_state}

请按照{stage_name}的节奏写本章内容。
"""

            # 使用写作图生成
            from writing_langgraph.graph import planner_node, writer_node, critic_node
            from writing_langgraph.state import initial_state

            state = initial_state(
                story_idea=context,
                chapter_task=f"{stage_name}：{stage_desc}",
                chapter_no=ch,
                novel_id=novel_id,
                max_iterations=max_iterations,
                score_pass=score_pass,
                output_dir=f"novel_output/{novel_id}",
                plan=global_mem.content if global_mem else "",
            )

            # Planner
            plan_result = planner_node(state, llm)
            state["plan"] = plan_result.get("plan", "") if isinstance(plan_result, dict) else plan_result

            # Writer → Critic 迭代
            for _ in range(max_iterations):
                draft_result = writer_node(state, llm)
                state["draft"] = draft_result.get("draft", "") if isinstance(draft_result, dict) else draft_result
                result = critic_node(state, llm)
                state.update(result)
                if result.get("score", 0) >= score_pass:
                    break

            # 更新章节
            update_chapter(
                novel_id=novel_id,
                chapter_id=chapter.id,
                draft=state.get("draft", ""),
                plan=state.get("plan", ""),
                score=state.get("score", 0),
                status="finalized",
            )
            generated.append(ch)

        current_chapter = stage_end + 1

    return generated


# =============================================
# 5. 调整后续章节
# =============================================

def adjust_following_chapters(
    novel_id: int,
    plan: InsertPlan,
    llm,
    max_iterations: int = 2,
) -> list[int]:
    """
    调整后续章节（第86章及后续）。

    根据复仇结局调整：
    1. 人物状态（如果主角在复仇中死亡/受伤等）
    2. 人物关系（如果仇人死了，相关关系需要更新）
    3. 后续剧情逻辑（如果有新的敌人/目标）

    Args:
        novel_id: 小说 ID
        plan: 插入计划
        llm: LLM 实例
        max_iterations: 最大迭代次数

    Returns:
        调整后的章节号列表
    """
    from writing_langgraph.memory.chapter_memory import get_chapter_by_order, update_chapter
    from writing_langgraph.memory.global_memory import load_global_memory

    adjusted = []
    global_mem = load_global_memory(novel_id)

    # 后续章节范围
    start_ch = plan.weak_impact_start
    end_ch = plan.weak_impact_end

    for ch in range(start_ch, end_ch + 1):
        # 获取原章节
        chapter = get_chapter_by_order(novel_id, ch)
        if not chapter or not chapter.draft:
            continue

        # 检查是否需要调整
        needs_adjustment = False
        reasons = []

        # 简单检测：如果章节内容涉及已死亡的角色，需要调整
        for char_data in plan.new_characters:
            if char_data.get("dies_in_story", False):
                if char_data["name"] in chapter.draft:
                    needs_adjustment = True
                    reasons.append(f"涉及已死亡角色 {char_data['name']}")

        if not needs_adjustment:
            continue

        # 需要调整，调用 LLM 修改
        adjustment_context = f"""
【原始章节】
{(chapter.draft or '')[:2000]}...

【新情节结局摘要】
{plan.user_description}

【需要调整的原因】
{', '.join(reasons)}

【调整要求】
1. 移除/替换涉及已死亡角色的内容
2. 保持与复仇结局的逻辑一致
3. 不要改变章节的核心剧情，只做最小改动

请重写本章，使内容与复仇结局一致。
"""

        # 调用 LLM 重写
        from writing_langgraph.prompts import WRITER_SYSTEM
        from langchain_core.messages import HumanMessage, SystemMessage

        response = llm.bind(temperature=0.7).invoke([
            SystemMessage(content=WRITER_SYSTEM),
            HumanMessage(content=adjustment_context),
        ])
        new_draft = response.content if hasattr(response, "content") else str(response)

        # 更新章节
        update_chapter(
            novel_id=novel_id,
            chapter_id=chapter.id,
            draft=new_draft,
            status="finalized",
        )
        adjusted.append(ch)

    return adjusted


# =============================================
# 主执行函数
# =============================================

def execute_plot_insert(
    novel_id: int,
    plan: InsertPlan,
    llm,
    max_iterations: int = 4,
    score_pass: float = 8.0,
) -> dict:
    """
    执行情节插入的完整流程。

    Args:
        novel_id: 小说 ID
        plan: 插入计划
        llm: LLM 实例
        max_iterations: 最大迭代次数
        score_pass: 及格分数

    Returns:
        执行结果摘要
    """
    result = {
        "status": "started",
        "memory_updated": False,
        "chapters_renumbered": [],
        "setup_chapters": [],
        "new_plot_chapters": [],
        "adjusted_chapters": [],
        "errors": [],
    }

    try:
        # 1. 更新全局记忆
        mem_result = update_memory_for_insert(novel_id, plan)
        result["memory_updated"] = True
        result["memory_update_details"] = mem_result

        # 2. 重新编号章节（为新情节腾出章节号）
        # 实际新情节需要多少章节？这里预留
        estimated_new = plan.estimated_chapters
        renumber_changes = renumber_chapters(
            novel_id,
            plan.insert_after_chapter + 1,
            estimated_new,
        )
        result["chapters_renumbered"] = renumber_changes

        # 3. 生成铺垫章节
        # 铺垫章节数 = 预计新情节开始章节 - 插入点后第一章
        result["setup_chapters"] = generate_setup_chapters(
            novel_id, plan, llm, max_iterations, score_pass
        )

        # 4. 生成新情节主体
        result["new_plot_chapters"] = generate_inserted_plot(
            novel_id, plan, llm, max_iterations, score_pass
        )

        # 5. 调整后续章节
        result["adjusted_chapters"] = adjust_following_chapters(
            novel_id, plan, llm, max_iterations=2
        )

        result["status"] = "completed"

    except Exception as e:
        result["status"] = "failed"
        result["errors"].append(str(e))

    return result
