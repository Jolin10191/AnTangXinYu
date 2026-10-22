"""低血糖信念的重构问句。

这些是**提问素材**，不是结论，也不是治疗方案。用处只有两个：
- 让对话有具体可问的句子，而不是笼统地「你要放松」；
- 让替代想法落在生活事实上，而不是安慰话。

三条边界（写在这里是为了避免以后被当成话术库扩张）：
- 一次只问一个问题，不连发；
- 用户明确说不想谈就停，不追着问；
- 这套素材未经过临床签字，分级暴露（强度、时长、血糖下限）不在其中。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReframeSet:
    """针对一条信念的提问序列与一个更平衡的想法。"""

    opening: str
    followup: str
    balanced: str


BELIEF_REFRAMES: dict[str, ReframeSet] = {
    "hypo_causes_death": ReframeSet(
        opening="你听说或经历的那次，当时身边有人吗？",
        followup="血糖往下掉的时候，你身上一般会先出现什么感觉？",
        balanced="低血糖是要认真对待的事，但它通常先给信号；你手边有葡萄糖片和加餐可用。",
    ),
    "hypo_causes_coma": ReframeSet(
        opening="你说的「没人发现」，具体是哪种时候——夜里一个人睡，还是白天独处？",
        followup="真到了那一步，你身边有什么是能帮上忙的？",
        balanced="夜间严重低血糖的风险是真实的，但它比「随时会昏迷」要窄；我们能做的是把夜里那一段单独照看。",
    ),
    "hypo_always_unpredictable": ReframeSet(
        opening="最近这几次里，有没有哪一次你是先感觉到什么、后来才测出偏低的？",
        followup="那一次之前，你做了什么和平常不一样的事吗？",
        balanced="不是每次都能预判，但有些信号重复出现过；把重复的那几个找出来，比全信或全否都靠得住。",
    ),
    "hypo_means_failure": ReframeSet(
        opening="如果同样这个数值出在别的病友身上，你会觉得是他没管好吗？",
        followup="那天你的睡眠、吃饭时间，和平常比有什么不同？",
        balanced="血糖受睡眠、激素、吸收速度影响，一天里有很多不由你决定的变量。",
    ),
    "hypo_needs_constant_checking": ReframeSet(
        opening="有没有哪一次你没测，结果也没出事？",
        followup="测完之后那种踏实，一般能维持多久？",
        balanced="监测是手段，不是护身符；反复测带来的安心通常很短，而且会一点点变短。",
    ),
    "hypo_avoid_exercise": ReframeSet(
        opening="你上次运动前后，血糖实际是怎么走的？",
        followup="那次运动持续了多久、强度大概怎么样？",
        balanced="运动会增加低血糖的可能，但它可以被加餐、强度和时机管理，不是非黑即白。",
    ),
    "hypo_hide_from_others": ReframeSet(
        opening="如果身边的人知道了，你最担心他们会怎么做？",
        followup="有没有哪个人知道了以后，反应比你预想的好？",
        balanced="让人知道，通常换来的是更快的帮助，而不是被看轻。",
    ),
    "hypo_carbs_unlimited": ReframeSet(
        opening="那次加餐之后，血糖后来走到哪儿了？",
        followup="当时你吃了多少，过了多久复测的？",
        balanced="补 15 克快速碳水、等 15 分钟再测，比「多吃一点更保险」更稳。",
    ),
}


def reframe_for(belief_code: str) -> ReframeSet | None:
    """取出某条信念对应的提问素材；不认识的编码返回 None。"""

    return BELIEF_REFRAMES.get(belief_code)


def render_reframe_hint(belief_code: str, label: str) -> str:
    """把一条信念的提问素材渲染成提示词片段；没有素材时返回空串。"""

    entry = reframe_for(belief_code)
    if entry is None:
        return ""

    return "\n".join(
        [
            f"[可以试着这样问] 用户反复提到「{label}」。",
            f"先只问一句：{entry.opening}",
            f"如果用户愿意往下说，再问：{entry.followup}",
            f"如果用户接住了，可以给一个更平衡的说法：{entry.balanced}",
            "约束：一次只问一个问题；用户说不想谈就停，不要追问，也不要说「你这是在灾难化」。",
        ]
    )
