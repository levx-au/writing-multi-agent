"""完整流程测试：生成两章连贯的小说"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_two_chapters():
    from writing_langgraph.state import initial_state
    from writing_langgraph.graph import build_writing_graph
    from langchain_openai import ChatOpenAI

    # 配置 LLM
    # ==== 在这里配置你的 API ====
    API_KEY = ""  # 设置你的 MiniMax API Key
    BASE_URL = "https://api.minimaxi.com/v1"  # MiniMax API 地址
    MODEL = "minimax-m2.7"  # MiniMax 模型名
    # ==================================

    import os
    api_key = API_KEY or os.environ.get("OPENAI_API_KEY", "")
    base_url = BASE_URL or os.environ.get("OPENAI_BASE_URL", "")
    model = MODEL or os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    proxy = os.environ.get("OPENAI_PROXY", "")  # 代理地址，如 "http://127.0.0.1:7890"

    if not api_key:
        print("[ERROR] 请设置 API_KEY（环境变量或脚本顶部配置）")
        return False

    kw = {"api_key": api_key, "model": model, "timeout": 300}  # 300秒超时
    if base_url:
        kw["base_url"] = base_url.rstrip("/")

    # 设置代理（如果配置了）
    if proxy:
        import httpx
        kw["http_client"] = httpx.Client(proxy=proxy)

    llm = ChatOpenAI(**kw)
    print(f"[OK] LLM 配置完成: {model}")

    graph = build_writing_graph(llm)
    print(f"[OK] 图构建成功")

    # ========== 第一章 ==========
    print("\n" + "=" * 60)
    print("生成第一章")
    print("=" * 60)

    state1 = initial_state(
        story_idea="""写一个玄幻修仙小说：
- 主角林寒，杂灵根，被视为废物
- 背景：青云宗，世俗界的一个小门派
- 金手指：意外获得上古仙人遗留的《天元诀》，可以吸收任何灵气
- 主线：从小人物崛起，最终成为一代仙尊
- 风格：凡人流、杀伐果断、节奏快
""",
        chapter_task="""主角林寒是青云宗的外门弟子，杂灵根，被所有人看不起。
今天是他参加宗门年度考核的日子，只有通过考核才能留在宗门。
考核内容是灵力测试，只有达到炼气三层才能留下。
林寒知道自己最多只有炼气一层的水平，但他必须通过。
请写出他参加考核的经历。""",
        max_iterations=3,
        score_pass=8.0,
        chapter_no=1,
        novel_id=1,
        output_dir="test_output",
    )

    print("[INFO] 开始执行工作流...")
    final1 = graph.invoke(state1)

    print("\n" + "-" * 40)
    print("第一章结果:")
    print(f"  章节: {final1.get('chapter_no')}")
    print(f"  迭代: {final1.get('iteration')}")
    print(f"  评分: {final1.get('score')}")
    print(f"  停止原因: {final1.get('stopped_reason')}")
    print(f"  字数: {len(final1.get('draft', ''))}")

    draft1 = final1.get('draft', '')
    plan1 = final1.get('plan', '')

    if not draft1 or len(draft1) < 500:
        print("[ERROR] 第一章正文太短或为空")
        return False

    print("\n[OK] 第一章生成成功！")

    # ========== 第二章 ==========
    print("\n" + "=" * 60)
    print("生成第二章（衔接第一章）")
    print("=" * 60)

    # 提取第一章结尾用于衔接
    ending = draft1[-1500:] if len(draft1) > 1500 else draft1
    prev_plan = plan1[:1500] if len(plan1) > 1500 else plan1

    user_feedback = f"""【续写任务：承接上一章结尾】
上一章结尾如下，续写必须从这里继续：
{ending}

请在此基础上继续推进故事，不要重复已写内容。
"""

    auto_brief = f"""衔接第一章，继续推进故事发展。
上文结尾摘要：
{ending[-500:]}
"""

    state2 = initial_state(
        story_idea=state1.get('story_idea', ''),
        chapter_task=auto_brief,
        max_iterations=3,
        score_pass=8.0,
        chapter_no=2,
        novel_id=1,
        output_dir="test_output",
        plan_macro=state1.get('plan_macro', ''),
        plan_phase=state1.get('plan_phase', ''),
    )
    state2['draft'] = draft1  # 传入上一章正文作为参考
    state2['user_feedback'] = user_feedback

    print("[INFO] 开始执行工作流...")
    final2 = graph.invoke(state2)

    print("\n" + "-" * 40)
    print("第二章结果:")
    print(f"  章节: {final2.get('chapter_no')}")
    print(f"  迭代: {final2.get('iteration')}")
    print(f"  评分: {final2.get('score')}")
    print(f"  停止原因: {final2.get('stopped_reason')}")
    print(f"  字数: {len(final2.get('draft', ''))}")

    draft2 = final2.get('draft', '')

    if not draft2 or len(draft2) < 500:
        print("[ERROR] 第二章正文太短或为空")
        return False

    print("\n[OK] 第二章生成成功！")

    # ========== 保存结果 ==========
    output_dir = "test_output"
    os.makedirs(output_dir, exist_ok=True)

    with open(f"{output_dir}/chapter_1.txt", "w", encoding="utf-8") as f:
        f.write(f"=== 第一章 ===\n\n{draft1}")

    with open(f"{output_dir}/chapter_2.txt", "w", encoding="utf-8") as f:
        f.write(f"=== 第二章 ===\n\n{draft2}")

    print(f"\n[OK] 两章已保存到 {output_dir}/ 目录")

    # ========== 打印正文预览 ==========
    print("\n" + "=" * 60)
    print("第一章正文预览（前1000字）:")
    print("=" * 60)
    print(draft1[:1000])

    print("\n" + "=" * 60)
    print("第二章正文预览（前1000字）:")
    print("=" * 60)
    print(draft2[:1000])

    return True


if __name__ == "__main__":
    success = test_two_chapters()
    sys.exit(0 if success else 1)
