"""把心理社会评估换算成「怎么跟这个人说话」。

为什么要有这一层：低血糖恐惧不是一件事，是两件事的交叉——这个人有多怕，以及他的身体
还会不会给他信号。同样一句「你的血糖在往下走」，对两个格子的人效果可以完全相反。

这里只做两件事：判定象限、把这个象限的沟通规则写成给模型的指令。措辞不给模型自由发挥，
因为「怎么说」本身就是这个设计的一部分。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

# 恐惧高低的分界：两个分量表的平均得分率达到一半即视为高恐惧。
FEAR_HIGH_PERCENT = 50
# Gold 计分法 >= 4 表示低血糖感知受损（1 = 总能察觉，7 = 从来察觉不到）。
AWARENESS_IMPAIRED_GOLD = 4

AwarenessLevel = Literal["normal", "impaired", "unknown"]
Quadrant = Literal[
    "high_fear_normal_awareness",
    "high_fear_impaired_awareness",
    "low_fear_normal_awareness",
    "low_fear_impaired_awareness",
    "unknown_awareness",
]

DOSAGE_BY_QUADRANT: dict[Quadrant, int] = {
    # 每周主动消息上限。高恐惧的人被频繁打扰会把「检查」外包给系统。
    "high_fear_normal_awareness": 3,
    "high_fear_impaired_awareness": 4,
    "low_fear_normal_awareness": 2,
    # 不害怕 + 察觉不到 = 临床上最容易被漏掉的高危组合，宁可多问一句。
    "low_fear_impaired_awareness": 5,
    "unknown_awareness": 3,
}

_GUIDANCE: dict[Quadrant, str] = {
    "high_fear_normal_awareness": (
        "对方对低血糖的恐惧偏高，但身体仍能给出信号。"
        "说话时先承认这份担心是有道理的，再把话题落回「他现在能做什么」，"
        "把判断权交回给他（例如「你自己的感觉是什么」）。"
        "不要用「别担心」「没事的」来否认恐惧，也不要反复强调风险大小；"
        "不要在他没有主动问的时候提起低血糖。"
    ),
    "high_fear_impaired_awareness": (
        "对方对低血糖恐惧偏高，而且察觉能力受损——他的身体不一定会在血糖下降时报警。"
        "这必须说得温和而明确：不是「你要小心」，而是「你身体的信号比别人弱，"
        "所以我会比你早一点说」。"
        "每次提到风险都必须同时给出一个具体动作和一次明确的回访时间，"
        "不能只留下威胁。不要假定「他能自己感觉到」，也不要把察觉受损说成他的过错。"
    ),
    "low_fear_normal_awareness": (
        "对方对低血糖的担心不高，身体也能正常报警。"
        "保持简洁，不必反复安抚，也不必堆叠风险提示；重点放在具体信息和他问的事上。"
        "不要因为「他不太怕」就替他放大危险，那会让他觉得被当成不懂事的人。"
    ),
    "low_fear_impaired_awareness": (
        "对方对低血糖的担心不高，但察觉能力受损——这是最容易被漏掉的一类："
        "他不会主动查，也不一定能感觉到。"
        "所以提示要具体、要早、要带动作，而且要说明为什么值得说一句"
        "（例如「你平时不太感觉得到，所以这次我提前说」）。"
        "不要因为他语气轻松就判断风险低；也不要暗示他「不够重视」。"
    ),
    "unknown_awareness": (
        "还没有做过低血糖感知评估，所以不能假定对方能或不能感觉到低血糖，"
        "也不能假定他有多怕。谨慎的默认做法：给区间不给结论，给动作不给威胁，"
        "并在合适的时候邀请他聊聊自己的感受，而不是替他判断。"
    ),
}


@dataclass(frozen=True)
class PsychosocialProfile:
    """评估结果的只读视图；不做任何写入，方便在提示词构造处直接传。"""

    fear_behavior_percent: int
    fear_worry_percent: int
    gold_score: int | None

    def __post_init__(self) -> None:
        for name, value in (
            ("fear_behavior_percent", self.fear_behavior_percent),
            ("fear_worry_percent", self.fear_worry_percent),
        ):
            if not 0 <= value <= 100:
                raise ValueError(f"{name} 必须在 0–100 之间，收到 {value}")
        if self.gold_score is not None and not 1 <= self.gold_score <= 7:
            raise ValueError(f"gold_score 必须在 1–7 之间，收到 {self.gold_score}")

    @property
    def fear_percent(self) -> int:
        return round((self.fear_behavior_percent + self.fear_worry_percent) / 2)

    @property
    def fear_high(self) -> bool:
        return self.fear_percent >= FEAR_HIGH_PERCENT

    @property
    def awareness(self) -> AwarenessLevel:
        if self.gold_score is None:
            return "unknown"
        return "impaired" if self.gold_score >= AWARENESS_IMPAIRED_GOLD else "normal"

    @property
    def quadrant(self) -> Quadrant:
        awareness = self.awareness
        if awareness == "unknown":
            return "unknown_awareness"
        if self.fear_high and awareness == "normal":
            return "high_fear_normal_awareness"
        if self.fear_high and awareness == "impaired":
            return "high_fear_impaired_awareness"
        if awareness == "normal":
            return "low_fear_normal_awareness"
        return "low_fear_impaired_awareness"

    @property
    def weekly_contact_limit(self) -> int:
        return DOSAGE_BY_QUADRANT[self.quadrant]


def render_guidance(profile: PsychosocialProfile | None) -> str:
    """把象限写成给模型的沟通指令；没有评估时返回空串，调用方据此不加这一段。"""

    if profile is None:
        return ""
    return (
        f"[沟通方式参考]\n{_GUIDANCE[profile.quadrant]}\n"
        f"每周主动联系不超过 {profile.weekly_contact_limit} 次；"
        "对方没有回应时不要追问，也不要把沉默解释成病情变化。"
        "评估分数是内部参考，不要向对方复述分数或量表名称，也不要据此给他贴标签。"
    )
