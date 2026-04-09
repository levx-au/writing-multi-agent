"""数据库 ORM 模型"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional


def json_loads(s: str | None, default: Any = None) -> Any:
    """安全解析 JSON"""
    if s is None or s == "":
        return default
    try:
        return json.loads(s)
    except (json.JSONDecodeError, TypeError):
        return default


def json_dumps(obj: Any, default: str = "{}") -> str:
    """安全序列化 JSON"""
    try:
        return json.dumps(obj, ensure_ascii=False)
    except (TypeError, ValueError):
        return default


@dataclass
class NovelMetadata:
    """小说元数据"""
    id: int = 0
    title: str = ""
    genre: str = ""
    world_rules: str = "{}"
    power_system_name: Optional[str] = None
    main_plot_outline: str = ""
    theme: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @property
    def world_rules_dict(self) -> dict:
        return json_loads(self.world_rules, {})

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> NovelMetadata:
        return cls(
            id=row["id"],
            title=row["title"],
            genre=row["genre"],
            world_rules=row["world_rules"] or "{}",
            power_system_name=row["power_system_name"],
            main_plot_outline=row["main_plot_outline"] or "",
            theme=row["theme"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


@dataclass
class PowerLevel:
    """战力/境界定义"""
    id: int = 0
    novel_id: int = 0
    level_order: int = 0
    name: str = ""
    description: Optional[str] = None
    is_realm_boundary: bool = False

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> PowerLevel:
        return cls(
            id=row["id"],
            novel_id=row["novel_id"],
            level_order=row["level_order"],
            name=row["name"],
            description=row["description"],
            is_realm_boundary=bool(row["is_realm_boundary"]),
        )


@dataclass
class Character:
    """人物"""
    id: int = 0
    novel_id: int = 0
    name: str = ""
    alias: Optional[str] = None
    role_type: str = "supporting"
    core_motivation: Optional[str] = None
    core_flaw: Optional[str] = None
    arc_direction: Optional[str] = None
    current_power_level: Optional[str] = None
    current_location: Optional[str] = None
    physical_state: str = "{}"
    psychological_state: str = "{}"
    inventory: str = "[]"
    is_active: bool = True
    first_appearance_chapter: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @property
    def physical(self) -> dict:
        return json_loads(self.physical_state, {})

    @property
    def psychological(self) -> dict:
        return json_loads(self.psychological_state, {})

    @property
    def inventory_list(self) -> list:
        return json_loads(self.inventory, [])

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> Character:
        return cls(
            id=row["id"],
            novel_id=row["novel_id"],
            name=row["name"],
            alias=row["alias"],
            role_type=row["role_type"] or "supporting",
            core_motivation=row["core_motivation"],
            core_flaw=row["core_flaw"],
            arc_direction=row["arc_direction"],
            current_power_level=row["current_power_level"],
            current_location=row["current_location"],
            physical_state=row["physical_state"] or "{}",
            psychological_state=row["psychological_state"] or "{}",
            inventory=row["inventory"] or "[]",
            is_active=bool(row["is_active"]),
            first_appearance_chapter=row["first_appearance_chapter"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


@dataclass
class CharacterRelationship:
    """人物关系"""
    id: int = 0
    novel_id: int = 0
    char_a_id: int = 0
    char_b_id: int = 0
    relationship_type: str = ""
    description: Optional[str] = None
    start_chapter: Optional[int] = None
    is_active: bool = True
    updated_at: Optional[datetime] = None

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> CharacterRelationship:
        return cls(
            id=row["id"],
            novel_id=row["novel_id"],
            char_a_id=row["char_a_id"],
            char_b_id=row["char_b_id"],
            relationship_type=row["relationship_type"],
            description=row["description"],
            start_chapter=row["start_chapter"],
            is_active=bool(row["is_active"]),
            updated_at=row["updated_at"],
        )


@dataclass
class Item:
    """道具/功法/宝物"""
    id: int = 0
    novel_id: int = 0
    name: str = ""
    item_type: str = "other"
    rarity: str = "common"
    owner_id: Optional[int] = None
    previous_owner_id: Optional[int] = None
    description: Optional[str] = None
    abilities: str = "[]"
    origin: Optional[str] = None
    first_appearance_chapter: Optional[int] = None
    is_active: bool = True
    created_at: Optional[datetime] = None

    @property
    def abilities_list(self) -> list:
        return json_loads(self.abilities, [])

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> Item:
        return cls(
            id=row["id"],
            novel_id=row["novel_id"],
            name=row["name"],
            item_type=row["item_type"] or "other",
            rarity=row["rarity"] or "common",
            owner_id=row["owner_id"],
            previous_owner_id=row["previous_owner_id"],
            description=row["description"],
            abilities=row["abilities"] or "[]",
            origin=row["origin"],
            first_appearance_chapter=row["first_appearance_chapter"],
            is_active=bool(row["is_active"]),
            created_at=row["created_at"],
        )


@dataclass
class PowerChangeLog:
    """战力变化日志"""
    id: int = 0
    novel_id: int = 0
    character_id: int = 0
    from_level: str = ""
    to_level: str = ""
    chapter_no: int = 0
    cause: Optional[str] = None
    details: Optional[str] = None
    created_at: Optional[datetime] = None

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> PowerChangeLog:
        return cls(
            id=row["id"],
            novel_id=row["novel_id"],
            character_id=row["character_id"],
            from_level=row["from_level"],
            to_level=row["to_level"],
            chapter_no=row["chapter_no"],
            cause=row["cause"],
            details=row["details"],
            created_at=row["created_at"],
        )


@dataclass
class ItemLog:
    """道具日志"""
    id: int = 0
    novel_id: int = 0
    item_id: int = 0
    character_id: Optional[int] = None
    action_type: str = ""
    chapter_no: int = 0
    details: Optional[str] = None
    created_at: Optional[datetime] = None

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> ItemLog:
        return cls(
            id=row["id"],
            novel_id=row["novel_id"],
            item_id=row["item_id"],
            character_id=row["character_id"],
            action_type=row["action_type"],
            chapter_no=row["chapter_no"],
            details=row["details"],
            created_at=row["created_at"],
        )


@dataclass
class PlotThread:
    """伏笔/情节线"""
    id: int = 0
    novel_id: int = 0
    thread_code: str = ""
    title: str = ""
    content_summary: str = ""
    planted_chapter: Optional[int] = None
    planned_resolution_chapter: Optional[int] = None
    actual_resolution_chapter: Optional[int] = None
    status: str = "planted"
    resolution_summary: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> PlotThread:
        return cls(
            id=row["id"],
            novel_id=row["novel_id"],
            thread_code=row["thread_code"],
            title=row["title"],
            content_summary=row["content_summary"],
            planted_chapter=row["planted_chapter"],
            planned_resolution_chapter=row["planned_resolution_chapter"],
            actual_resolution_chapter=row["actual_resolution_chapter"],
            status=row["status"] or "planted",
            resolution_summary=row["resolution_summary"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


@dataclass
class Volume:
    """卷"""
    id: int = 0
    novel_id: int = 0
    volume_order: int = 0
    title: str = ""
    outline: Optional[str] = None
    start_chapter: int = 0
    end_chapter: Optional[int] = None
    status: str = "planning"
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> Volume:
        return cls(
            id=row["id"],
            novel_id=row["novel_id"],
            volume_order=row["volume_order"],
            title=row["title"],
            outline=row["outline"],
            start_chapter=row["start_chapter"],
            end_chapter=row["end_chapter"],
            status=row["status"] or "planning",
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


@dataclass
class Chapter:
    """章节"""
    id: int = 0
    novel_id: int = 0
    volume_id: Optional[int] = None
    chapter_order: int = 0
    title: Optional[str] = None
    brief: Optional[str] = None
    plan: Optional[str] = None
    draft: Optional[str] = None
    word_count: Optional[int] = None
    score: Optional[float] = None
    status: str = "pending"
    generation_config: str = "{}"
    parent_chapter_id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @property
    def config_dict(self) -> dict:
        return json_loads(self.generation_config, {})

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> Chapter:
        return cls(
            id=row["id"],
            novel_id=row["novel_id"],
            volume_id=row["volume_id"],
            chapter_order=row["chapter_order"],
            title=row["title"],
            brief=row["brief"],
            plan=row["plan"],
            draft=row["draft"],
            word_count=row["word_count"],
            score=row["score"],
            status=row["status"] or "pending",
            generation_config=row["generation_config"] or "{}",
            parent_chapter_id=row["parent_chapter_id"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


@dataclass
class MemoryGlobal:
    """全局记忆"""
    id: int = 0
    novel_id: int = 0
    content: str = ""
    version: int = 1
    updated_at: Optional[datetime] = None

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> MemoryGlobal:
        return cls(
            id=row["id"],
            novel_id=row["novel_id"],
            content=row["content"],
            version=row["version"],
            updated_at=row["updated_at"],
        )


@dataclass
class MemoryVolume:
    """卷记忆"""
    id: int = 0
    novel_id: int = 0
    volume_id: int = 0
    content: str = ""
    version: int = 1
    updated_at: Optional[datetime] = None

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> MemoryVolume:
        return cls(
            id=row["id"],
            novel_id=row["novel_id"],
            volume_id=row["volume_id"],
            content=row["content"],
            version=row["version"],
            updated_at=row["updated_at"],
        )


@dataclass
class MemoryChapter:
    """章节记忆"""
    id: int = 0
    novel_id: int = 0
    chapter_id: int = 0
    iteration: int = 0
    content: str = ""
    created_at: Optional[datetime] = None

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> MemoryChapter:
        return cls(
            id=row["id"],
            novel_id=row["novel_id"],
            chapter_id=row["chapter_id"],
            iteration=row["iteration"],
            content=row["content"],
            created_at=row["created_at"],
        )


@dataclass
class TropeTemplate:
    """网文套路模板"""
    id: int = 0
    novel_id: int = 0
    trope_type: str = ""
    template_name: str = ""
    trigger_condition: Optional[str] = None
    typical_arc: Optional[str] = None
    key_beat_sequence: str = "[]"
    example_summary: Optional[str] = None
    usage_count: int = 0
    last_used_chapter: Optional[int] = None
    created_at: Optional[datetime] = None

    @property
    def beats(self) -> list:
        return json_loads(self.key_beat_sequence, [])

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> TropeTemplate:
        return cls(
            id=row["id"],
            novel_id=row["novel_id"],
            trope_type=row["trope_type"],
            template_name=row["template_name"],
            trigger_condition=row["trigger_condition"],
            typical_arc=row["typical_arc"],
            key_beat_sequence=row["key_beat_sequence"] or "[]",
            example_summary=row["example_summary"],
            usage_count=row["usage_count"],
            last_used_chapter=row["last_used_chapter"],
            created_at=row["created_at"],
        )
