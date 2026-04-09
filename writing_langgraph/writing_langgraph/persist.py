"""章节文件持久化 - 支持文件和数据库两种模式"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Optional

from writing_langgraph.db import Chapter, transaction


def save_chapter_file(
    *,
    output_dir: str,
    chapter_no: int,
    draft: str,
    chapter_task: str,
    score: float,
    iteration: int,
    plan_excerpt_max_chars: int = 1200,
    plan: str = "",
) -> Path:
    """
    将章节保存为 Markdown 文件。

    Returns:
        保存的文件路径
    """
    root = Path(output_dir or "novel_output").expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)

    # 生成文件名，避免覆盖已有文件
    base_path = root / f"chapter_{int(chapter_no):03d}"
    path = base_path.with_suffix(".md")
    if path.exists():
        # 文件已存在，添加版本号
        for version in range(2, 100):
            path = base_path.parent / f"{base_path.stem}_v{version}.md"
            if not path.exists():
                break

    plan_str = str(plan) if plan else ""

    # 确保 draft 是纯文本字符串
    if isinstance(draft, str):
        draft_str = draft
    elif isinstance(draft, (list, dict)):
        # 处理 content block 格式（如 LangChain 的 AIMessage content）
        if isinstance(draft, list):
            draft_str = "".join(
                item.get("text", str(item)) if isinstance(item, dict) else str(item)
                for item in draft
            )
        else:
            draft_str = str(draft)
    else:
        draft_str = str(draft) if draft else ""

    brief_str = str(chapter_task) if chapter_task else ""
    excerpt = plan_str[:plan_excerpt_max_chars]
    if len(plan_str) > plan_excerpt_max_chars:
        excerpt += "\n\n…（策划节选，完整见同目录 plan_snapshot 或 UI）"
    body = f"""---
chapter: {int(chapter_no)}
score: {float(score):.1f}
writer_iterations: {int(iteration)}
chapter_brief: {brief_str!r}
---

## 本章任务

{brief_str}

## 正文

{draft_str}

## 策划节选（定稿时蓝图快照）

{excerpt or "（无）"}
"""
    path.write_text(body, encoding="utf-8")
    return path


def save_chapter_to_db(
    novel_id: int,
    chapter_no: int,
    draft: str,
    plan: str,
    score: float,
    iteration: int,
    status: str = "finalized",
) -> None:
    """
    将章节保存到数据库（INSERT-or-UPDATE 语义）。

    Args:
        novel_id: 小说 ID
        chapter_no: 章节序号（用于唯一定位章节）
        draft: 正文内容
        plan: 策划方案
        score: 评分
        iteration: 迭代轮次
        status: 章节状态
    """
    from writing_langgraph.memory.chapter_memory import upsert_chapter

    upsert_chapter(
        novel_id=novel_id,
        chapter_no=chapter_no,
        draft=draft,
        plan=plan,
        score=score,
        iteration=iteration,
        status=status,
    )


def save_chapter(
    *,
    novel_id: int,
    chapter_no: int,
    output_dir: Optional[str] = None,
    draft: str,
    chapter_task: str,
    score: float,
    iteration: int,
    plan: str = "",
    save_to_file: bool = True,
    save_to_db: bool = True,
) -> tuple[Optional[Path], bool]:
    """
    保存章节（支持文件和数据库双模式）。

    Args:
        novel_id: 小说 ID
        chapter_no: 章节序号
        output_dir: 文件输出目录
        draft: 正文
        chapter_brief: 章节任务
        score: 评分
        iteration: 迭代轮次
        plan: 策划方案
        save_to_file: 是否保存到文件
        save_to_db: 是否保存到数据库

    Returns:
        (文件路径, 是否成功)
    """
    file_path = None
    db_success = True

    if save_to_file and output_dir:
        try:
            file_path = save_chapter_file(
                output_dir=output_dir,
                chapter_no=chapter_no,
                draft=draft,
                chapter_task=chapter_task,
                score=score,
                iteration=iteration,
                plan=plan,
            )
        except (OSError, IOError) as e:
            file_path = None

    if save_to_db:
        try:
            save_chapter_to_db(
                novel_id=novel_id,
                chapter_no=chapter_no,
                draft=draft,
                plan=plan,
                score=score,
                iteration=iteration,
            )
            db_success = True
        except sqlite3.Error:
            db_success = False

    return file_path, db_success
