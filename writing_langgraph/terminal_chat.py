"""终端对话式写作 Agent - 自然语言交流"""

import os
import sys

# 配置日志
import logging
logging.basicConfig(
    level=logging.WARNING,
    format="%(levelname)s | %(message)s",
)
logging.getLogger("langchain").setLevel(logging.ERROR)

API_KEY = os.environ.get("OPENAI_API_KEY", "")
BASE_URL = os.environ.get("OPENAI_BASE_URL", "https://api.minimaxi.com/v1")
MODEL = os.environ.get("OPENAI_MODEL", "minimax-m2.7")

# ========== 自然语言理解 ==========

INTENT_KEYWORDS = {
    "写": ["写", "开始写", "创作", "写一个", "写第", "写第一章", "写第二章"],
    "继续": ["继续", "续写", "下一章", "接着写", "后面的内容"],
    "修改": ["修改", "调整", "修订", "改一下", "改动", "改动一下"],
    "查看": ["查看", "看看", "看一下", "读一下", "查一下", "第几章", "状态", "进度"],
    "插入": ["插入", "加一段", "加一个情节", "加个情节"],
}

def understand_intent(text: str) -> str:
    """从自然语言推断用户意图"""
    text = text.strip()

    # 查看状态类
    for kw in INTENT_KEYWORDS["查看"]:
        if kw in text:
            return "query"
    if any(x in text for x in ["什么", "多少", "怎么"]):
        if "写" not in text and "继续" not in text:
            return "chat"

    # 继续写类
    for kw in INTENT_KEYWORDS["继续"]:
        if kw in text:
            return "continue"
    if text in ["继续", "续", "下一", "接着"]:
        return "continue"

    # 插入情节类
    for kw in INTENT_KEYWORDS["插入"]:
        if kw in text:
            return "plot_insert"

    # 修改类
    for kw in INTENT_KEYWORDS["修改"]:
        if kw in text:
            return "revise"

    # 写新章节类
    for kw in INTENT_KEYWORDS["写"]:
        if kw in text:
            return "new_chapter"

    # 默认：当作聊天或新章节
    return "chat"


# ========== 核心写作逻辑 ==========

def write_chapter(novel_id: int, chapter_no: int, brief: str, llm, max_iter: int = 4, score_pass: float = 8.0, plan_macro: str = "", plan_phase: str = "", phase_start: int = 0, phase_end: int = 0, small_story_index: int = 0, prev_chapter_draft: str = ""):
    """执行单章节写作流程（使用 LangGraph 工作流）"""
    from writing_langgraph.state import initial_state
    from writing_langgraph.graph import build_writing_graph

    print(f"\n{'='*50}")
    print(f" 开始写第 {chapter_no} 章")
    print(f"{'='*50}\n")

    state = initial_state(
        story_idea=brief,
        chapter_task=brief,
        max_iterations=max_iter,
        score_pass=score_pass,
        chapter_no=chapter_no,
        novel_id=novel_id,
        output_dir=f"novel_output/{novel_id}",
        plan_macro=plan_macro,
        plan_phase=plan_phase,
        current_phase_start_ch=phase_start,
        current_phase_end_ch=phase_end,
        current_small_story_index=small_story_index,
        prev_chapter_draft=prev_chapter_draft,
    )

    # 使用 LangGraph 工作流：Critic 会根据 arch_action/prose_action 自动路由
    # 到 planner（修订策划）或 writer（修订正文），无需手动循环
    print("[Planner → Writer → Critic → 自动路由] 迭代中...")
    graph = build_writing_graph(llm)
    final_state = graph.invoke(state)

    iteration = int(final_state.get("iteration", 0))
    score = float(final_state.get("score", 0))
    draft = final_state.get("draft", "")
    plan = final_state.get("plan", "")
    saved_path = final_state.get("saved_chapter_path", "")

    # 提取新的规划追踪字段
    new_phase_start = int(final_state.get("current_phase_start_ch", 0))
    new_phase_end = int(final_state.get("current_phase_end_ch", 0))
    new_small_story_index = int(final_state.get("current_small_story_index", 0))
    new_plan_macro = final_state.get("plan_macro", "")
    new_plan_phase = final_state.get("plan_phase", "")

    print(f"    完成（{iteration} 轮，评分 {score:.1f}/10，{len(draft)} 字）")
    if new_small_story_index > 0:
        print(f"    当前小故事：#{new_small_story_index}（第{new_phase_start}-{new_phase_end}章）")
    print()

    return {
        "iteration": iteration,
        "saved_path": saved_path,
        "plan_macro": new_plan_macro,
        "plan_phase": new_plan_phase,
        "phase_start": new_phase_start,
        "phase_end": new_phase_end,
        "small_story_index": new_small_story_index,
    }


# ========== 终端对话 ==========

