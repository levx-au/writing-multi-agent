"""LangGraph 共享状态定义 - 支持百万字长文的分层记忆"""

from __future__ import annotations

from typing import Optional, TypedDict
from typing_extensions import Literal


# =============================================
# 分层记忆子状态
# =============================================

class GlobalMemory(TypedDict, total=False):
    """全局记忆：跨所有卷的核心信息"""
    world_rules: str
    power_system: dict
    character_templates: list[dict]
    main_plot_threads: list[str]
    core_constraints: list[str]
    world_state_snapshot: str


class VolumeMemory(TypedDict, total=False):
    """卷记忆：当前卷的人物状态、伏笔进展"""
    volume_id: int
    volume_title: str
    character_states: list[dict]
    active_plot_threads: list[dict]
    volume_arc_progress: str
    pending_foreshadowing: list[str]


class ChapterMemory(TypedDict, total=False):
    """章节记忆：当前章节草稿、场景细节"""
    chapter_id: int
    scene_details: list[dict]
    local_plot_progress: str
    connection_points: list[str]


class ParallelContext(TypedDict, total=False):
    """并行写作上下文"""
    is_parallel_task: bool
    parent_chapter_id: Optional[int]
    sibling_chapter_ids: list[int]
    merged_content: str


class WritingConfig(TypedDict, total=False):
    """写作配置"""
    max_iterations: int
    score_pass: float
    temperature_plan: float
    temperature_write: float
    temperature_critic: float


class MemoryDelta(TypedDict, total=False):
    """记忆增量（章节写作后产生）"""
    character_updates: list[dict]
    new_characters: list[dict]
    power_breakthroughs: list[dict]
    item_changes: list[dict]
    plot_threads_updated: list[dict]
    new_constraints: list[str]
    location_changes: list[dict]
    new_character_appearance: bool
    major_realm_breakthrough: bool
    main_thread_resolution: bool


# =============================================
# 主状态
# =============================================

class WritingState(TypedDict, total=False):
    """LangGraph 共享状态。"""

    # ========== 身份与元数据 ==========
    novel_id: int
    novel_title: str
    genre: str
    current_volume_id: Optional[int]
    current_chapter_id: Optional[int]
    output_dir: str

    # ========== 分层记忆 ==========
    global_memory: GlobalMemory
    volume_memory: Optional[VolumeMemory]
    chapter_memory: Optional[ChapterMemory]

    # ========== 创作输入 ==========
    story_idea: str       # 创作意图：世界观/类型/核心角色/主线方向（项目开始时一次性输入）
    chapter_task: str     # 本章指令：用户给的本章具体写作任务（每章输入）
    chapter_no: int

    # 三层架构
    plan_macro: str    # 宏观规划：类型/主题/核心冲突/大致走向（3-5段，极虚）
    plan_phase: str    # 阶段性规划：10-20章为单位，具体事件大纲（详实）
    plan: str          # 兼容字段：plan_macro + plan_phase 合并文本
    chapter_guide: str  # 本章写作指引（从 plan_phase 提取，精简）
    draft: str

    # Critic 反馈
    feedback: str
    arch_feedback: str
    prose_feedback: str
    arch_action: Literal["revise", "keep"]
    prose_action: Literal["rewrite", "keep"]

    # 增量生成小故事追踪
    current_phase_start_ch: int   # 当前小故事起始章节
    current_phase_end_ch: int     # 当前小故事结束章节
    current_small_story_index: int  # 当前小故事序号（从1开始）
    prev_chapter_draft: str       # 上一章正文结尾（用于衔接）

    # 评分与迭代
    score: float
    iteration: int
    max_iterations: int
    score_pass: float

    # ========== 并行化支持 ==========
    parallel_context: Optional[ParallelContext]
    pending_updates: list[dict]
    lock_acquired: list[str]

    # ========== 执行结果 ==========
    stopped_reason: str
    saved_chapter_path: str
    db_synced: bool
    plot_extracted: bool  # 伏笔是否已提取并保存
    consecutive_keep_count: int  # 连续 keep 的次数（用于打破死循环）
    force_write: bool  # 强制大幅重写（打破死循环用）
    user_feedback: str  # 用户对本章的修改意见
    _route: str  # 内部路由决策（供条件边 mapper 读取，不应手动设置）


