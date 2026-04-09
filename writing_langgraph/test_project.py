"""项目完整性测试 - 验证各模块能否正常导入和基本调用"""

import sys
import os

# 确保项目根目录在 Python 路径中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_imports():
    """测试所有核心模块能否正常导入"""
    print("=" * 60)
    print("1. 测试模块导入...")
    print("=" * 60)

    try:
        from writing_langgraph import state, schemas, prompts, utils
        print("  [OK] state.py")
        print("  [OK] schemas.py")
        print("  [OK] prompts.py")
        print("  [OK] utils.py")
    except ImportError as e:
        print(f"  [FAIL] 核心模块导入失败: {e}")
        return False

    try:
        from writing_langgraph import agents
        print("  [OK] agents.py")
    except ImportError as e:
        print(f"  [FAIL] agents.py 导入失败: {e}")
        return False

    try:
        from writing_langgraph import graph
        print("  [OK] graph.py")
    except ImportError as e:
        print(f"  [FAIL] graph.py 导入失败: {e}")
        return False

    try:
        from writing_langgraph.db import connection, models
        print("  [OK] db/connection.py")
        print("  [OK] db/models.py")
    except ImportError as e:
        print(f"  [FAIL] db 模块导入失败: {e}")
        return False

    try:
        from writing_langgraph.memory import (
            global_memory, volume_memory, chapter_memory,
            memory_parser, tools, plot_insert
        )
        print("  [OK] memory/global_memory.py")
        print("  [OK] memory/volume_memory.py")
        print("  [OK] memory/chapter_memory.py")
        print("  [OK] memory/memory_parser.py")
        print("  [OK] memory/tools.py")
        print("  [OK] memory/plot_insert.py")
    except ImportError as e:
        print(f"  [FAIL] memory 模块导入失败: {e}")
        return False

    return True


