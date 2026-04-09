"""测试：生成一章小说"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_write():
    from writing_langgraph.graph import build_writing_graph
    from writing_langgraph.state import initial_state

    # 使用 Fake LLM 测试图构建
    class FakeResponse:
        def __init__(self, content):
            self.content = content

    class FakeChatOpenAI:
        def bind(self, **kwargs):
            return self
        def invoke(self, messages):
            content = messages[-1].content if messages else ""
            # 根据消息内容返回不同响应
            if "策划" in str(content) or "宏观规划" in str(content):
                return FakeResponse("""# 宏观规划

## 类型与基调
玄幻修仙小说，主角从凡人崛起，最终成为一代仙尊。

## 大故事框架
### 大故事1（第1-100章）：凡人流崛起
- 核心目标：主角进入修仙门派
- 主要障碍：灵根资质低下
- 阶段结局：筑基成功，加入内门
""")
            elif "小故事" in str(content) or "阶段性规划" in str(content):
                return FakeResponse("""## 小故事1（第1-10章）：入门考核

### 核心目标
主角通过宗门入门考核

### 关键情节点
- 第1-3章：主角林寒得知宗门招生
- 第4-6章：参加考核，遇到刁难
- 第7-10章：通过考核，成为外门弟子

### 主角收获
- 能力：炼气一层
- 关系：结识师兄李明
- 认知：修仙世界的残酷
""")
            elif "本章写作指引" in str(content):
                return FakeResponse("""## 本章核心任务
主角林寒参加青云宗入门考核

## 设定约束
- 主角资质：杂灵根
- 考核内容：灵力测试+心性考验
""")
            elif "审阅" in str(content) or "Critic" in str(content):
                return FakeResponse("""架构层反馈：世界观完整，情节推进合理
文字层反馈：语句流畅，描写生动

{
  "arch_feedback": "世界观完整，情节推进合理",
  "prose_feedback": "语句流畅，描写生动",
  "arch_action": "keep",
  "prose_action": "keep",
  "score": 8.5
}
""")
            else:
                return FakeResponse("""这是一个测试章节的正文。

林寒站在青云宗的山门前，望着云雾缭绕的仙山，心中豪情万丈。

"我一定要成为修仙者！"他在心中暗暗发誓。

经过层层考核，林寒终于凭借坚定的意志通过了入门测试，成为了一名外门弟子。
""")

    print("=" * 60)
    print("测试：生成一章小说")
    print("=" * 60)

    llm = FakeChatOpenAI()
    graph = build_writing_graph(llm)
    print(f"[OK] 图构建成功，节点: {list(graph.nodes.keys())}")

    state = initial_state(
        story_idea="写一个玄幻修仙小说，主角林寒是杂灵根的少年",
        chapter_task="主角林寒参加青云宗入门考核",
        max_iterations=2,
        score_pass=8.0,
        chapter_no=1,
        novel_id=1,
    )
    print(f"[OK] 状态创建成功")

    print("\n开始执行工作流...")
    final_state = graph.invoke(state)

    print("\n" + "=" * 60)
    print("执行结果")
    print("=" * 60)
    print(f"章节号: {final_state.get('chapter_no')}")
    print(f"迭代次数: {final_state.get('iteration')}")
    print(f"评分: {final_state.get('score')}")
    print(f"停止原因: {final_state.get('stopped_reason')}")
    print(f"策划长度: {len(final_state.get('plan', ''))} 字")
    print(f"正文长度: {len(final_state.get('draft', ''))} 字")
    print(f"Draft预览: {final_state.get('draft', '')[:200]}...")

    if final_state.get('draft'):
        print("\n[OK] Draft generated!")
    else:
        print("\n[FAIL] No draft generated!")

    return final_state.get('draft') and len(final_state.get('draft', '')) > 100

if __name__ == "__main__":
    success = test_write()
    sys.exit(0 if success else 1)
