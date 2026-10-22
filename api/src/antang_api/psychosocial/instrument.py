"""沟通方式自评的题库，由服务端下发。

以前题目写死在 App 里（`apps/mobile/src/psychosocial/PsychosocialSection.tsx`），
后果是换一次题库就得重新打包、每个患者重新装一次。HFS-II 授权到位那天要换的正是
题目与计分，所以题目必须挪到服务端：只有后端发版，装过的包不用动。

题库只提供「问什么、怎么选、说明什么」，不提供计分细则：App 按选项最大值算百分比，
后端仍只存 `fear_behavior_percent` / `fear_worry_percent` / `gold_score`，与
`api/src/antang_api/psychosocial/store.py` 的接口一致。
"""

from dataclasses import dataclass
from typing import Literal

QuestionKind = Literal["behavior", "worry"]


@dataclass(frozen=True)
class InstrumentOption:
    value: int
    label: str


@dataclass(frozen=True)
class InstrumentQuestion:
    id: str
    kind: QuestionKind
    text: str


@dataclass(frozen=True)
class Instrument:
    """一份可以整份替换的题库。"""

    id: str
    title: str
    instructions: str
    disclaimer: str
    options: tuple[InstrumentOption, ...]
    questions: tuple[InstrumentQuestion, ...]
    gold_label: str
    gold_hint: str
    gold_options: tuple[InstrumentOption, ...]


BEHAVIOR_SCALE = (
    InstrumentOption(value=0, label="从不"),
    InstrumentOption(value=1, label="很少"),
    InstrumentOption(value=2, label="有时"),
    InstrumentOption(value=3, label="经常"),
    InstrumentOption(value=4, label="几乎每天"),
)

GOLD_SCALE = tuple(InstrumentOption(value=value, label=str(value)) for value in range(1, 8))

SELF_REPORT_INSTRUMENT = Instrument(
    id="antang-behavior-v1",
    title="沟通方式自评",
    instructions="六个问题，约一分钟。选最接近最近一个月实际情况的一项。",
    disclaimer="这几道题是我们自己写的，不是标准化量表，只用来决定沟通方式，不作为诊断依据。",
    options=BEHAVIOR_SCALE,
    questions=(
        InstrumentQuestion(
            id="repeat-test",
            kind="behavior",
            text="过去一个月，我因为担心低血糖而反复测血糖，即使刚测过。",
        ),
        InstrumentQuestion(
            id="skip-exercise",
            kind="behavior",
            text="过去一个月，我因为怕低血糖而减少或取消了原本要做的运动。",
        ),
        InstrumentQuestion(
            id="bedtime-snack",
            kind="behavior",
            text="过去一个月，我会在睡前额外吃东西，即使当时血糖正常。",
        ),
        InstrumentQuestion(
            id="night-worry",
            kind="worry",
            text="过去一个月，我担心夜里睡着以后发生低血糖。",
        ),
        InstrumentQuestion(
            id="alone-worry",
            kind="worry",
            text="过去一个月，我担心一个人时低血糖会没人帮忙。",
        ),
        InstrumentQuestion(
            id="anxious-thought",
            kind="worry",
            text="过去一个月，一想到可能低血糖，我就会紧张或心慌。",
        ),
    ),
    gold_label="你平时能感觉到低血糖开始了吗？",
    gold_hint="1 = 总能感觉到，7 = 完全感觉不到",
    gold_options=GOLD_SCALE,
)


def current_instrument() -> Instrument:
    """App 该拿到的那份题库。

    HFS-II 授权到位后，把 `SELF_REPORT_INSTRUMENT` 换成新的常量、把 id 改成对应的
    量表名即可；接口与 App 都不用动。
    """

    return SELF_REPORT_INSTRUMENT
