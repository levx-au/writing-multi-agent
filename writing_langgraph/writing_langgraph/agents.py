"""共享 Agent 实现 — Planner / Writer / Critic 节点逻辑，供 graph.py 调用"""

from __future__ import annotations

from typing import TYPE_CHECKING

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from writing_langgraph.prompts import (
    CHAPTER_GUIDE_SYSTEM,
    CRITIC_SYSTEM,
    PLANNER_MACRO_SYSTEM,
    PLANNER_PHASE_SYSTEM,
    WRITER_SYSTEM,
)
from writing_langgraph.schemas import CriticResponse
from writing_langgraph.utils import safe_temperature

if TYPE_CHECKING:
    from writing_langgraph.state import WritingState

# 延迟导入 memory tools（避免顶层 sqlite3 import 问题）
_memory_tools_available = False
_get_full_context = None
_get_pending_plot_threads = None
_get_chapters_summary = None


def _ensure_memory_tools():
    global _get_full_context, _get_pending_plot_threads, _get_chapters_summary
    global _memory_tools_available
    if not _memory_tools_available:
        from writing_langgraph.memory.tools import (
            get_full_context,
            get_pending_plot_threads,
            get_chapters_summary,
        )
        _get_full_context = get_full_context
        _get_pending_plot_threads = get_pending_plot_threads
        _get_chapters_summary = get_chapters_summary
        _memory_tools_available = True


def _invoke(msgs: list, temperature: float, llm: BaseChatModel, timeout: int = 180, retries: int = 5) -> str:
    """统一的 LLM 调用，支持重试"""
    import time
    t = safe_temperature(temperature)
    last_err = None
    for attempt in range(retries):
        try:
            r = llm.bind(temperature=t, timeout=timeout).invoke(msgs)
            c = r.content
            if isinstance(c, str):
                return c
            if isinstance(c, list):
                return "".join(
                    item.get("text", str(item)) if isinstance(item, dict) else str(item)
                    for item in c
                )
            return str(c)
        except (TypeError, Exception) as e:
            last_err = e
            err_str = str(e)
            # 处理 MiniMax 等 API 过载错误，等待后重试
            if "overloaded_error" in err_str or "529" in err_str:
                wait = 5 * (attempt + 1)  # 递增等待时间
                print(f"[WARN] API 过载，等待 {wait} 秒后重试...")
                time.sleep(wait)
                continue
            # 其他错误也重试一次
            if attempt < retries - 1:
                time.sleep(2)
                continue
            raise
    raise last_err


def _load_context_for_writer(novel_id: int, chapter_no: int) -> str:
    """为 Writer Agent 加载精简上下文（约束优先）"""
    _ensure_memory_tools()

    try:
        full_ctx = _get_full_context.invoke({"novel_id": novel_id})

        # 提取关键约束（只保留世界规则和核心约束）
        # 这里做简单的文本截取，实际可以进一步优化
        lines = full_ctx.split('\n')
        constraint_lines = []
        capture = False
        for line in lines:
            if '## 世界规则' in line or '## 战力体系' in line or '## 核心约束' in line:
                capture = True
            elif capture and line.startswith('## '):
                capture = False
            elif capture and line.strip():
                constraint_lines.append(line)

        constraints = '\n'.join(constraint_lines[:20])  # 最多20行

        return f"""
{'='*50}
## 本章写作约束
{'='*50}
{constraints if constraints else '（暂无硬性约束）'}

{'='*50}
## 本章任务
{'='*50}
（见上方【本章任务】）
"""
    except Exception:
        return "（上下文加载失败，继续使用已有信息）"


