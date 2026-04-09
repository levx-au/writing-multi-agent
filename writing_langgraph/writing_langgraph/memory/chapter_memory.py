"""章节记忆管理器"""

from __future__ import annotations

from typing import Optional

from writing_langgraph.db import (
    Chapter,
    MemoryChapter,
    get_db,
)


def load_latest_chapter_memory(novel_id: int, chapter_id: int) -> Optional[MemoryChapter]:
    """加载指定章节的最新记忆"""
    with get_db(novel_id) as conn:
        row = conn.execute(
            """
            SELECT * FROM memory_chapter
            WHERE novel_id = ? AND chapter_id = ?
            ORDER BY iteration DESC
            LIMIT 1
            """,
            (novel_id, chapter_id),
        ).fetchone()

        if row is None:
            return None
        return MemoryChapter.from_row(row)


def load_chapter_memory_by_iteration(
    novel_id: int,
    chapter_id: int,
    iteration: int,
) -> Optional[MemoryChapter]:
    """加载指定章节指定迭代轮次的记忆"""
    with get_db(novel_id) as conn:
        row = conn.execute(
            """
            SELECT * FROM memory_chapter
            WHERE novel_id = ? AND chapter_id = ? AND iteration = ?
            """,
            (novel_id, chapter_id, iteration),
        ).fetchone()

        if row is None:
            return None
        return MemoryChapter.from_row(row)


def save_chapter_memory(
    novel_id: int,
    chapter_id: int,
    iteration: int,
    content: str,
) -> MemoryChapter:
    """保存章节记忆（每次迭代都会创建新记录）"""
    with get_db(novel_id) as conn:
        cursor = conn.execute(
            """
            INSERT INTO memory_chapter (novel_id, chapter_id, iteration, content)
            VALUES (?, ?, ?, ?)
            """,
            (novel_id, chapter_id, iteration, content),
        )

        return MemoryChapter(
            id=cursor.lastrowid,
            novel_id=novel_id,
            chapter_id=chapter_id,
            iteration=iteration,
            content=content,
        )


def get_chapter_memory_content(novel_id: int, chapter_id: int) -> str:
    """获取章节最新记忆内容文本"""
    mem = load_latest_chapter_memory(novel_id, chapter_id)
    return mem.content if mem else ""


def get_chapter_history(novel_id: int, chapter_id: int) -> list[MemoryChapter]:
    """获取章节所有迭代轮次的记忆历史"""
    with get_db(novel_id) as conn:
        rows = conn.execute(
            """
            SELECT * FROM memory_chapter
            WHERE novel_id = ? AND chapter_id = ?
            ORDER BY iteration ASC
            """,
            (novel_id, chapter_id),
        ).fetchall()

        return [MemoryChapter.from_row(r) for r in rows]


def create_chapter(
    novel_id: int,
    chapter_order: int,
    volume_id: Optional[int] = None,
    brief: str = "",
    title: str = "",
    generation_config: dict | None = None,
) -> Chapter:
    """创建新章节"""
    import json
    from writing_langgraph.db import json_dumps

    with get_db(novel_id) as conn:
        config_str = json_dumps(generation_config or {})

        cursor = conn.execute(
            """
            INSERT INTO chapter
            (novel_id, volume_id, chapter_order, title, brief, status, generation_config)
            VALUES (?, ?, ?, ?, ?, 'pending', ?)
            """,
            (novel_id, volume_id, chapter_order, title, brief, config_str),
        )

        return Chapter(
            id=cursor.lastrowid,
            novel_id=novel_id,
            volume_id=volume_id,
            chapter_order=chapter_order,
            title=title,
            brief=brief,
            status="pending",
            generation_config=config_str,
        )


