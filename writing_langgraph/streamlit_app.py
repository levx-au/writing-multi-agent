"""写作助手 - 按钮式界面，实时显示工作流程"""

from __future__ import annotations

import os
import logging

# 配置日志：显示所有 [xxx] 标签的 debug 信息
logging.basicConfig(
    level=logging.WARNING,
    format="%(levelname)s | %(message)s",
)
# 让 langchain 的冗长 warnings 只显示一次
logging.getLogger("langchain").setLevel(logging.ERROR)

import streamlit as st
from langchain_openai import ChatOpenAI

from writing_langgraph.state import initial_state
from writing_langgraph.graph import build_writing_graph


PAGE_TITLE = "写作助手"
STYLES = """
<style>
    .main-header {
        font-size: 2rem;
        font-weight: 700;
        margin-bottom: 1rem;
        color: #1a1a2e;
    }
    .chapter-box {
        background: #fafafa;
        border-radius: 12px;
        padding: 1.5rem;
        margin: 1rem 0;
        border-left: 4px solid #667eea;
    }
    .chapter-box h3 {
        margin-top: 0;
        color: #667eea;
    }
    .plan-box {
        background: #f0f4ff;
        border-radius: 12px;
        padding: 1rem;
        margin: 0.5rem 0;
        border-left: 3px solid #4f86f7;
    }
    div[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #f8f9fc 0%, #f0f2f8 100%);
    }
    .stButton>button {
        width: 100%;
    }
    div[data-testid="stStatusWidget"] {
        max-width: 100%;
    }
</style>
"""


def _make_llm(api_key: str, base_url: str | None, model: str) -> ChatOpenAI:
    kw = {"api_key": api_key, "model": model}
    if base_url and base_url.strip():
        kw["base_url"] = base_url.strip().rstrip("/")
    return ChatOpenAI(**kw)


def write_one_chapter(
    llm: ChatOpenAI,
    novel_id: int,
    chapter_no: int,
    story_idea: str,
    chapter_task: str,
    output_dir: str,
    max_iterations: int,
    score_pass: float,
    status_placeholder=None,
    error_placeholder=None,
    prev_draft: str = "",
    user_feedback: str = "",
    plan_macro: str = "",
    plan_phase: str = "",
) -> dict:
    """
    写一个章节的完整流程（通过 LangGraph 工作流）。

    Args:
        plan_macro: 宏观规划（从数据库加载，用于续写）
        plan_phase: 阶段性规划（从数据库加载，用于续写）
        prev_draft: 上一章的正文（用于保持连贯性）
        user_feedback: 用户对本章的修改意见/指令（会注入到 Writer prompt 最前面）
    """
    try:
        # 确保 chapter_no 有效
        assert isinstance(chapter_no, int) and chapter_no >= 1, f"chapter_no 无效: {chapter_no}"
        assert isinstance(novel_id, int) and novel_id >= 1, f"novel_id 无效: {novel_id}"

        state = initial_state(
            story_idea=story_idea,
            chapter_task=chapter_task,
            max_iterations=max_iterations,
            score_pass=score_pass,
            chapter_no=chapter_no,
            output_dir=output_dir,
            novel_id=novel_id,
            plan_macro=plan_macro,
            plan_phase=plan_phase,
            # 传入上一章正文结尾，用于章节衔接
            prev_chapter_draft=prev_draft,
        )

        # 用户意见/续写指令（注入 Writer prompt 最前面，优先级最高）
        if user_feedback:
            state["user_feedback"] = user_feedback

        # 确认 state 中的 chapter_no 正确（用于 debug）
        assert state["chapter_no"] == chapter_no, f"state chapter_no {state['chapter_no']} != 传入的 {chapter_no}"

        # 走 LangGraph 工作流：Critic 会根据 arch_action/prose_action 自动路由
        # 到 planner（修订策划）或 writer（修订正文），无需手动循环
        if status_placeholder:
            status_placeholder.info(f"🤖 写作中（章节 {chapter_no}，Critic 会自动反馈给 Planner/Writer）...")
        graph = build_writing_graph(llm)
        final_state = graph.invoke(state)

        # 确认 graph 返回的 state 中 chapter_no 正确
        final_chapter_no = final_state.get("chapter_no")
        assert final_chapter_no == chapter_no, f"graph 返回的 chapter_no {final_chapter_no} != 传入的 {chapter_no}"

        # graph.invoke 结束后 state 中已包含最终结果，直接取用
        score = float(final_state.get("score", 0))
        saved_path = final_state.get("saved_chapter_path", "")

        if status_placeholder:
            status_placeholder.success(
                f"✅ 完成（评分 {score:.1f}/10，迭代 {final_state.get('iteration', 0)} 轮）"
            )

        return {
            "plan": final_state.get("plan", ""),
            "plan_macro": final_state.get("plan_macro", ""),
            "plan_phase": final_state.get("plan_phase", ""),
            "draft": final_state.get("draft", ""),
            "score": score,
            "iterations": int(final_state.get("iteration", 0)),
            "saved_path": saved_path or "",
        }

    except Exception as e:
        if error_placeholder:
            error_placeholder.error(f"发生错误: {e}")
            import traceback
            error_placeholder.code(traceback.format_exc())
        raise


