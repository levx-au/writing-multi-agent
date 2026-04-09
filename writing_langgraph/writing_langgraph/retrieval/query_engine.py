"""检索系统 - 支持按人物/道具/伏笔等查询"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from writing_langgraph.db import (
    Character,
    Chapter,
    Item,
    ItemLog,
    NovelMetadata,
    PlotThread,
    PowerChangeLog,
    get_db,
)


@dataclass
class QueryResult:
    """查询结果"""
    success: bool
    data: list[dict]
    message: str = ""


def query_character(
    novel_id: int,
    name: Optional[str] = None,
    role_type: Optional[str] = None,
    is_active: Optional[bool] = None,
) -> QueryResult:
    """
    查询人物

    Args:
        novel_id: 小说 ID
        name: 人物名称（模糊匹配）
        role_type: 角色类型 (protagonist/supporting/antagonist/minor)
        is_active: 是否活跃
    """
    try:
        with get_db(novel_id) as conn:
            sql = "SELECT * FROM character WHERE novel_id = ?"
            params = [novel_id]

            if name:
                sql += " AND name LIKE ?"
                params.append(f"%{name}%")

            if role_type:
                sql += " AND role_type = ?"
                params.append(role_type)

            if is_active is not None:
                sql += " AND is_active = ?"
                params.append(1 if is_active else 0)

            sql += " ORDER BY first_appearance_chapter"

            rows = conn.execute(sql, params).fetchall()
            characters = [dict(row) for row in rows]

            return QueryResult(success=True, data=characters)
    except Exception as e:
        return QueryResult(success=False, data=[], message=str(e))


def query_character_power_history(
    novel_id: int,
    character_name: str,
) -> QueryResult:
    """查询某人物的战力变化历史"""
    try:
        with get_db(novel_id) as conn:
            row = conn.execute(
                "SELECT id FROM character WHERE novel_id = ? AND name LIKE ?",
                (novel_id, f"%{character_name}%"),
            ).fetchone()

            if not row:
                return QueryResult(success=False, data=[], message="人物不存在")

            char_id = row["id"]
            rows = conn.execute(
                """
                SELECT * FROM power_change_log
                WHERE novel_id = ? AND character_id = ?
                ORDER BY chapter_no DESC
                """,
                (novel_id, char_id),
            ).fetchall()

            history = [dict(row) for row in rows]
            return QueryResult(success=True, data=history)
    except Exception as e:
        return QueryResult(success=False, data=[], message=str(e))


def query_character_location(novel_id: int, character_name: str) -> QueryResult:
    """查询某人物当前所在位置"""
    try:
        with get_db(novel_id) as conn:
            row = conn.execute(
                "SELECT current_location FROM character WHERE novel_id = ? AND name LIKE ?",
                (novel_id, f"%{character_name}%"),
            ).fetchone()

            if not row:
                return QueryResult(success=False, data=[], message="人物不存在")

            return QueryResult(
                success=True,
                data=[{"name": character_name, "location": row["current_location"] or "未知"}],
            )
    except Exception as e:
        return QueryResult(success=False, data=[], message=str(e))


def query_item(
    novel_id: int,
    name: Optional[str] = None,
    item_type: Optional[str] = None,
    owner_name: Optional[str] = None,
) -> QueryResult:
    """查询道具"""
    try:
        with get_db(novel_id) as conn:
            sql = """
                SELECT i.*, c.name as owner_name
                FROM item i
                LEFT JOIN character c ON i.owner_id = c.id
                WHERE i.novel_id = ?
            """
            params = [novel_id]

            if name:
                sql += " AND i.name LIKE ?"
                params.append(f"%{name}%")

            if item_type:
                sql += " AND i.item_type = ?"
                params.append(item_type)

            if owner_name:
                sql += " AND c.name LIKE ?"
                params.append(f"%{owner_name}%")

            rows = conn.execute(sql, params).fetchall()
            items = [dict(row) for row in rows]

            return QueryResult(success=True, data=items)
    except Exception as e:
        return QueryResult(success=False, data=[], message=str(e))


def query_item_history(novel_id: int, item_name: str) -> QueryResult:
    """查询道具获得/使用历史"""
    try:
        with get_db(novel_id) as conn:
            row = conn.execute(
                "SELECT id FROM item WHERE novel_id = ? AND name LIKE ?",
                (novel_id, f"%{item_name}%"),
            ).fetchone()

            if not row:
                return QueryResult(success=False, data=[], message="道具不存在")

            item_id = row["id"]
            rows = conn.execute(
                """
                SELECT il.*, c.name as character_name
                FROM item_log il
                LEFT JOIN character c ON il.character_id = c.id
                WHERE il.novel_id = ? AND il.item_id = ?
                ORDER BY il.chapter_no DESC
                """,
                (novel_id, item_id),
            ).fetchall()

            history = [dict(row) for row in rows]
            return QueryResult(success=True, data=history)
    except Exception as e:
        return QueryResult(success=False, data=[], message=str(e))


def query_plot_threads(
    novel_id: int,
    status: Optional[str] = None,
    is_main: bool = False,
) -> QueryResult:
    """
    查询伏笔

    Args:
        novel_id: 小说 ID
        status: 状态 (planted/foreshadowed/resolved/abandoned)
        is_main: 是否主线伏笔
    """
    try:
        with get_db(novel_id) as conn:
            sql = "SELECT * FROM plot_thread WHERE novel_id = ?"
            params = [novel_id]

            if status:
                sql += " AND status = ?"
                params.append(status)

            rows = conn.execute(sql, params).fetchall()

            # 过滤主线伏笔（标题包含"主线"或代码以 F 开头）
            if is_main:
                threads = [
                    dict(row) for row in rows
                    if row["thread_code"].startswith("F")
                ]
            else:
                threads = [dict(row) for row in rows]

            return QueryResult(success=True, data=threads)
    except Exception as e:
        return QueryResult(success=False, data=[], message=str(e))


def query_unresolved_plot_threads(novel_id: int) -> QueryResult:
    """查询未回收的伏笔"""
    return query_plot_threads(novel_id, status="planted")


def query_chapters(
    novel_id: int,
    volume_id: Optional[int] = None,
    status: Optional[str] = None,
    limit: int = 20,
) -> QueryResult:
    """查询章节列表"""
    try:
        with get_db(novel_id) as conn:
            sql = "SELECT * FROM chapter WHERE novel_id = ?"
            params = [novel_id]

            if volume_id:
                sql += " AND volume_id = ?"
                params.append(volume_id)

            if status:
                sql += " AND status = ?"
                params.append(status)

            sql += " ORDER BY chapter_order DESC LIMIT ?"
            params.append(limit)

            rows = conn.execute(sql, params).fetchall()
            chapters = [dict(row) for row in rows]

            return QueryResult(success=True, data=chapters)
    except Exception as e:
        return QueryResult(success=False, data=[], message=str(e))


def query_novel_stats(novel_id: int) -> QueryResult:
    """查询小说统计信息"""
    try:
        with get_db(novel_id) as conn:
            stats = {}

            # 总章节数
            row = conn.execute(
                "SELECT COUNT(*) as cnt, SUM(word_count) as words FROM chapter WHERE novel_id = ?",
                (novel_id,),
            ).fetchone()
            stats["total_chapters"] = row["cnt"] or 0
            stats["total_words"] = row["words"] or 0

            # 已完成章节数
            row = conn.execute(
                "SELECT COUNT(*) as cnt FROM chapter WHERE novel_id = ? AND status = 'finalized'",
                (novel_id,),
            ).fetchone()
            stats["finalized_chapters"] = row["cnt"] or 0

            # 人物数
            row = conn.execute(
                "SELECT COUNT(*) as cnt FROM character WHERE novel_id = ?",
                (novel_id,),
            ).fetchone()
            stats["total_characters"] = row["cnt"] or 0

            # 活跃人物数
            row = conn.execute(
                "SELECT COUNT(*) as cnt FROM character WHERE novel_id = ? AND is_active = 1",
                (novel_id,),
            ).fetchone()
            stats["active_characters"] = row["cnt"] or 0

            # 道具数
            row = conn.execute(
                "SELECT COUNT(*) as cnt FROM item WHERE novel_id = ? AND is_active = 1",
                (novel_id,),
            ).fetchone()
            stats["total_items"] = row["cnt"] or 0

            # 伏笔统计
            row = conn.execute(
                "SELECT status, COUNT(*) as cnt FROM plot_thread WHERE novel_id = ? GROUP BY status",
                (novel_id,),
            ).fetchall()
            stats["plot_threads"] = {r["status"]: r["cnt"] for r in row}

            return QueryResult(success=True, data=[stats])
    except Exception as e:
        return QueryResult(success=False, data=[], message=str(e))