def _load_context_for_critic(novel_id: int, chapter_no: int) -> str:
    """为 Critic Agent 加载上下文"""
    _ensure_memory_tools()

    try:
        # 前后章节摘要
        summary = _get_chapters_summary.invoke({
            "novel_id": novel_id,
            "start_chapter": max(1, chapter_no - 1),
            "end_chapter": chapter_no + 1,
        })

        # 即将回收的伏笔
        pending = _get_pending_plot_threads.invoke({
            "novel_id": novel_id,
            "within_chapters": 10,
        })

        # 人物当前状态（评估人物弧线用）
        from writing_langgraph.memory.tools import get_planning_context
        planning_ctx = get_planning_context(novel_id, chapter_no)
        character_states = planning_ctx.get("character_states", "")
        active_plot = planning_ctx.get("active_plot_threads", "")

        return f"""
{'='*50}
## 前后章节摘要
{'='*50}
{summary}

{'='*50}
## 人物当前状态
{'='*50}
{character_states or '（暂无）'}

{'='*50}
## 活跃伏笔
{'='*50}
{active_plot or '（暂无）'}

{'='*50}
## 即将回收伏笔（10章内）
{'='*50}
{pending or '（暂无）'}
"""
    except Exception:
        return "（上下文加载失败，继续使用已有信息）"


# =============================================
# Planner 专用上下文（按需查询，不浪费）
# =============================================

def _load_context_for_plan_macro(novel_id: int) -> str:
    """
    为 plan_macro 生成提供上下文。
    只包含：全局记忆（世界观/战力体系/人物模板/主线伏笔）。
    不包含：章节摘要、当前人物状态。
    """
    try:
        from writing_langgraph.memory.tools import get_macro_context
        return get_macro_context(novel_id)
    except Exception:
        return "（上下文加载失败，继续使用已有信息）"


def _load_context_for_plan_phase(novel_id: int, chapter_no: int) -> str:
    """
    为 plan_phase 生成提供上下文。
    包含：人物当前状态、活跃伏笔、全局记忆。
    不包含：章节摘要。
    """
    try:
        from writing_langgraph.memory.tools import get_planning_context
        ctx = get_planning_context(novel_id, chapter_no)
        return f"""{'='*50}
## 全局记忆（世界观/战力体系/约束）
{'='*50}
{ctx['global_memory']}

{'='*50}
## 人物当前状态
{'='*50}
{ctx['character_states']}

{'='*50}
## 活跃伏笔
{'='*50}
{ctx['active_plot_threads']}
"""
    except Exception:
        return "（上下文加载失败，继续使用已有信息）"


def _load_context_for_chapter_guide() -> str:
    """
    为 chapter_guide 提取提供上下文。
    不需要查数据库，直接从 plan_phase 计算章节位置。
    """
    return ""


# =============================================
# Planner Agent
# =============================================