# =============================================
# 侧边栏
# =============================================

def _render_sidebar() -> dict:
    with st.sidebar:
        st.markdown("### 🔑 API 配置")
        api_key = st.text_input(
            "API Key",
            value=os.environ.get("OPENAI_API_KEY", ""),
            type="password",
        )
        base_url = st.text_input(
            "Base URL（可选）",
            value=os.environ.get("OPENAI_BASE_URL", ""),
            placeholder="https://api.minimaxi.com/v1",
        )
        model = st.text_input(
            "模型名",
            value=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
        )

        st.markdown("---")
        st.markdown("### 📚 小说配置")

        # 首次设置时记录 output_dir，之后保持不变
        if "output_dir" not in st.session_state:
            st.session_state["output_dir"] = f"novel_output/{st.session_state.get('initial_novel_id', 1)}"

        # 只在首次设置 initial_novel_id
        if "initial_novel_id" not in st.session_state:
            st.session_state["initial_novel_id"] = 1

        novel_id = st.number_input(
            "小说 ID",
            min_value=1,
            max_value=9999,
            value=st.session_state["initial_novel_id"],
            help="同一 ID 共享记忆",
        )

        output_dir = st.session_state["output_dir"]
        st.text_input("输出目录", value=output_dir, disabled=True)

        st.markdown("---")
        st.markdown("### ⚙️ 写作参数")
        max_iter = st.number_input("最大迭代轮数", min_value=1, max_value=12, value=4)
        score_pass = st.slider("定稿分数线", 0.0, 10.0, 8.0, 0.5)

        st.markdown("---")
        if st.button("🗑️ 重置项目", use_container_width=True):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()

    return {
        "api_key": api_key,
        "base_url": base_url,
        "model": model,
        "max_iter": max_iter,
        "score_pass": score_pass,
        "novel_id": novel_id,
        "output_dir": output_dir,
    }


# =============================================
# 主界面
# =============================================

