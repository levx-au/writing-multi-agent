"""网文套路模板"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TropeTemplate:
    """套路模板"""
    trope_type: str
    name: str
    description: str
    trigger_conditions: list[str]
    beats: list[str]  # 关键节拍
    expected_climax: str  # 预期爽点
    anti_tropes: list[str]  # 反套路方向


# =============================================
# 退婚流
# =============================================
TUIFU_TROPE = TropeTemplate(
    trope_type="退婚流",
    name="莫欺少年穷",
    description="主角被未婚妻或其家族退婚，受尽屈辱，随后逆袭打脸",
    trigger_conditions=[
        "主角有婚约在身",
        "未婚妻家族势力强大",
        "主角被视为废物/没有修炼天赋",
    ],
    beats=[
        "1. 展示婚约关系和未婚妻的优秀",
        "2. 退婚场景：羞辱、嘲讽、扔休书",
        "3. 主角隐忍或霸气回应",
        "4. 意外获得金手指/传承",
        "5. 实力快速提升",
        "6. 再次相遇：未婚妻/家族震惊",
        "7. 主角霸气打脸/悔不当初",
        "8. 解除婚约或对方倒追",
    ],
    expected_climax="未婚妻家族发现主角已是高不可攀的存在，跪求复合",
    anti_tropes=[
        "主角不计较，大度原谅",
        "未婚妻其实是好人，被家族胁迫",
        "主角直接无视，不给眼神",
    ],
)


# =============================================
# 升级流
# =============================================
LEVELING_TROPE = TropeTemplate(
    trope_type="升级流",
    name="步步高升",
    description="主角通过各种方式不断提升实力，从弱者到强者",
    trigger_conditions=[
        "存在明确的实力等级体系",
        "有足够的资源和副本支撑升级",
        "主角有强烈的升级动机",
    ],
    beats=[
        "1. 展示当前实力和所处等级",
        "2. 遇到瓶颈或困境",
        "3. 发现突破契机（秘境/丹药/感悟）",
        "4. 突破成功，实力大涨",
        "5. 新副本/新对手",
        "6. 循环升级",
    ],
    expected_climax="突破大境界时的异象和各方反应",
    anti_tropes=[
        "主角天赋太好，不需要努力",
        "升级太容易，失去紧张感",
    ],
)


# =============================================
# 打脸流
# =============================================
DABIAN_TROPE = TropeTemplate(
    trope_type="打脸流",
    name="当场报应",
    description="嘲讽主角的人很快被打脸，爽快直接",
    trigger_conditions=[
        "有明确的反派或嘲讽角色",
        "主角有隐藏实力或金手指",
        "有观众/第三方见证",
    ],
    beats=[
        "1. 反派嘲讽、看不起主角",
        "2. 主角淡定或微笑回应",
        "3. 战斗开始或结果揭晓",
        "4. 反派被碾压/秒杀",
        "5. 围观者震惊",
        "6. 反派后悔/求饶",
    ],
    expected_climax="打脸过程要详细，让读者爽够",
    anti_tropes=[
        "主角打脸后说教",
        "反派直接认输，没有挣扎",
    ],
)


# =============================================
# 凡人流
# =============================================
FANREN_TROPE = TropeTemplate(
    trope_type="凡人流",
    name="小人物奋斗史",
    description="没有逆天天赋，靠计谋、资源、机缘一步步崛起",
    trigger_conditions=[
        "主角天赋一般或低下",
        "有复杂的派系斗争",
        "资源和机缘可以靠努力获得",
    ],
    beats=[
        "1. 展示主角的劣势处境",
        "2. 面对强敌，选择智取",
        "3. 利用情报、环境、人脉",
        "4. 关键战斗险胜",
        "5. 获得资源，稳固基础",
        "6. 继续积累，准备下次突破",
    ],
    expected_climax="以弱胜强的战斗，智谋大于蛮力",
    anti_tropes=[
        "主角突然开挂",
        "敌人集体降智",
    ],
)


# =============================================
# 系统流
# =============================================
SYSTEM_TROPE = TropeTemplate(
    trope_type="系统流",
    name="任务奖励爽歪歪",
    description="主角获得游戏化系统，做任务得奖励",
    trigger_conditions=[
        "主角获得系统",
        "有任务/成就机制",
        "有商店/抽奖等奖励",
    ],
    beats=[
        "1. 获得系统，介绍功能",
        "2. 首个新手任务",
        "3. 完成任务，获得奖励",
        "4. 实力提升，震惊旁人",
        "5. 连续任务，滚雪球",
        "6. 系统升级，解锁新功能",
    ],
    expected_climax="抽到稀有奖励或触发隐藏成就",
    anti_tropes=[
        "系统太万能，没有挑战",
        "系统话太多，喧宾夺主",
    ],
)


# =============================================
# 套路注册表
# =============================================
TROPE_REGISTRY: dict[str, TropeTemplate] = {
    "退婚流": TUIFU_TROPE,
    "升级流": LEVELING_TROPE,
    "打脸流": DABIAN_TROPE,
    "凡人流": FANREN_TROPE,
    "系统流": SYSTEM_TROPE,
}


def get_trope(name: str) -> TropeTemplate | None:
    """获取指定套路模板"""
    return TROPE_REGISTRY.get(name)


def get_all_tropes() -> list[TropeTemplate]:
    """获取所有套路模板"""
    return list(TROPE_REGISTRY.values())


def detect_tropes(user_request: str) -> list[str]:
    """
    从用户需求中检测可能适用的套路

    Returns:
        匹配的套路名称列表
    """
    detected = []
    request_lower = user_request.lower()

    # 关键词匹配
    keywords_map = {
        "退婚": "退婚流",
        "休妻": "退婚流",
        "废物": "退婚流",
        "未婚妻": "退婚流",
        "升级": "升级流",
        "修炼": "升级流",
        "境界": "升级流",
        "打脸": "打脸流",
        "嘲讽": "打脸流",
        "凡人流": "凡人流",
        "普通人": "凡人流",
        "系统": "系统流",
        "任务": "系统流",
    }

    for keyword, trope in keywords_map.items():
        if keyword in request_lower and trope not in detected:
            detected.append(trope)

    return detected


def format_trope_for_prompt(trope: TropeTemplate) -> str:
    """格式化套路为提示文本"""
    lines = [
        f"## 套路：{trope.name}",
        f"类型：{trope.trope_type}",
        f"简介：{trope.description}",
        "",
        "### 触发条件",
    ]

    for condition in trope.trigger_conditions:
        lines.append(f"- {condition}")

    lines.extend(["", "### 关键节拍"])
    for beat in trope.beats:
        lines.append(f"- {beat}")

    lines.extend([
        "",
        f"### 预期爽点",
        trope.expected_climax,
        "",
        "### 反套路方向",
    ])

    for anti in trope.anti_tropes:
        lines.append(f"- {anti}")

    return "\n".join(lines)
