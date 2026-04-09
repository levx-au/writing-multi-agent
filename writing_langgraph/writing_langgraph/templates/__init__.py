"""网文模板系统"""

from writing_langgraph.templates.power_systems import (
    XIANXIA_CULTIVATION_REALMS,
    URBAN_ABILITY_LEVELS,
    GAME_CLASS_LEVELS,
    get_power_system_template,
    format_power_system_prompt,
)
from writing_langgraph.templates.tropes import (
    TropeTemplate,
    TUIFU_TROPE,
    LEVELING_TROPE,
    DABIAN_TROPE,
    FANREN_TROPE,
    SYSTEM_TROPE,
    TROPE_REGISTRY,
    get_trope,
    get_all_tropes,
    detect_tropes,
    format_trope_for_prompt,
)

__all__ = [
    # Power systems
    "XIANXIA_CULTIVATION_REALMS",
    "URBAN_ABILITY_LEVELS",
    "GAME_CLASS_LEVELS",
    "get_power_system_template",
    "format_power_system_prompt",
    # Tropes
    "TropeTemplate",
    "TUIFU_TROPE",
    "LEVELING_TROPE",
    "DABIAN_TROPE",
    "FANREN_TROPE",
    "SYSTEM_TROPE",
    "TROPE_REGISTRY",
    "get_trope",
    "get_all_tropes",
    "detect_tropes",
    "format_trope_for_prompt",
]
