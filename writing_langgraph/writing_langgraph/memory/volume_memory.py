"""卷记忆管理器"""

from __future__ import annotations

from typing import Optional

from writing_langgraph.db import (
    Character,
    MemoryVolume,
    Volume,
    get_db,
)


def load_volume_memory(novel_id: int, volume_id: int) -> Optional[MemoryVolume]:
    """加载指定卷的记忆"""
    with get_db(novel_id) as conn:
        row = conn.execute(
            """
            SELECT * FROM memory_volume
            WHERE novel_id = ? AND volume_id = ?
            ORDER BY version DESC
            LIMIT 1
            """,
            (novel_id, volume_id),
        ).fetchone()

        if row is None:
            return None
        return MemoryVolume.from_row(row)


def save_volume_memory(
    novel_id: int,
    volume_id: int,
    content: str,
) -> MemoryVolume:
    """保存新版卷记忆"""
    with get_db(novel_id) as conn:
        row = conn.execute(
            "SELECT MAX(version) as max_ver FROM memory_volume WHERE volume_id = ?",
            (volume_id,),
        ).fetchone()
        max_ver = row["max_ver"] or 0

        cursor = conn.execute(
            """
            INSERT INTO memory_volume (novel_id, volume_id, content, version)
            VALUES (?, ?, ?, ?)
            """,
            (novel_id, volume_id, content, max_ver + 1),
        )

        return MemoryVolume(
            id=cursor.lastrowid,
            novel_id=novel_id,
            volume_id=volume_id,
            content=content,
            version=max_ver + 1,
        )


def get_volume_memory_content(novel_id: int, volume_id: int) -> str:
    """获取卷记忆内容文本"""
    mem = load_volume_memory(novel_id, volume_id)
    return mem.content if mem else ""


def get_current_volume(novel_id: int) -> Optional[Volume]:
    """获取当前进行中的卷"""
    with get_db(novel_id) as conn:
        row = conn.execute(
            """
            SELECT * FROM volume
            WHERE novel_id = ? AND status = 'in_progress'
            ORDER BY volume_order DESC
            LIMIT 1
            """,
            (novel_id,),
        ).fetchone()

        if row is None:
            return None
        return Volume.from_row(row)


def get_or_create_volume(
    novel_id: int,
    volume_order: int,
    title: str = "",
) -> Volume:
    """获取或创建卷"""
    with get_db(novel_id) as conn:
        row = conn.execute(
            """
            SELECT * FROM volume
            WHERE novel_id = ? AND volume_order = ?
            """,
            (novel_id, volume_order),
        ).fetchone()

        if row:
            return Volume.from_row(row)

        # 创建新卷
        # 计算起始章节号
        last_row = conn.execute(
            """
            SELECT MAX(end_chapter) as max_ch FROM volume
            WHERE novel_id = ?
            """,
            (novel_id,),
        ).fetchone()
        start_ch = (last_row["max_ch"] or 0) + 1

        cursor = conn.execute(
            """
            INSERT INTO volume (novel_id, volume_order, title, start_chapter, status)
            VALUES (?, ?, ?, ?, 'in_progress')
            """,
            (novel_id, volume_order, title or f"第{volume_order}卷", start_ch),
        )

        return Volume(
            id=cursor.lastrowid,
            novel_id=novel_id,
            volume_order=volume_order,
            title=title or f"第{volume_order}卷",
            start_chapter=start_ch,
            status="in_progress",
        )


def finalize_volume(novel_id: int, volume_id: int, end_chapter: int) -> None:
    """完成卷写作，更新状态和结束章节"""
    with get_db(novel_id) as conn:
        conn.execute(
            """
            UPDATE volume
            SET status = 'completed', end_chapter = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (end_chapter, volume_id),
        )