class ChapterGenerationState(TypedDict, total=False):
    """
    章节生成的子图状态。
    用于 chapter_subgraph 中。
    """

    # ========== 输入 ==========
    chapter_id: int
    chapter_no: int
    chapter_task: str
    parent_context: Optional[ParallelContext]

    # ========== 上下文（从全局/卷记忆加载） ==========
    global_memory: GlobalMemory
    volume_memory: VolumeMemory
    chapter_memory: ChapterMemory

    # ========== 写作流程 ==========
    plan_macro: str
    plan_phase: str
    plan: str  # 兼容字段
    draft: str
    feedback: str
    arch_feedback: str
    prose_feedback: str
    arch_action: str
    prose_action: str
    score: float
    iteration: int

    # ========== 输出 ==========
    final_draft: str
    memory_delta: MemoryDelta
    stopped_reason: str
    saved_chapter_path: str


class GlobalSyncState(TypedDict, total=False):
    """
    全局状态同步状态。
    用于跨章节的状态一致性管理。
    """
    novel_id: int
    pending_character_updates: list[dict]
    pending_power_updates: list[dict]
    pending_item_updates: list[dict]
    pending_plot_thread_updates: list[dict]
    sync_conflicts: list[str]
    last_sync_chapter: int


# =============================================
# 情节插入任务
# =============================================

class PlotInsertTask(TypedDict, total=False):
    """情节插入任务"""
    task_type: Literal["insert_plot"]
    user_description: str  # 用户描述的情节
    insert_after_chapter: int  # 插入点：哪一章之后
    estimated_chapters: int  # 预计跨度多少章

    # Planner 分析后的输出
    analysis_complete: bool
    insert_plan: str  # 分析后的插入计划
    strong_impact_range: str  # 强影响区（如 "31-85"）
    weak_impact_range: str  # 弱影响区（如 "86-100"）
    no_impact_range: str  # 无影响区（如 "1-30"）
    new_characters: list[dict]  # 新增角色
    plot_thread_updates: list[dict]  # 伏笔更新
    user_confirmed: bool  # 用户是否确认


class PlotInsertState(TypedDict, total=False):
    """情节插入流程状态"""
    novel_id: int
    task: PlotInsertTask
    current_phase: Literal[
        "analyzing",  # 分析中
        "awaiting_confirm",  # 等待用户确认
        "updating_memory",  # 更新记忆
        "regenerating_affected",  # 重新生成受影响章节
        "generating_new",  # 生成新情节
        "completed",
        "cancelled",
    ]
    chapters_to_regenerate: list[int]  # 需要重新生成的章节列表
    chapters_generated: list[int]  # 已生成的章节列表


# =============================================
# 便捷函数
# =============================================

def initial_state(
    story_idea: str,
    chapter_task: str,
    *,
    chapter_no: int,
    novel_id: int,
    max_iterations: int,
    score_pass: float,
    plan_macro: str = "",
    plan_phase: str = "",
    plan: str = "",
    output_dir: str = "novel_output",
    genre: str = "玄幻",
    current_phase_start_ch: int = 0,
    current_phase_end_ch: int = 0,
    current_small_story_index: int = 0,
    prev_chapter_draft: str = "",
) -> WritingState:
    """创建初始状态"""
    state: WritingState = {
        "story_idea": story_idea,
        "chapter_task": chapter_task,
        "chapter_no": chapter_no,
        "output_dir": output_dir,
        "novel_id": novel_id,
        "genre": genre,
        "plan_macro": plan_macro,
        "plan_phase": plan_phase,
        "plan": plan or plan_macro + "\n\n" + plan_phase,  # 兼容：合并文本
        "chapter_guide": "",
        "draft": "",
        "feedback": "",
        "arch_feedback": "",
        "prose_feedback": "",
        "arch_action": "keep",
        "prose_action": "keep",
        "score": 0.0,
        "iteration": 0,
        "max_iterations": max_iterations,
        "score_pass": score_pass,
        "stopped_reason": "",
        "saved_chapter_path": "",
        "db_synced": False,
        "plot_extracted": False,
        "consecutive_keep_count": 0,
        "force_write": False,
        "user_feedback": "",
        "current_phase_start_ch": current_phase_start_ch,
        "current_phase_end_ch": current_phase_end_ch,
        "current_small_story_index": current_small_story_index,
        "prev_chapter_draft": prev_chapter_draft,
        "global_memory": GlobalMemory(),
        "volume_memory": None,
        "chapter_memory": None,
        "pending_updates": [],
        "lock_acquired": [],
    }
    return state