def chat():
    from langchain_openai import ChatOpenAI

    print("\n" + "=" * 50)
    print(" 写作助手 - 自然语言对话版")
    print("=" * 50)
    print("直接说话就可以，比如:")
    print('  "写第一章，主角是个修仙少年"')
    print('  "继续写第二章"')
    print('  "修改第一章"')
    print('  "现在写到第几章了"')
    print('  "继续"')
    print('  "查看第三章"')
    print('  "直接问我问题也可以"')
    print('  "/quit" 退出')
    print("-" * 50 + "\n")

    # 获取 API Key（优先使用环境变量，否则让用户输入）
    global API_KEY, BASE_URL, MODEL
    if not API_KEY:
        print("\n请输入 API Key:", end=" ")
        API_KEY = input().strip()
        if not API_KEY:
            print("没有 API Key 无法运行")
            return
        print(f"\n[已设置 API Key: {API_KEY[:8]}...]")

    llm = ChatOpenAI(
        api_key=API_KEY,
        base_url=BASE_URL.strip().rstrip("/") if BASE_URL else None,
        model=MODEL,
    )

    print(f"\n[配置] API Key: {API_KEY[:8]}...")
    print(f"[配置] Base URL: {BASE_URL}")
    print(f"[配置] Model: {MODEL}")
    print("[提示] API 已配置，直接开始对话吧！\n")

    novel_id = 1
    chapter_states = {}  # chapter_no -> {iteration, path, plan_phase, phase_start, phase_end, small_story_index}

    # 全局规划状态（跨章节共享）
    global_plan_macro = ""
    global_plan_phase = ""

    # 启动时尝试从数据库恢复状态
    try:
        from writing_langgraph.memory.tools import load_small_story_tracking
        saved = load_small_story_tracking(novel_id)
        if saved and saved.get("plan_macro"):
            global_plan_macro = saved["plan_macro"]
            global_plan_phase = saved["plan_phase"]
            chapter_counter = saved["next_chapter"]
            print(f"[恢复] 当前在小故事#{saved['small_story_index']}，从第{chapter_counter}章继续")
            print(f"[恢复] 宏观规划 {len(global_plan_macro)} 字，小故事规划 {len(global_plan_phase)} 字")
        else:
            chapter_counter = 1
            print("[新项目] 从第一章开始")
    except Exception as e:
        chapter_counter = 1
        print(f"[新项目] 从第一章开始（加载失败: {e}）")

    while True:
        try:
            user = input("\n你: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\n再见!")
            break

        if not user:
            continue

        if user.lower() in ["/quit", "/exit", "quit", "exit", "退出", "再见"]:
            print("再见!")
            break

        intent = understand_intent(user)
        print(f"\n[理解意图: {intent}]\n")

        # -------- 写新章节 --------
        if intent == "new_chapter":
            # 提取章节号
            import re
            ch_match = re.search(r"第\s*(\d+)\s*章", user)
            if ch_match:
                chapter_no = int(ch_match.group(1))
            else:
                chapter_no = chapter_counter

            # 从已有状态获取最新的规划追踪信息
            latest_state = chapter_states[max(chapter_states.keys())] if chapter_states else {}
            phase_start = latest_state.get("phase_start", 0)
            phase_end = latest_state.get("phase_end", 0)
            small_story_index = latest_state.get("small_story_index", 0)

            # 加载上一章正文结尾（用于章节衔接）
            prev_chapter_draft = ""
            if chapter_no > 1:
                try:
                    from writing_langgraph.memory.chapter_memory import get_chapter_by_order
                    prev_ch = get_chapter_by_order(novel_id, chapter_no - 1)
                    if prev_ch and prev_ch.draft:
                        prev_chapter_draft = prev_ch.draft[-2000:]
                except Exception:
                    pass

            result = write_chapter(
                novel_id=novel_id,
                chapter_no=chapter_no,
                brief=user,
                llm=llm,
                plan_macro=global_plan_macro,
                plan_phase=global_plan_phase,
                phase_start=phase_start,
                phase_end=phase_end,
                small_story_index=small_story_index,
                prev_chapter_draft=prev_chapter_draft,
            )

            # 更新全局规划状态
            if result["plan_macro"]:
                global_plan_macro = result["plan_macro"]
            if result["plan_phase"]:
                global_plan_phase = result["plan_phase"]

            chapter_states[chapter_no] = result
            chapter_counter = max(chapter_counter, chapter_no + 1)
            continue

        # -------- 继续写 --------
        if intent == "continue":
            # chapter_states 仅存于进程内存，重启后为空
            # 从数据库加载最后一章的信息来续写
            if not chapter_states:
                # 从 small_story_tracking 恢复 chapter_counter
                try:
                    from writing_langgraph.memory.tools import load_small_story_tracking
                    saved = load_small_story_tracking(novel_id)
                    if saved:
                        chapter_counter = saved["phase_end_ch"] + 1
                        # global_plan_macro / global_plan_phase 已在启动时加载
                except Exception:
                    pass

            if not chapter_states and chapter_counter <= 1:
                print("还没有写任何章节，请先说 '写第一章' 开始")
                continue

            chapter_no = chapter_counter

            # 从最新章节获取规划追踪状态（若有）
            if chapter_states:
                latest_state = chapter_states[max(chapter_states.keys())]
                phase_start = latest_state.get("phase_start", 0)
                phase_end = latest_state.get("phase_end", 0)
                small_story_index = latest_state.get("small_story_index", 0)
            else:
                phase_start = phase_end = small_story_index = 0

            print(f"[继续写第 {chapter_no} 章]")
            brief = f"继续上一章的故事，写第{chapter_no}章"

            # 加载上一章正文结尾（用于章节衔接）
            prev_chapter_draft = ""
            try:
                from writing_langgraph.memory.chapter_memory import get_chapter_by_order
                prev_ch = get_chapter_by_order(novel_id, chapter_no - 1)
                if prev_ch and prev_ch.draft:
                    prev_chapter_draft = prev_ch.draft[-2000:]
            except Exception:
                pass

            result = write_chapter(
                novel_id=novel_id,
                chapter_no=chapter_no,
                brief=brief,
                llm=llm,
                plan_macro=global_plan_macro,
                plan_phase=global_plan_phase,
                phase_start=phase_start,
                phase_end=phase_end,
                small_story_index=small_story_index,
                prev_chapter_draft=prev_chapter_draft,
            )

            if result["plan_macro"]:
                global_plan_macro = result["plan_macro"]
            if result["plan_phase"]:
                global_plan_phase = result["plan_phase"]

            chapter_states[chapter_no] = result
            chapter_counter += 1
            continue

        # -------- 修改章节 --------
        if intent == "revise":
            import re
            ch_match = re.search(r"第\s*(\d+)\s*章", user)
            if ch_match:
                chapter_no = int(ch_match.group(1))
            else:
                chapter_no = max(chapter_states.keys()) if chapter_states else 1
            print(f"[修改第 {chapter_no} 章]")

            # 修改时需要从 DB 加载完整的规划状态
            from writing_langgraph.memory.chapter_memory import get_chapter_by_order
            try:
                ch = get_chapter_by_order(novel_id, chapter_no)
                if ch:
                    brief = f"修改第{chapter_no}章\n原策划:\n{ch.plan}\n\n原正文:\n{ch.draft}\n\n修改意见: {user}"
                    # 从 DB 加载的章节没有追踪字段，用当前全局状态
                    latest_state = chapter_states[max(chapter_states.keys())] if chapter_states else {}
                    phase_start = latest_state.get("phase_start", 0)
                    phase_end = latest_state.get("phase_end", 0)
                    small_story_index = latest_state.get("small_story_index", 0)
                else:
                    brief = user
                    phase_start = phase_end = small_story_index = 0
            except:
                brief = user
                phase_start = phase_end = small_story_index = 0

            result = write_chapter(
                novel_id=novel_id,
                chapter_no=chapter_no,
                brief=brief,
                llm=llm,
                plan_macro=global_plan_macro,
                plan_phase=global_plan_phase,
                phase_start=phase_start,
                phase_end=phase_end,
                small_story_index=small_story_index,
            )

            if result["plan_macro"]:
                global_plan_macro = result["plan_macro"]
            if result["plan_phase"]:
                global_plan_phase = result["plan_phase"]

            chapter_states[chapter_no] = result
            continue

        # -------- 查看状态 --------
        if intent == "query":
            if not chapter_states:
                print("还没有写任何章节")
                continue
            print(f"已写章节 (共 {len(chapter_states)} 章):")
            for ch, info in sorted(chapter_states.items()):
                ss_idx = info.get("small_story_index", 0)
                phase_info = f"，小故事#{ss_idx}" if ss_idx > 0 else ""
                print(f"  第 {ch} 章: {info.get('iteration', '?')} 轮{phase_info}，{info.get('saved_path', '未保存')}")
            if global_plan_macro:
                print(f"\n当前大故事规划: {len(global_plan_macro)} 字")
            continue

        # -------- 插入情节 --------
        if intent == "plot_insert":
            print("情节插入功能: 抱歉，这个功能我还没来得及实现，你可以先告诉我你要写什么内容")
            continue

        # -------- 聊天 --------
        from langchain_core.messages import HumanMessage, SystemMessage
        response = llm.invoke([
            SystemMessage(content="你是写作助手的对话伙伴。用户想和你聊写作相关的事情，或者问问题。请简洁友好地回答。"),
            HumanMessage(content=user)
        ])
        content = response.content if hasattr(response, "content") else str(response)
        print(f"\n助手: {content}")


if __name__ == "__main__":
    chat()
