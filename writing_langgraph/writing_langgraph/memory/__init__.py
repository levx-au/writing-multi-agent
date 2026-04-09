"""分层记忆系统"""

from writing_langgraph.memory.chapter_memory import (
    create_chapter,
    get_chapter,
    get_chapter_by_order,
    get_chapter_history,
    get_chapter_memory_content,
    get_recent_chapters,
    load_chapter_memory_by_iteration,
    load_latest_chapter_memory,
    save_chapter_memory,
    update_chapter,
    upsert_chapter,
)
from writing_langgraph.memory.global_memory import (
    create_initial_global_memory,
    get_global_memory_content,
    get_novel_metadata,
    load_global_memory,
    save_global_memory,
    should_update_global_memory,
)
from writing_langgraph.memory.memory_parser import (
    MemoryDelta,
    extract_memory_sections,
    extract_and_save_plot_threads,
    parse_character_states,
    parse_memory_delta,
    parse_plot_threads,
    parse_power_breakthroughs,
    parse_structured_json_from_memory,
)
from writing_langgraph.memory.volume_memory import (
    finalize_volume,
    get_current_volume,
    get_or_create_volume,
    get_volume_memory_content,
    load_volume_memory,
    save_volume_memory,
)
from writing_langgraph.memory.tools import (
    get_chapters_summary,
    get_character_power_history,
    get_full_context,
    get_plot_thread_detail,
    get_pending_plot_threads,
)
from writing_langgraph.memory.plot_insert import (
    InsertPlan,
    execute_plot_insert,
    update_memory_for_insert,
    renumber_chapters,
    generate_setup_chapters,
    generate_inserted_plot,
    adjust_following_chapters,
)

__all__ = [
    # Global
    "create_initial_global_memory",
    "load_global_memory",
    "save_global_memory",
    "get_global_memory_content",
    "should_update_global_memory",
    "get_novel_metadata",
    # Volume
    "load_volume_memory",
    "save_volume_memory",
    "get_volume_memory_content",
    "get_current_volume",
    "get_or_create_volume",
    "finalize_volume",
    # Chapter
    "load_latest_chapter_memory",
    "load_chapter_memory_by_iteration",
    "save_chapter_memory",
    "get_chapter_memory_content",
    "get_chapter_history",
    "create_chapter",
    "update_chapter",
    "upsert_chapter",
    "get_chapter",
    "get_chapter_by_order",
    "get_recent_chapters",
    # Parser
    "MemoryDelta",
    "parse_memory_delta",
    "parse_structured_json_from_memory",
    "parse_character_states",
    "parse_power_breakthroughs",
    "parse_plot_threads",
    "extract_memory_sections",
    "extract_and_save_plot_threads",
    # Tools (for LLM)
    "get_full_context",
    "get_chapters_summary",
    "get_character_power_history",
    "get_plot_thread_detail",
    "get_pending_plot_threads",
    # Plot Insert
    "InsertPlan",
    "execute_plot_insert",
    "update_memory_for_insert",
    "renumber_chapters",
    "generate_setup_chapters",
    "generate_inserted_plot",
    "adjust_following_chapters",
]