def planner_agent(state: "WritingState", llm: BaseChatModel) -> dict:
    """
    增量策划节点实现。

    1. plan_macro（宏观规划）：若为空，根据 story_idea 创建；不变
    2. plan_phase（当前小故事规划）：每次只生成一个小故事
       - 若为空 → 生成第一个小故事
       - 若当前章节超出当前小故事范围 → 生成下一个小故事
       - 若有架构层反馈 → 重建当前小故事
    3. chapter_guide（本章指引）：从 plan_phase 提取

    chapter_task（用户指令）是第一位的。

    Returns:
        包含 plan_macro, plan_phase, plan, chapter_guide,
        current_phase_start_ch, current_phase_end_ch, current_small_story_index 的字典
    """
    from writing_langgraph.prompts import (
        PLANNER_MACRO_SYSTEM,
        PLANNER_PHASE_SYSTEM,
    )

    arch_fb = (state.get("arch_feedback") or "").strip()
    if state.get("arch_action") == "revise" and not arch_fb:
        arch_fb = (state.get("feedback") or "").strip()

    novel_id = state.get("novel_id", 0)
    chapter_no = state.get("chapter_no", 1)

    story_idea = state.get("story_idea", "")
    chapter_task = state.get("chapter_task", "")
    plan_macro = state.get("plan_macro", "")
    plan_phase = state.get("plan_phase", "")
    # 上一章正文结尾（用于章节衔接）
    prev_draft = (state.get("prev_chapter_draft") or "").strip()

    # 当前小故事的章节范围
    current_phase_start_ch = int(state.get("current_phase_start_ch", 0) or 0)
    current_phase_end_ch = int(state.get("current_phase_end_ch", 0) or 0)
    current_small_story_index = int(state.get("current_small_story_index", 0) or 0)

    # ========================================
    # Step 1: 若 plan_macro 为空 → 创建宏观规划
    # ========================================
    if not plan_macro:
        print(f"[Planner] 创建宏观规划...")
        macro_ctx = _load_context_for_plan_macro(novel_id)
        user_macro = (
            f"【创作意图】\n{story_idea}\n\n"
            f"【本章指令】\n{chapter_task or '（暂无，先建宏观框架）'}"
        )
        user_macro += "\n\n" + macro_ctx

        plan_macro = _invoke(
            [SystemMessage(content=PLANNER_MACRO_SYSTEM), HumanMessage(content=user_macro)],
            0.7, llm,
        )
        print(f"[Planner] 宏观规划完成 ({len(plan_macro)} 字)")

    # ========================================
    # Step 2: 判断是否需要生成/更新当前小故事规划
    # ========================================
    needs_phase_update = arch_fb or not plan_phase

    # 检查当前章节是否超出当前小故事的章节范围
    if not needs_phase_update and current_phase_end_ch > 0 and chapter_no > current_phase_end_ch:
        print(f"[Planner] 当前小故事（第{current_phase_start_ch}-{current_phase_end_ch}章）已完成，生成下一个小故事...")
        needs_phase_update = True
        current_small_story_index += 1
        # 旧的 plan_phase 成为历史，不传入
        plan_phase = ""

    if needs_phase_update:
        print(f"[Planner] 生成小故事 #{current_small_story_index + 1}（第{chapter_no}章起）...")
        phase_ctx = _load_context_for_plan_phase(novel_id, chapter_no)
        user_phase = _build_phase_prompt(
            plan_macro=plan_macro,
            plan_phase=plan_phase,
            chapter_task=chapter_task,
            arch_feedback=arch_fb,
            context_extra=phase_ctx,
            start_chapter=chapter_no,
            small_story_index=current_small_story_index + 1,
            prev_draft=prev_draft,
        )

        plan_phase = _invoke(
            [SystemMessage(content=PLANNER_PHASE_SYSTEM), HumanMessage(content=user_phase)],
            0.7, llm,
        )
        print(f"[Planner] 小故事 #{current_small_story_index + 1} 完成 ({len(plan_phase)} 字)")

        # 从 plan_phase 解析章节范围
        phase_start, phase_end = _parse_phase_chapter_range(plan_phase)
        current_phase_start_ch = phase_start or chapter_no
        current_phase_end_ch = phase_end or (chapter_no + 19)

        # 持久化追踪状态到数据库
        if novel_id > 0:
            try:
                from writing_langgraph.memory.tools import save_small_story_tracking
                save_small_story_tracking(
                    novel_id=novel_id,
                    small_story_index=current_small_story_index,
                    phase_start_ch=current_phase_start_ch,
                    phase_end_ch=current_phase_end_ch,
                    plan_macro=plan_macro,
                    plan_phase=plan_phase,
                )
                print(f"[Planner] 追踪状态已保存到数据库")
            except Exception:
                pass

    # ========================================
    # Step 3: 从 plan_phase 提取本章指引
    # ========================================
    chapter_guide = _extract_chapter_guide(
        plan_phase=plan_phase,
        chapter_task=chapter_task,
        chapter_no=chapter_no,
        llm=llm,
    )

    # 兼容字段 plan = macro + phase 合并
    plan_combined = plan_macro + "\n\n" + plan_phase

    return {
        "plan_macro": plan_macro,
        "plan_phase": plan_phase,
        "plan": plan_combined,
        "chapter_guide": chapter_guide,
        "current_phase_start_ch": current_phase_start_ch,
        "current_phase_end_ch": current_phase_end_ch,
        "current_small_story_index": current_small_story_index or 1,
    }


