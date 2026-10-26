"""把对话里识别出的「这一餐」「这次用药」写进患者自己的记录。

设计约束（和产品口径一致）：
- 只记录患者说过或照片里能看清的事实，不推断、不补剂量；
- 剂量缺失时工具调用会失败，模型必须回头问患者（这就是「询问补全」的实现）；
- 时间是真实发生时间，不是提交时间：晚上 16 点补记早上 10 点的药，记的是 10 点。
"""

from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal
from uuid import UUID

from langchain.tools import ToolRuntime, tool
from langchain_core.tools import BaseTool
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from antang_api.agents.runtime import AgentContext
from antang_api.database import session_factory as default_session_factory
from antang_api.models import (
    AgentRun,
    MealLog,
    MedicationLog,
    Message,
    MessageRole,
)

RECORD_MEAL_TOOL_NAME = "record_meal"
RECORD_MEDICATION_TOOL_NAME = "record_medication"

# 补记允许往前 30 天；未来时间最多容忍 2 分钟（手机时钟误差）。
BACKFILL_LIMIT = timedelta(days=30)
FUTURE_TOLERANCE = timedelta(minutes=2)


def _check_event_time(value: datetime, now: datetime) -> datetime:
    """时间是真实发生时间：不能是未来，也不能久到记不清。"""

    if value.tzinfo is None:
        raise ValueError("时间要带时区，例如 2026-10-24T10:00:00+08:00")
    if value > now + FUTURE_TOLERANCE:
        raise ValueError("这个时间还没到，确认一下是不是记错了")
    if value < now - BACKFILL_LIMIT:
        raise ValueError("只支持补记最近 30 天内的记录")
    return value.astimezone(UTC)


MealType = Annotated[
    Literal["breakfast", "lunch", "dinner", "snack"],
    Field(description="早餐 / 午餐 / 晚餐 / 加餐；不确定就按现在的时间推断。"),
]
EatenAt = Annotated[
    datetime,
    Field(
        description=(
            "这餐真实发生的时刻，带时区。用户说「刚才」就用当前时间；"
            "补记早上的一餐要写早上那个时刻，不是现在。"
        )
    ),
]
MealDescription = Annotated[
    str,
    Field(
        max_length=200,
        description="吃了什么，用患者自己的说法，例如「一碗米饭、青菜、鸡胸」。",
    ),
]
MealCarbs = Annotated[
    int | None,
    Field(
        ge=0,
        le=400,
        description=(
            "碳水克数估计，可选。患者没说、照片里也看不出就不要填，不要凭习惯猜。"
        ),
    ),
]
PortionHint = Annotated[
    str | None,
    Field(max_length=40, description="份量描述，例如「一碗」「半碗」；没有就说不要填。"),
]

MedicationName = Annotated[
    str,
    Field(min_length=1, max_length=64, description="药名或胰岛素名，照患者说的写。"),
]
DoseText = Annotated[
    str,
    Field(
        min_length=1,
        max_length=64,
        description=(
            "患者说出的剂量原文，例如「6 单位」「一片」；"
            "患者没说剂量就不要调用这个工具，先问清楚——系统不会替你算剂量。"
        ),
    ),
]
TakenAt = Annotated[
    datetime,
    Field(
        description=(
            "真实用药时刻，带时区。下午才想起来早上 10 点吃的药，写早上 10 点。"
        )
    ),
]
MedicationKind = Annotated[
    Literal["oral", "insulin", "other"],
    Field(description="胰岛素 / 口服药 / 其它。"),
]
MedicationNote = Annotated[
    str | None,
    Field(max_length=200, description="患者原话片段或当时情境，可选。"),
]


class MealRequest(BaseModel):
    """患者刚吃的一餐。"""

    model_config = ConfigDict(extra="forbid")

    meal_type: MealType
    eaten_at: EatenAt
    description: MealDescription = ""
    carbs_grams: MealCarbs = None
    portion_hint: PortionHint = None


class MedicationRequest(BaseModel):
    """患者打的一次胰岛素或吃的一次药。"""

    model_config = ConfigDict(extra="forbid")

    name: MedicationName
    dose_text: DoseText
    taken_at: TakenAt
    kind: MedicationKind = "other"
    note: MedicationNote = None


