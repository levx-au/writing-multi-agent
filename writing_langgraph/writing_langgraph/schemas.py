"""结构化响应 schema — 替代脆弱的 regex 解析"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional
from typing_extensions import Literal


@dataclass
class CriticResponse:
    """Critic 节点的标准化响应"""
    # 双层反馈文本
    arch_feedback: str = ""
    prose_feedback: str = ""

    # 路由动作
    arch_action: Literal["revise", "keep"] = "keep"
    prose_action: Literal["rewrite", "keep"] = "keep"

    # 评分
    score: float = 0.0

    # 解析状态（用于调试）
    parse_error: Optional[str] = None

    @classmethod
    def from_json(cls, raw: str) -> "CriticResponse":
        """从 JSON 字符串解析（支持纯 JSON 或 markdown 代码块）"""
        import json, re
        import logging

        # 先尝试直接解析（纯 JSON 格式）
        try:
            data = json.loads(raw.strip())
            score_val = data.get("score", 0.0)
            # 确保 score 是数字类型
            if isinstance(score_val, str):
                score_val = float(score_val)
            logging.warning(f"[CriticResponse.from_json] 直接JSON解析成功: score={score_val}, arch_action={data.get('arch_action')}, prose_action={data.get('prose_action')}")
            return cls(
                arch_feedback=data.get("arch_feedback", ""),
                prose_feedback=data.get("prose_feedback", ""),
                arch_action=data.get("arch_action", "keep"),
                prose_action=data.get("prose_action", "keep"),
                score=float(score_val) if score_val is not None else 0.0,
            )
        except (json.JSONDecodeError, ValueError, KeyError, TypeError):
            pass

        # 尝试从 ```json ... ``` 或 ``` ... ``` 代码块中提取
        try:
            m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", raw, re.I)
            if m:
                json_str = m.group(1).strip()
                data = json.loads(json_str)
                score_val = data.get("score", 0.0)
                if isinstance(score_val, str):
                    score_val = float(score_val)
                logging.warning(f"[CriticResponse.from_json] 代码块JSON解析成功: score={score_val}")
                return cls(
                    arch_feedback=data.get("arch_feedback", ""),
                    prose_feedback=data.get("prose_feedback", ""),
                    arch_action=data.get("arch_action", "keep"),
                    prose_action=data.get("prose_action", "keep"),
                    score=float(score_val) if score_val is not None else 0.0,
                )
            else:
                logging.warning(f"[CriticResponse.from_json] 未找到代码块，降级到markdown fallback")
        except (json.JSONDecodeError, ValueError, KeyError, TypeError) as e:
            logging.warning(f"[CriticResponse.from_json] 代码块JSON解析异常: {e}，降级到markdown fallback")

        # 降级：Markdown 格式解析
        logging.warning(f"[CriticResponse.from_json] 降级到markdown fallback")
        return cls._from_markdown_fallback(raw)

    @classmethod
    def _from_markdown_fallback(cls, text: str) -> "CriticResponse":
        """Markdown 格式 fallback（兼容旧格式）"""
        import re

        arch, prose = "", ""
        aa, pa = "keep", "keep"
        score = 0.0

        # 解析架构层 / 文字层
        arch_match = re.search(
            r"(?:###|##|#)\s*架构[层-]?[^\n]*\n([\s\S]*?)(?=(?:###|##|#)\s*文字)",
            text, re.I
        )
        if arch_match:
            arch = arch_match.group(1).strip()

        prose_match = re.search(
            r"(?:###|##|#)\s*文字[层-]?[^\n]*\n([\s\S]*?)(?=(?:###|##|#)\s*路由)",
            text, re.I
        )
        if prose_match:
            prose = prose_match.group(1).strip()

        # 解析路由
        am = re.search(r"ARCH_ACTION:\s*(revise|keep)\b", text, re.I)
        pm = re.search(r"PROSE_ACTION:\s*(rewrite|keep)\b", text, re.I)
        if am:
            aa = am.group(1).lower()
        if pm:
            pa = pm.group(1).lower()

        # 解析评分（多重 fallback）
        score = cls._parse_score_fallback(text)

        return cls(
            arch_feedback=arch,
            prose_feedback=prose,
            arch_action=aa,
            prose_action=pa,
            score=score,
            parse_error="used_markdown_fallback",
        )

    @staticmethod
    def _parse_score_fallback(text: str) -> float:
        """评分解析 — 多重 fallback"""
        import re

        # 标准格式
        m = re.search(r"SCORE[：:]\s*([0-9]+(?:\.[0-9]+)?)", text, re.I)
        if m:
            return max(0.0, min(10.0, float(m.group(1))))

        # N/10 格式
        for pattern in [
            r"\b([0-9]+(?:\.[0-9]+)?)\s*/\s*10\b",
        ]:
            ms = re.findall(pattern, text)
            if ms:
                return max(0.0, min(10.0, float(ms[-1])))

        # 评分 8.5 格式
        m = re.search(r"评分[：:\s]*([0-9]+(?:\.[0-9]+)?)", text, re.I)
        if m:
            return max(0.0, min(10.0, float(m.group(1))))

        return 0.0

    def to_state_updates(self) -> dict:
        """转换为 WritingState 更新字典"""
        return {
            "feedback": f"{self.arch_feedback}\n\n{self.prose_feedback}",
            "arch_feedback": self.arch_feedback,
            "prose_feedback": self.prose_feedback,
            "arch_action": self.arch_action,
            "prose_action": self.prose_action,
            "score": self.score,
        }


@dataclass
class IterationContext:
    """
    迭代控制上下文（不污染 State）。

    作为节点函数的局部变量传递，不写入 LangGraph State。
    """
    iteration: int = 0
    max_iterations: int = 4
    score_pass: float = 8.0
    consecutive_keep: int = 0
    force_write: bool = False

    def tick(self) -> None:
        self.iteration += 1

    def should_stop(self) -> bool:
        return self.iteration >= self.max_iterations or self.score >= self.score_pass

    @property
    def score(self) -> float:
        """由外部注入，通过 check() 方法更新"""
        return self._score

    def check(self, score: float) -> bool:
        self._score = score
        return score >= self.score_pass

    def record_keep(self) -> int:
        self.consecutive_keep += 1
        return self.consecutive_keep

    def reset_keep(self) -> None:
        self.consecutive_keep = 0

    def request_force_write(self) -> None:
        self.force_write = True

    def clear_force_write(self) -> None:
        self.force_write = False