def _build_phase_prompt(
    plan_macro: str,
    plan_phase: str,
    chapter_task: str,
    arch_feedback: str,
    context_extra: str,
    start_chapter: int,
    small_story_index: int,
    prev_draft: str = "",
) -> str:
    """构建小故事生成的 prompt"""
    # 上一章结尾（用于衔接）
    prev_ending = ""
    if prev_draft:
        prev_ending = f"\n\n【上一章结尾】（新章节必须从这里继续，不得偏离）\n{prev_draft[-1500:]}"

    if arch_feedback:
        base = (
            f"【宏观规划】\n{plan_macro}\n\n"
            f"【当前小故事规划】\n{plan_phase or '（暂无）'}\n\n"
            f"【本章指令】\n{chapter_task or '（暂无）'}\n\n"
            f"【架构层审阅意见】（请根据意见修订当前小故事规划）\n{arch_feedback}"
            f"{prev_ending}"
        )
    else:
        prev_story_info = ""
        if plan_phase:
            prev_story_info = (
                f"\n\n【已完成的小故事】\n{plan_phase}\n\n"
                "请基于上述已完成的小故事，规划下一个要写的全新小故事。"
                "注意：不要重复已完成的情节，新小故事必须承接并推进大故事核心目标。"
            )

        base = (
            f"【宏观规划】\n{plan_macro}\n\n"
            f"【本章指令】（最高优先级，据此规划小故事）\n{chapter_task or '继续故事'}\n\n"
            f"【起始章节】第{start_chapter}章\n"
            f"【小故事序号】#{small_story_index}\n"
            f"{prev_story_info}"
            f"{prev_ending}"
        )

    return base + "\n\n" + context_extra


def _parse_phase_chapter_range(plan_phase: str) -> tuple:
    """从 plan_phase 文本中解析章节范围"""
    import re

    # 匹配 "第A章 - 第B章" 或 "第A-B章" 格式
    patterns = [
        r'第(\d+)章\s*[-–]\s*第(\d+)章',
        r'第(\d+)\s*[-–]\s*第(\d+)章',
        r'第(\d+)-(\d+)章',
    ]

    for pattern in patterns:
        m = re.search(pattern, plan_phase)
        if m:
            return int(m.group(1)), int(m.group(2))

    return 0, 0


def _extract_chapter_guide(
    plan_phase: str,
    chapter_task: str,
    chapter_no: int,
    llm: BaseChatModel,
) -> str:
    """从阶段性规划中提取本章写作指引（精简版）"""
    user = (
        f"【阶段性规划】\n{plan_phase}\n\n"
        f"【本章指令】\n{chapter_task}\n\n"
        f"【本章章节号】\n第{chapter_no}章"
    )

    guide = _invoke(
        [SystemMessage(content=CHAPTER_GUIDE_SYSTEM), HumanMessage(content=user)],
        0.3,  # 低温度，更确定性
        llm,
    )

    return guide


# =============================================
# Writer Agent
# =============================================