def test_db_init():
    """测试数据库初始化"""
    print("\n" + "=" * 60)
    print("2. 测试数据库初始化...")
    print("=" * 60)

    try:
        import tempfile
        from writing_langgraph.db.connection import init_db, get_db_path

        # 使用临时目录避免污染
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = get_db_path(99, db_dir=tmpdir)

            conn = init_db(99, title="测试小说", genre="玄幻", db_dir=tmpdir)
            print(f"  [OK] 数据库创建成功: {db_path}")

            # 验证表存在
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            )
            tables = [row[0] for row in cursor.fetchall()]
            print(f"  [OK] 数据库表数量: {len(tables)}")
            for t in tables:
                print(f"       - {t}")

            # 验证元数据
            row = conn.execute(
                "SELECT id, title, genre FROM novel_metadata WHERE id = 99"
            ).fetchone()
            print(f"  [OK] 元数据: id={row[0]}, title={row[1]}, genre={row[2]}")

            conn.close()

        return True
    except Exception as e:
        print(f"  [FAIL] 数据库测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_state_creation():
    """测试状态创建"""
    print("\n" + "=" * 60)
    print("3. 测试状态创建...")
    print("=" * 60)

    try:
        from writing_langgraph.state import initial_state, WritingState

        state = initial_state(
            story_idea="写一个修仙小说",
            chapter_task="主角林寒是个杂灵根的少年",
            max_iterations=2,
            score_pass=8.0,
            chapter_no=1,
            novel_id=1,
        )

        print(f"  [OK] initial_state 创建成功")
        print(f"       novel_id: {state['novel_id']}")
        print(f"       chapter_no: {state['chapter_no']}")
        print(f"       max_iterations: {state['max_iterations']}")
        print(f"       score_pass: {state['score_pass']}")
        print(f"       story_idea: {state.get('story_idea', '')[:20]}...")

        # 验证是 WritingState 类型
        # TypedDict 不支持 isinstance，改为检查 keys
        assert set(state.keys()).issuperset({"novel_id", "chapter_no", "story_idea"})
        print("  [OK] 类型验证通过")

        return True
    except Exception as e:
        print(f"  [FAIL] 状态创建失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_graph_build():
    """测试 LangGraph 图构建"""
    print("\n" + "=" * 60)
    print("4. 测试 LangGraph 图构建...")
    print("=" * 60)

    try:
        from langchain_openai import ChatOpenAI
        from writing_langgraph.graph import build_writing_graph

        # 使用假 API key 测试图构建（不需要真实调用）
        class FakeChatOpenAI:
            def bind(self, **kwargs):
                return self
            def invoke(self, messages):
                class FakeResponse:
                    content = '{"arch_feedback":"ok","prose_feedback":"ok","arch_action":"keep","prose_action":"keep","score":8.5}'
                return FakeResponse()

        fake_llm = FakeChatOpenAI()
        g = build_writing_graph(fake_llm)
        print(f"  [OK] LangGraph 构建成功")
        print(f"       图节点: {g.nodes.keys() if hasattr(g, 'nodes') else 'N/A'}")

        return True
    except Exception as e:
        print(f"  [FAIL] 图构建失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_memory_tools():
    """测试记忆工具"""
    print("\n" + "=" * 60)
    print("5. 测试记忆工具...")
    print("=" * 60)

    try:
        from writing_langgraph.memory.tools import get_full_context

        # 测试工具函数存在
        print(f"  [OK] get_full_context 函数存在: {callable(get_full_context)}")

        # 测试工具 metadata
        print(f"  [OK] get_full_context.name: {get_full_context.name}")
        print(f"  [OK] get_full_context.description: {get_full_context.description[:50]}...")

        return True
    except Exception as e:
        print(f"  [FAIL] 记忆工具测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_schemas():
    """测试 schema 解析"""
    print("\n" + "=" * 60)
    print("6. 测试 CriticResponse 解析...")
    print("=" * 60)

    try:
        from writing_langgraph.schemas import CriticResponse

        # 测试 JSON 解析
        json_str = '''{
            "arch_feedback": "世界观完整",
            "prose_feedback": "文笔流畅",
            "arch_action": "keep",
            "prose_action": "keep",
            "score": 8.5
        }'''

        resp = CriticResponse.from_json(json_str)
        print(f"  [OK] JSON 解析: score={resp.score}, arch_action={resp.arch_action}")

        # 测试 Markdown fallback
        md_str = """
### 架构层
世界观完整，人物弧清晰

### 文字层
文笔流畅，对话自然

ARCH_ACTION: revise
PROSE_ACTION: keep
SCORE: 7.5
"""
        resp2 = CriticResponse._from_markdown_fallback(md_str)
        print(f"  [OK] Markdown 解析: score={resp2.score}, arch_action={resp2.arch_action}")

        # 测试 to_state_updates
        updates = resp.to_state_updates()
        print(f"  [OK] to_state_updates: keys={list(updates.keys())}")

        return True
    except Exception as e:
        print(f"  [FAIL] Schema 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_prompts():
    """测试 prompt 模板"""
    print("\n" + "=" * 60)
    print("7. 测试 Prompt 模板...")
    print("=" * 60)

    try:
        from writing_langgraph.prompts import (
            PLANNER_SYSTEM, WRITER_SYSTEM, CRITIC_SYSTEM,
            MEMORY_SYSTEM
        )

        print(f"  [OK] PLANNER_SYSTEM: {len(PLANNER_SYSTEM)} 字符")
        print(f"  [OK] WRITER_SYSTEM: {len(WRITER_SYSTEM)} 字符")
        print(f"  [OK] CRITIC_SYSTEM: {len(CRITIC_SYSTEM)} 字符")
        print(f"  [OK] MEMORY_SYSTEM: {len(MEMORY_SYSTEM)} 字符")

        return True
    except Exception as e:
        print(f"  [FAIL] Prompt 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    print("\n" + "#" * 60)
    print("# writing_langgraph Project Test")
    print("#" * 60)

    results = []

    results.append(("模块导入", test_imports()))
    results.append(("数据库初始化", test_db_init()))
    results.append(("状态创建", test_state_creation()))
    results.append(("Graph 构建", test_graph_build()))
    results.append(("记忆工具", test_memory_tools()))
    results.append(("Schema 解析", test_schemas()))
    results.append(("Prompt 模板", test_prompts()))

    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)

    all_pass = True
    for name, passed in results:
        status = "PASS" if passed else "FAIL"
        print(f"  [{status}] - {name}")
        if not passed:
            all_pass = False

    print("=" * 60)
    if all_pass:
        print("All tests passed! Project can run.")
    else:
        print("Some tests failed, please check errors.")

    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