def main() -> None:
    st.set_page_config(
        page_title=PAGE_TITLE,
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.markdown(STYLES, unsafe_allow_html=True)

    cfg = _render_sidebar()

    # 初始化 session state
    if "chapter_history" not in st.session_state:
        st.session_state["chapter_history"] = {}

    st.markdown('<p class="main-header">📝 写作助手</p>', unsafe_allow_html=True)

    # ---- 写作/阅读 Tab ----
    tab1, tab2 = st.tabs(["✍️ 写作", "📖 阅读"])

    with tab1:
        # ---- 章节输入 ----
        col1, col2 = st.columns([3, 1])
        with col1:
            brief = st.text_area(
                "本章任务描述",
                value="",
                height=80,
                placeholder="描述本章要写什么...（例如：主角林寒参加宗门大比初赛）",
                key="brief_input",
            )
        with col2:
            # 启动时从数据库查询已写章节数，恢复到最后一章的下一页
            def _get_next_chapter(novel_id: int) -> int:
                try:
                    from writing_langgraph.db import get_db
                    with get_db(novel_id) as conn:
                        row = conn.execute(
                            "SELECT MAX(chapter_order) as max_ch FROM chapter WHERE novel_id = ?",
                            (novel_id,),
                        ).fetchone()
                        return (row["max_ch"] or 0) + 1
                except Exception:
                    return 1

            next_ch = _get_next_chapter(cfg["novel_id"])
            chapter_options = list(range(1, 100))
            default_idx = min(next_ch - 1, len(chapter_options) - 1)
            chapter_no = st.selectbox(
                "章节号",
                options=chapter_options,
                index=default_idx,
                key="chapter_select",
            )

        # ---- 写作按钮 ----
        write_clicked = st.button(
            "✍️ 写第X章",
            type="primary",
            use_container_width=True,
            disabled=not bool(brief.strip()),
        )

        # ---- 写作状态 / 错误显示 ----
        status_box = st.container()
        error_box = st.container()

        # ---- 写作执行 ----
        if write_clicked and brief.strip():
            if not cfg["api_key"]:
                error_box.error("请先填写 API Key")
            else:
                llm = _make_llm(cfg["api_key"], cfg["base_url"], cfg["model"])

                # 从数据库加载追踪状态（宏观规划、小故事规划）
                pm_macro, pm_phase = "", ""
                try:
                    from writing_langgraph.memory.tools import load_small_story_tracking
                    saved = load_small_story_tracking(cfg["novel_id"])
                    if saved and saved.get("plan_macro"):
                        pm_macro = saved["plan_macro"]
                        pm_phase = saved["plan_phase"]
                except Exception:
                    pass

                try:
                    result = write_one_chapter(
                        llm=llm,
                        novel_id=cfg["novel_id"],
                        chapter_no=chapter_no,
                        story_idea=brief.strip(),
                        chapter_task=brief.strip(),
                        output_dir=cfg["output_dir"],
                        max_iterations=cfg["max_iter"],
                        score_pass=cfg["score_pass"],
                        status_placeholder=status_box,
                        error_placeholder=error_box,
                        plan_macro=pm_macro,
                        plan_phase=pm_phase,
                    )
                    st.session_state["chapter_history"][chapter_no] = result

                    st.markdown("---")
                    st.markdown(f"### ✅ 第{chapter_no}章 完成")

                    m1, m2, m3, m4 = st.columns(4)
                    m1.metric("评分", f"{result['score']:.1f}/10")
                    m2.metric("迭代", f"{result['iterations']}轮")
                    m3.metric("保存", "✅" if result["saved_path"] else "❌")
                    m4.metric("字数", f"{len(result.get('draft', ''))}字")

                    with st.expander("📋 策划方案", expanded=False):
                        st.markdown(result.get("plan", "（无）"))

                    st.markdown("### ✍️ 正文")
                    st.markdown(result.get("draft", "（无）"))

                    # ---- 写下一章 ----
                    st.markdown("---")
                    next_ch = chapter_no + 1
                    if st.button(f"📖 继续写第{next_ch}章 →", type="primary", use_container_width=True):
                        # 传递更多策划上下文（增加到1500字），让 Planner 理解完整方向
                        prev_plan = (result.get("plan") or "")[:1500]
                        # 传递上一章最后2000字作为衔接上下文
                        prev_draft = (result.get("draft") or "")[-2000:]

                        # user_feedback：最高优先级指令，直接注入 Writer prompt 最前面
                        # 明确告诉 Writer 上一章结尾是什么、故事要往哪走
                        user_feedback = (
                            f"【续写任务：承接上一章结尾】\n"
                            f"上一章（第{chapter_no}章）结尾如下，续写必须从这里继续：\n"
                            f"{prev_draft}\n\n"
                            f"【上文策划方向参考】：\n{prev_plan}\n\n"
                            f"请在此基础上继续推进故事，不要重复已写内容，不要改变既定的情节走向。"
                        )

                        # auto_brief 给 Planner：用更具体的描述引导生成新章节的策划
                        auto_brief = (
                            f"衔接第{chapter_no}章，继续推进故事发展。\n"
                            f"【上文策划方向】（参考）：\n{prev_plan[:800]}\n\n"
                            f"【上文结尾摘要】：\n{prev_draft[-500:]}"
                        )
                        try:
                            cont_result = write_one_chapter(
                                llm=llm,
                                novel_id=cfg["novel_id"],
                                chapter_no=next_ch,
                                story_idea=auto_brief,
                                chapter_task=auto_brief,
                                output_dir=st.session_state["output_dir"],
                                max_iterations=cfg["max_iter"],
                                score_pass=cfg["score_pass"],
                                status_placeholder=status_box,
                                error_placeholder=error_box,
                                prev_draft=prev_draft,
                                user_feedback=user_feedback,
                                plan_macro=result.get("plan_macro", ""),
                                plan_phase=result.get("plan_phase", ""),
                            )
                            st.session_state["chapter_history"][next_ch] = cont_result
                            st.session_state["chapter_select"] = next_ch
                            st.rerun()
                        except Exception as e:
                            import traceback
                            st.error(f"续写失败: {e}")
                            st.code(traceback.format_exc())

                except Exception as e:
                    error_box.error(f"写作失败: {e}")
                    import traceback
                    error_box.code(traceback.format_exc())

        # ---- 历史章节 ----
        if st.session_state.get("chapter_history"):
            st.markdown("---")
            with st.expander(f"📚 已完成章节（共{len(st.session_state['chapter_history'])}章）", expanded=False):
                for ch, r in sorted(st.session_state["chapter_history"].items()):
                    st.markdown(
                        f"**第{ch}章** — 评分 {r['score']:.1f} — "
                        f"字数 {len(r.get('draft', ''))}字 — "
                        f"{r['saved_path'] or '未保存'}"
                    )

    # =============================================
    # 阅读 Tab
    # =============================================
    with tab2:
        st.markdown("### 📖 章节阅读")

        def load_chapters_from_db(novel_id: int):
            """从数据库加载章节列表"""
            try:
                from writing_langgraph.memory.chapter_memory import get_recent_chapters
                return get_recent_chapters(novel_id, limit=999)
            except Exception:
                return []

        chapters = load_chapters_from_db(cfg["novel_id"])

        if not chapters:
            st.info("暂无已保存的章节，请先在写作界面生成章节")
        else:
            # 章节选择器
            chapter_dict = {ch.chapter_order: ch for ch in chapters}
            sorted_orders = sorted(chapter_dict.keys())

            col_sel1, col_sel2 = st.columns([1, 3])
            with col_sel1:
                read_chapter_no = st.selectbox(
                    "选择章节",
                    options=sorted_orders,
                    index=len(sorted_orders) - 1,
                    format_func=lambda x: f"第{x}章",
                    key="read_chapter_select",
                )

            # 显示章节信息
            chapter = chapter_dict.get(read_chapter_no)
            if chapter:
                with col_sel2:
                    word_count = chapter.word_count or len(chapter.draft or '')
                    st.markdown(
                        f"**字数**：{word_count} | "
                        f"**评分**：{chapter.score or 'N/A'} | "
                        f"**状态**：{chapter.status or 'unknown'} | "
                        f"**迭代**：{chapter.iteration if hasattr(chapter, 'iteration') else 'N/A'}轮"
                    )

                # 章节任务
                if chapter.brief:
                    st.markdown("#### 本章任务")
                    st.markdown(chapter.brief)

                # 策划方案
                if chapter.plan:
                    with st.expander("📋 策划方案", expanded=False):
                        st.markdown(chapter.plan)

                # 正文
                if chapter.draft:
                    st.markdown("#### 正文")
                    st.markdown(chapter.draft)
                else:
                    st.info("本章暂无正文内容")

                # 章节导航
                st.markdown("---")
                nav_col1, nav_col2, nav_col3 = st.columns([1, 1, 1])
                current_idx = sorted_orders.index(read_chapter_no)
                with nav_col1:
                    if current_idx > 0:
                        prev_ch = sorted_orders[current_idx - 1]
                        if st.button(f"◀ 第{prev_ch}章", use_container_width=True):
                            st.session_state["read_chapter_select"] = prev_ch - 1
                            st.rerun()
                with nav_col2:
                    st.markdown(f"**第{read_chapter_no}章 / 共{len(sorted_orders)}章**")
                with nav_col3:
                    if current_idx < len(sorted_orders) - 1:
                        next_ch = sorted_orders[current_idx + 1]
                        if st.button(f"第{next_ch}章 ▶", use_container_width=True):
                            st.session_state["read_chapter_select"] = next_ch - 1
                            st.rerun()
            else:
                st.error(f"未找到第{read_chapter_no}章")


if __name__ == "__main__":
    main()