def writer_agent(state: "WritingState", llm: BaseChatModel) -> str:
    """
    写作节点实现。

    Returns:
        正文文本
    """
    novel_id = state.get("novel_id", 0)
    chapter_no = state.get("chapter_no", 1)
    prose_fb = (state.get("prose_feedback") or "").strip()
    prev = (state.get("draft") or "").strip()
    force = state.get("force_write", False)
    user_fb = (state.get("user_feedback") or "").strip()
    # 上一章正文结尾（用于章节衔接）
    prev_chapter_draft = (state.get("prev_chapter_draft") or "").strip()

    # 查数据库：获取世界规则约束
    db_context = _load_context_for_writer(novel_id, chapter_no)

    user_parts = []

    if user_fb:
        user_parts.append(
            f"【用户修改意见】（请优先处理以下所有意见，完成后再写正文）\n{user_fb}\n"
        )

    # 续写衔接：必须包含上一章结尾作为续写起点
    if prev_chapter_draft:
        user_parts.append(
            f"【续写起点 - 上一章结尾】（新章节必须从这里继续，承接情节与语气，不得偏离）\n"
            f"{prev_chapter_draft}\n\n"
        )

    user_parts.extend([
        f"【本章写作指引】\n{state.get('chapter_guide') or '（暂无指引）'}\n\n",
        f"【本章写作约束】\n{db_context}\n\n",
        f"【文字层审阅意见】（仅据此改文笔与表达；禁止改设定）\n"
        f"{prose_fb or '（首稿：无文字层反馈）'}\n\n",
        f"【上一版正文】\n{prev or '（无，请新写）'}\n\n",
        f"【本章任务】\n{state.get('chapter_task', '')}",
    ])

    if force:
        user_parts.append(
            "\n\n【强制重写指令】"
            "上一轮审阅意见为 keep（无修改要求）但评分未达标，系统检测到你可能在微改文字而非实质性改进。"
            "**必须**做出以下改变之一：（1）重构叙事结构/视角 （2）加强核心冲突与张力 "
            "（3）增加新的戏剧性细节 （4）改变节奏（加快或放缓）。"
            "不能只是换同义词或调语序，必须让本章有明显的提升。"
        )

    user = "".join(user_parts)

    return _invoke(
        [SystemMessage(content=WRITER_SYSTEM), HumanMessage(content=user)],
        0.85,
        llm,
    )


# =============================================
# Critic Agent
# =============================================

def critic_agent(state: "WritingState", llm: BaseChatModel) -> CriticResponse:
    """
    审阅节点实现。

    优先使用 JSON 格式解析，Markdown fallback 兼容旧格式。
    """
    novel_id = state.get("novel_id", 0)
    chapter_no = state.get("chapter_no", 1)
    chapter_guide = state.get("chapter_guide") or state.get("plan") or ""
    draft = state.get("draft") or ""

    # 使用精简上下文（critic）
    context_extra = _load_context_for_critic(novel_id, chapter_no)

    user = (
        f"【当前审阅章节】\n第{chapter_no}章\n\n"
        f"【本章写作指引】\n{chapter_guide}\n\n"
        f"【本章草稿】\n{draft}\n\n"
        f"{context_extra}"
        f"{CRITIC_SYSTEM}"
    )

    fb = _invoke([HumanMessage(content=user)], 0.35, llm)

    # DEBUG: 打印 Critic 原始输出
    import logging
    logging.warning(f"[critic_agent] chapter={chapter_no}, iteration={state.get('iteration')}")
    logging.warning(f"[critic_agent] raw_response({len(fb)}字)={fb[:800] if len(fb) > 800 else fb}")

    # 结构化解析
    response = CriticResponse.from_json(fb)

    # 评分兜底：JSON 解析失败且 score=0 时，用 markdown fallback 再试
    if response.parse_error and response.score == 0.0:
        fallback = CriticResponse._from_markdown_fallback(fb)
        if fallback.score > 0:
            response = fallback
            logging.warning(f"[critic_agent] markdown fallback有效: score={response.score}")
        else:
            logging.warning(f"[critic_agent] markdown fallback也无效（score=0）")

    # 最终兜底：仍然得不出有效评分
    if response.score <= 0:
        response.score = 5.0  # 默认5分，让流程继续
        logging.warning(f"[critic_agent] 兜底评分 5.0（parse_error={response.parse_error}）")

    logging.warning(f"[critic_agent] 最终结果: score={response.score}, "
                    f"arch_action={response.arch_action}, prose_action={response.prose_action}")

    return response