def update_chapter(
    novel_id: int,
    chapter_id: int,
    plan: Optional[str] = None,
    draft: Optional[str] = None,
    score: Optional[float] = None,
    status: Optional[str] = None,
) -> None:
    """更新章节内容（通过 chapter.id 主键）"""
    with get_db(novel_id) as conn:
        updates = []
        params = []

        if plan is not None:
            updates.append("plan = ?")
            params.append(plan)

        if draft is not None:
            updates.append("draft = ?")
            params.append(draft)

            word_count = len(draft) if draft else 0
            updates.append("word_count = ?")
            params.append(word_count)

        if score is not None:
            updates.append("score = ?")
            params.append(score)

        if status is not None:
            updates.append("status = ?")
            params.append(status)

        if not updates:
            return

        updates.append("updated_at = CURRENT_TIMESTAMP")
        params.append(chapter_id)

        sql = f"UPDATE chapter SET {', '.join(updates)} WHERE id = ?"
        conn.execute(sql, params)


def upsert_chapter(
    novel_id: int,
    chapter_no: int,
    plan: Optional[str] = None,
    draft: Optional[str] = None,
    score: Optional[float] = None,
    iteration: Optional[int] = None,
    status: Optional[str] = None,
) -> Optional[Chapter]:
    """
    插入或更新章节（通过 novel_id + chapter_order 定位）。

    如果章节已存在则更新，不存在则插入。
    使用事务确保原子性。
    """
    import json
    from writing_langgraph.db import json_dumps, transaction

    with transaction(novel_id) as conn:
        existing = conn.execute(
            "SELECT id FROM chapter WHERE novel_id = ? AND chapter_order = ?",
            (novel_id, chapter_no),
        ).fetchone()

        word_count = len(draft) if draft else 0

        if existing:
            updates = []
            params = []
            if draft is not None:
                updates.append("draft = ?")
                params.append(draft)
                updates.append("word_count = ?")
                params.append(word_count)
            if score is not None:
                updates.append("score = ?")
                params.append(score)
            if status is not None:
                updates.append("status = ?")
                params.append(status)
            if plan is not None:
                updates.append("plan = ?")
                params.append(plan)
            updates.append("updated_at = CURRENT_TIMESTAMP")
            params.append(existing["id"])

            if updates:
                sql = f"UPDATE chapter SET {', '.join(updates)} WHERE id = ?"
                conn.execute(sql, params)

            chapter_id = existing["id"]
        else:
            config = {"iteration": iteration or 1}
            cursor = conn.execute(
                """
                INSERT INTO chapter
                (novel_id, chapter_order, title, brief, status, generation_config, draft, word_count, plan, score)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    novel_id,
                    chapter_no,
                    "",
                    "",
                    status or "pending",
                    json_dumps(config),
                    draft or "",
                    word_count,
                    plan or "",
                    score or 0.0,
                ),
            )
            chapter_id = cursor.lastrowid

    return get_chapter(novel_id, chapter_id)


def get_chapter(novel_id: int, chapter_id: int) -> Optional[Chapter]:
    """获取章节"""
    with get_db(novel_id) as conn:
        row = conn.execute(
            "SELECT * FROM chapter WHERE id = ?",
            (chapter_id,),
        ).fetchone()

        if row is None:
            return None
        return Chapter.from_row(row)


def get_chapter_by_order(novel_id: int, chapter_order: int) -> Optional[Chapter]:
    """根据章节序号获取章节"""
    with get_db(novel_id) as conn:
        row = conn.execute(
            "SELECT * FROM chapter WHERE novel_id = ? AND chapter_order = ?",
            (novel_id, chapter_order),
        ).fetchone()

        if row is None:
            return None
        return Chapter.from_row(row)


def get_recent_chapters(novel_id: int, limit: int = 10) -> list[Chapter]:
    """获取最近 N 个章节"""
    with get_db(novel_id) as conn:
        rows = conn.execute(
            """
            SELECT * FROM chapter
            WHERE novel_id = ? AND status = 'finalized'
            ORDER BY chapter_order DESC
            LIMIT ?
            """,
            (novel_id, limit),
        ).fetchall()

        return [Chapter.from_row(r) for r in rows]