async def _trigger_message_id(
    session: AsyncSession,
    runtime: ToolRuntime[AgentContext],
) -> UUID | None:
    """把记录回溯到触发它的那条用户消息。"""

    run = await session.get(AgentRun, runtime.context.run_id)
    if run is None or run.user_id != runtime.context.user_id:
        raise RuntimeError("记录必须由当前用户消息的 Core Agent 调用")
    if run.trigger_message_id is None:
        return None
    message = await session.get(Message, run.trigger_message_id)
    if message is None or message.role != MessageRole.USER:
        return None
    return message.id


def build_record_tools(
    sessions: async_sessionmaker[AsyncSession] = default_session_factory,
) -> tuple[BaseTool, BaseTool]:
    """创建「记这一餐」「记这次用药」两个工具。"""

    # 参数用扁平 schema（args_schema=...），不是「一个 request 对象里套所有字段」：
    # 线上真的踩过——模型把字段平铺着传过来，框架报 "request: Field required"，
    # 工具没执行、模型却回了一句「已经帮你记下来了」。扁平之后两种写法都只是字段，
    # 少一层嵌套就少一次「参数对不上」的失败。
    @tool(RECORD_MEAL_TOOL_NAME)
    async def record_meal(
        runtime: ToolRuntime[AgentContext],
        meal_type: MealType,
        eaten_at: EatenAt,
        description: MealDescription = "",
        carbs_grams: MealCarbs = None,
        portion_hint: PortionHint = None,
    ) -> dict[str, object]:
        """把患者刚吃的一餐写进饮食记录。

        只在患者明确说了这一餐吃了什么、或发来照片并且你看清了食物时调用。
        缺少份量或碳水时可以先记下来（份量与碳水都可以空），但不要把猜测写成事实。
        记完用一句话告诉患者记了什么、记到了几点，然后继续原来的话题。
        只有这个工具返回 recorded=true 才能说「已经记下来了」。
        """

        request = MealRequest(
            meal_type=meal_type,
            eaten_at=eaten_at,
            description=description,
            carbs_grams=carbs_grams,
            portion_hint=portion_hint,
        )
        now = datetime.now(UTC)
        eaten_at = _check_event_time(request.eaten_at, now)

        description = request.description.strip()
        if request.portion_hint:
            description = f"{description}（{request.portion_hint.strip()}）".strip("（）")

        async with sessions() as session:
            await _trigger_message_id(session, runtime)
            log = MealLog(
                user_id=runtime.context.user_id,
                eaten_at=eaten_at,
                meal_type=request.meal_type,
                description=description,
                carbs_grams=request.carbs_grams,
            )
            session.add(log)
            await session.commit()
            return {
                "recorded": True,
                "meal_type": log.meal_type,
                "eaten_at": log.eaten_at.isoformat(),
                "description": log.description,
                "carbs_grams": log.carbs_grams,
            }

    @tool(RECORD_MEDICATION_TOOL_NAME)
    async def record_medication(
        runtime: ToolRuntime[AgentContext],
        name: MedicationName,
        dose_text: DoseText,
        taken_at: TakenAt,
        kind: MedicationKind = "other",
        note: MedicationNote = None,
    ) -> dict[str, object]:
        """把患者这次用药写进用药记录（只记录，不给任何剂量建议）。

        剂量必须由患者说出或照片里能看清；没有剂量就先问，不要调用这个工具。
        患者自己调了量也照原样记下来——这条记录之后可以给医生看。
        只有这个工具返回 recorded=true 才能说「已经记下来了」。
        """

        request = MedicationRequest(
            name=name,
            dose_text=dose_text,
            taken_at=taken_at,
            kind=kind,
            note=note,
        )
        now = datetime.now(UTC)
        taken_at = _check_event_time(request.taken_at, now)

        async with sessions() as session:
            await _trigger_message_id(session, runtime)
            log = MedicationLog(
                user_id=runtime.context.user_id,
                taken_at=taken_at,
                name=request.name.strip(),
                dose_text=request.dose_text.strip(),
                kind=request.kind,
                note=request.note,
            )
            session.add(log)
            await session.commit()
            return {
                "recorded": True,
                "name": log.name,
                "dose_text": log.dose_text,
                "kind": log.kind,
                "taken_at": log.taken_at.isoformat(),
            }

    return record_meal, record_medication
