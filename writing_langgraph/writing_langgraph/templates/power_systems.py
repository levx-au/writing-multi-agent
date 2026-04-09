"""战力体系模板 - 网文常用战力系统"""

from __future__ import annotations


# =============================================
# 修仙体系
# =============================================

XIANXIA_CULTIVATION_REALMS = [
    # 炼气期
    {"name": "炼气初期", "order": 1, "is_realm_boundary": False},
    {"name": "炼气中期", "order": 2, "is_realm_boundary": False},
    {"name": "炼气后期", "order": 3, "is_realm_boundary": False},
    {"name": "炼气巅峰", "order": 4, "is_realm_boundary": False},
    # 筑基期
    {"name": "筑基初期", "order": 5, "is_realm_boundary": False},
    {"name": "筑基中期", "order": 6, "is_realm_boundary": False},
    {"name": "筑基后期", "order": 7, "is_realm_boundary": False},
    {"name": "筑基巅峰", "order": 8, "is_realm_boundary": True},  # 大境界
    # 金丹期
    {"name": "金丹初期", "order": 9, "is_realm_boundary": False},
    {"name": "金丹中期", "order": 10, "is_realm_boundary": False},
    {"name": "金丹后期", "order": 11, "is_realm_boundary": False},
    {"name": "金丹巅峰", "order": 12, "is_realm_boundary": True},  # 大境界
    # 元婴期
    {"name": "元婴初期", "order": 13, "is_realm_boundary": False},
    {"name": "元婴中期", "order": 14, "is_realm_boundary": False},
    {"name": "元婴后期", "order": 15, "is_realm_boundary": False},
    {"name": "元婴巅峰", "order": 16, "is_realm_boundary": True},  # 大境界
    # 化神期
    {"name": "化神初期", "order": 17, "is_realm_boundary": False},
    {"name": "化神中期", "order": 18, "is_realm_boundary": False},
    {"name": "化神后期", "order": 19, "is_realm_boundary": False},
    {"name": "化神巅峰", "order": 20, "is_realm_boundary": True},  # 大境界
]

# =============================================
# 都市异能体系
# =============================================

URBAN_ABILITY_LEVELS = [
    {"name": "F级异能者", "order": 1, "is_realm_boundary": False},
    {"name": "E级异能者", "order": 2, "is_realm_boundary": False},
    {"name": "D级异能者", "order": 3, "is_realm_boundary": False},
    {"name": "C级异能者", "order": 4, "is_realm_boundary": False},
    {"name": "B级异能者", "order": 5, "is_realm_boundary": False},
    {"name": "A级异能者", "order": 6, "is_realm_boundary": False},
    {"name": "S级异能者", "order": 7, "is_realm_boundary": False},
    {"name": "SS级异能者", "order": 8, "is_realm_boundary": True},
    {"name": "SSS级异能者", "order": 9, "is_realm_boundary": True},
]

# =============================================
# 游戏转职体系
# =============================================

GAME_CLASS_LEVELS = [
    # 战士系
    {"name": "见习战士", "order": 1, "class_type": "warrior"},
    {"name": "初级战士", "order": 2, "class_type": "warrior"},
    {"name": "中级战士", "order": 3, "class_type": "warrior"},
    {"name": "高级战士", "order": 4, "class_type": "warrior"},
    {"name": "战士大师", "order": 5, "class_type": "warrior"},
    {"name": "战神", "order": 6, "class_type": "warrior"},
    # 法师系
    {"name": "魔法学徒", "order": 1, "class_type": "mage"},
    {"name": "初级法师", "order": 2, "class_type": "mage"},
    {"name": "中级法师", "order": 3, "class_type": "mage"},
    {"name": "高级法师", "order": 4, "class_type": "mage"},
    {"name": "大法师", "order": 5, "class_type": "mage"},
    {"name": "法神", "order": 6, "class_type": "mage"},
    # 刺客系
    {"name": "见习刺客", "order": 1, "class_type": "assassin"},
    {"name": "初级刺客", "order": 2, "class_type": "assassin"},
    {"name": "中级刺客", "order": 3, "class_type": "assassin"},
    {"name": "高级刺客", "order": 4, "class_type": "assassin"},
    {"name": "刺客大师", "order": 5, "class_type": "assassin"},
    {"name": "暗影之神", "order": 6, "class_type": "assassin"},
]


def get_power_system_template(system_type: str) -> list[dict]:
    """
    获取战力体系模板

    Args:
        system_type: "xianxia" | "urban" | "game" | "martial"

    Returns:
        战力等级列表
    """
    templates = {
        "xianxia": XIANXIA_CULTIVATION_REALMS,
        "urban": URBAN_ABILITY_LEVELS,
        "game": GAME_CLASS_LEVELS,
    }
    return templates.get(system_type, XIANXIA_CULTIVATION_REALMS)


def format_power_system_prompt(power_levels: list[dict]) -> str:
    """格式化战力体系为提示文本"""
    lines = ["## 战力体系\n"]

    # 按大境界分组
    current_realm = None
    for level in power_levels:
        name = level["name"]
        order = level["order"]
        is_boundary = level.get("is_realm_boundary", False)

        if is_boundary and current_realm is not None:
            lines.append("")  # 空行分隔大境界

        lines.append(f"{order}. {name}")

        if is_boundary:
            current_realm = name

    return "\n".join(lines)
