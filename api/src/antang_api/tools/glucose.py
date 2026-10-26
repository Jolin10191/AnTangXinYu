"""血糖读数的只读工具。

患者自己在 App 里记的读数已经每轮放进提示词（近 7 天摘要 + 最近 5 条），
这个工具是给「想再往前看一点」用的：模型可以按天数和条数要明细。
不写库、不判读——判读留给对话本身。
"""

from datetime import UTC, date, datetime, timedelta
from typing import Annotated, Literal

from langchain.tools import ToolRuntime, tool
from langchain_core.tools import BaseTool
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from antang_api.agents.runtime import AgentContext
from antang_api.database import session_factory as default_session_factory
from antang_api.health_profile.glucose import (
    GLUCOSE_CONTEXT_LABELS,
    GLUCOSE_DEVICE_LABELS,
    list_glucose_readings,
    record_glucose_reading,
    record_glucose_report as save_glucose_report,
    summarize_glucose,
    to_mmol,
)

READ_GLUCOSE_TOOL_NAME = "read_glucose_readings"
RECORD_GLUCOSE_TOOL_NAME = "record_glucose_readings"
RECORD_GLUCOSE_REPORT_TOOL_NAME = "record_glucose_report"

# 患者发来的报告里能读出的一条读数：化验单一般几个点，CGM 报告最多一天几十个点。
MAX_REPORT_READINGS = 120
# 报告可能是补传的，但再久以前的数字意义不大，也容易和别的记录打架。
OLDEST_REPORT_DAYS = 400

GlucoseReportSource = Literal["cgm", "lab", "fingerstick", "manual"]
GlucoseReportDevice = Literal["roche", "abbott", "sannuo", "other"]
GlucoseReportContext = Literal[
    "fasting", "pre_meal", "post_meal", "bedtime", "night", "other"
]



class GlucoseReadRequest(BaseModel):
    """要看多长窗口、多少条患者自己记的血糖。"""

    model_config = ConfigDict(extra="forbid")

    days: Annotated[
        int,
        Field(
            ge=1,
            le=90,
            description="往前看多少天，默认 7 天；患者说「这两个月」时才用大值。",
        ),
    ] = 7
    limit: Annotated[
        int,
        Field(ge=1, le=50, description="最多返回多少条明细，默认 10 条。"),
    ] = 10


def build_glucose_read_tool(
    sessions: async_sessionmaker[AsyncSession] = default_session_factory,
) -> BaseTool:
    """创建读取血糖明细的工具。"""

    @tool(READ_GLUCOSE_TOOL_NAME)
    async def read_glucose_readings(
        request: GlucoseReadRequest,
        runtime: ToolRuntime[AgentContext],
    ) -> dict[str, object]:
        """读取患者自己在 App 里记的血糖读数。

        当患者问到具体的数字（「我上周那次多少」「这两天是不是有点飘」），
        而上下文里的摘要不够时调用。数值单位是 mmol/L。
        这些读数由患者手动录入，可能漏记，不是连续监测；不要说成 CGM 曲线。
        """

        async with sessions() as session:
            summary = await summarize_glucose(
                session,
                user_id=runtime.context.user_id,
                days=request.days,
            )
            readings = await list_glucose_readings(
                session,
                user_id=runtime.context.user_id,
                days=request.days,
                limit=request.limit,
            )

        if summary["count"] == 0:
            return {
                "days": request.days,
                "count": 0,
                "note": "这段时间患者没有记血糖。",
            }

        average = summary["average_mg_dl"]
        minimum = summary["minimum_mg_dl"]
        maximum = summary["maximum_mg_dl"]
        return {
            "days": request.days,
            "count": summary["count"],
            "average_mmol": None if average is None else to_mmol(round(average)),
            "minimum_mmol": None if minimum is None else to_mmol(minimum),
            "maximum_mmol": None if maximum is None else to_mmol(maximum),
            "below_70_count": summary["below_70_count"],
            "readings": [
                {
                    "measured_at": reading.measured_at.isoformat(),
                    "value_mmol": to_mmol(reading.value_mg_dl),
                    "context": GLUCOSE_CONTEXT_LABELS.get(
                        reading.context, reading.context
                    ),
                    "source": reading.source,
                    "device": GLUCOSE_DEVICE_LABELS.get(reading.source_device)
                    or None,
                    "note": reading.note,
                }
                for reading in readings
            ],
            "note": "患者自己记的，可能漏记，不是连续监测。",
        }

    return read_glucose_readings


class GlucosePoint(BaseModel):
    """报告里读到的一条血糖：什么时候、多少、什么场景。"""

    model_config = ConfigDict(extra="forbid")

    measured_at: Annotated[
        str,
        Field(
            description=(
                "测量时间，必须带时区，例如 2026-10-24T07:10:00+08:00。"
                "报告只写了日期（如 10-20）时用当天早上 07:00 并说明是日期精度。"
            )
        ),
    ]
    value_mmol: Annotated[
        float,
        Field(
            ge=1.0,
            le=40.0,
            description="血糖值，单位 mmol/L。报告写的是 mg/dL 时先除以 18。",
        ),
    ]
    context: Annotated[
        GlucoseReportContext,
        Field(
            default="other",
            description="空腹/餐前/餐后/睡前/夜间，报告没写就用 other。",
        ),
    ] = "other"
    note: Annotated[
        str | None,
        Field(default=None, description="一条备注，例如「报告日均值」「化验单」"),
    ] = None


def build_glucose_write_tool(
    sessions: async_sessionmaker[AsyncSession] = default_session_factory,
) -> BaseTool:
    """创建把报告里的血糖写进记录的工具。"""

    @tool(RECORD_GLUCOSE_TOOL_NAME)
    async def record_glucose_readings(
        runtime: ToolRuntime[AgentContext],
        readings: Annotated[
            list[GlucosePoint],
            Field(description="从报告或化验单里读出来的每一条血糖，一次全给。"),
        ],
        source: Annotated[
            GlucoseReportSource,
            Field(
                description=(
                    "这批数字从哪来：传感器/CGM 报告用 cgm，医院化验单用 lab，"
                    "患者念自己血糖仪的数字用 fingerstick。"
                )
            ),
        ] = "cgm",
        device: Annotated[
            GlucoseReportDevice | None,
            Field(default=None, description="只有指尖血才需要填，其它来源忽略。"),
        ] = None,
    ) -> dict[str, object]:
        """把患者发来的报告里的血糖数值写进血糖记录。

        患者发 CGM 报告/化验单/血糖记录截图，或者念出一串数字，并且希望「记下来、
        以后能看」的时候调用。只写库、不判读：解释和安慰在对话里说，不要让患者
        因为你念了一遍数字就以为已经存好了。
        写完后告诉患者「已经记进血糖记录，记录页能看到，也可以撤回」，不要编造
        没读到的数字，读不清的就不记并说明读不清。
        """

        now = datetime.now(UTC)
        oldest = now - timedelta(days=OLDEST_REPORT_DAYS)
        future_limit = now + timedelta(minutes=2)

        cleaned: list[tuple[datetime, GlucosePoint]] = []
        seen: set[tuple[str, int]] = set()
        skipped = 0
        for raw in readings[:MAX_REPORT_READINGS]:
            # 正常调用时框架已经校验过参数；这里再兜一层，是为了让「模型给了半个
            # 字段」这种情况只丢那一条，不至于整次记录都失败。
            try:
                point = raw if isinstance(raw, GlucosePoint) else GlucosePoint.model_validate(raw)
            except (TypeError, ValueError):
                skipped += 1
                continue
            try:
                measured_at = datetime.fromisoformat(point.measured_at)
            except ValueError:
                skipped += 1
                continue
            if measured_at.tzinfo is None:
                skipped += 1
                continue
            if measured_at > future_limit or measured_at < oldest:
                skipped += 1
                continue
            value_mg_dl = round(point.value_mmol * 18)
            key = (measured_at.isoformat(), value_mg_dl)
            if key in seen:
                # 报告里同一条被重复读出来很常见，重复的只留一条。
                skipped += 1
                continue
            seen.add(key)
            cleaned.append((measured_at, point))

        if not cleaned:
            return {
                "recorded": False,
                "count": 0,
                "skipped": skipped,
                "note": (
                    "一条也没记：需要带时区的测量时间和 mmol/L 数值。"
                    "请先问清时间，再说要不要记。"
                ),
            }

        async with sessions() as session:
            for measured_at, point in cleaned:
                await record_glucose_reading(
                    session,
                    user_id=runtime.context.user_id,
                    value_mg_dl=round(point.value_mmol * 18),
                    measured_at=measured_at,
                    context=point.context,
                    source=source,
                    source_device=device or "",
                    note=point.note,
                )
            await session.commit()

        return {
            "recorded": True,
            "count": len(cleaned),
            "skipped": skipped,
            "source": source,
            "first_at": cleaned[0][0].isoformat(),
            "last_at": cleaned[-1][0].isoformat(),
            "note": "已经写进血糖记录，患者能在记录页看到，也能逐条撤回。",
        }

    return record_glucose_readings


def build_glucose_report_tool(
    sessions: async_sessionmaker[AsyncSession] = default_session_factory,
) -> BaseTool:
    """创建把「一份报告说了什么」存进记录的工具。

    报告常常只有 AGP 图谱和汇总指标（均值、SD、CV、TIR/TAR/TBR、eHbA1c），没有
    逐点读数。硬拆成读数会变成一堆编出来的时间点，所以这一条只存指标本身。
    """

    @tool(RECORD_GLUCOSE_REPORT_TOOL_NAME)
    async def record_glucose_report(
        runtime: ToolRuntime[AgentContext],
        period_start: Annotated[
            str,
            Field(description="监测区间开始日，ISO 日期，例如 2024-05-30。"),
        ],
        period_end: Annotated[
            str,
            Field(description="监测区间结束日，ISO 日期，例如 2024-06-11。"),
        ],
        device: Annotated[
            str,
            Field(default="", description="报告上的设备名，例如 硅基动感Pro。没有就留空。"),
        ] = "",
        device_serial: Annotated[
            str,
            Field(
                default="",
                description="设备序列号/编号，例如 LT2410FE3P。报告上没有就留空。",
            ),
        ] = "",
        report_generated_at: Annotated[
            str | None,
            Field(
                default=None,
                description="报告生成日期，ISO 日期；报告上写了才填。",
            ),
        ] = None,
        mean_mmol: Annotated[
            float | None,
            Field(default=None, description="平均葡萄糖，mmol/L。报告没写就留空。"),
        ] = None,
        sd_mmol: Annotated[
            float | None,
            Field(default=None, description="标准差，mmol/L。"),
        ] = None,
        cv_percent: Annotated[
            float | None,
            Field(default=None, ge=0, le=100, description="变异系数，百分数，例如 23.27。"),
        ] = None,
        ehba1c_percent: Annotated[
            float | None,
            Field(default=None, ge=0, le=100, description="预估糖化血红蛋白，百分数。"),
        ] = None,
        tir_percent: Annotated[
            float | None,
            Field(default=None, ge=0, le=100, description="目标范围内时间占比，百分数。"),
        ] = None,
        tar_percent: Annotated[
            float | None,
            Field(default=None, ge=0, le=100, description="高于目标范围占比，百分数。"),
        ] = None,
        tbr_percent: Annotated[
            float | None,
            Field(default=None, ge=0, le=100, description="低于目标范围占比，百分数。"),
        ] = None,
        normal_percent: Annotated[
            float | None,
            Field(
                default=None,
                ge=0,
                le=100,
                description="分档里的「正常/目标范围内」占比，百分数。报告分五档时才填。",
            ),
        ] = None,
        low_percent: Annotated[
            float | None,
            Field(default=None, ge=0, le=100, description="分档里的「低」占比，百分数。"),
        ] = None,
        very_low_percent: Annotated[
            float | None,
            Field(default=None, ge=0, le=100, description="分档里的「很低」占比，百分数。"),
        ] = None,
        high_percent: Annotated[
            float | None,
            Field(default=None, ge=0, le=100, description="分档里的「高」占比，百分数。"),
        ] = None,
        very_high_percent: Annotated[
            float | None,
            Field(default=None, ge=0, le=100, description="分档里的「很高」占比，百分数。"),
        ] = None,
        lbgi_level: Annotated[
            Literal["", "high", "moderate", "low", "lowest"],
            Field(
                default="",
                description=(
                    "报告上「低血糖风险」的档位：high=高、moderate=中、low=低、"
                    "lowest=最低；报告没写就留空。"
                ),
            ),
        ] = "",
        note: Annotated[
            str | None,
            Field(default=None, description="一句备注，例如报告来自哪家医院。"),
        ] = None,
    ) -> dict[str, object]:
        """把一份 CGM/化验报告的关键指标存进记录页，患者以后能回看。

        患者发来报告、你读完之后调用一次，把区间和报告上写着的指标记下来：
        记录页会显示「这份报告说了什么」，而不是我们编出来的曲线。
        只记报告上真的写了的项，没写的留空，不要用估算值补齐，也不要自己算
        平均值或 TIR 填进去。报告如果按「正常/低/很低/高/很高」五档给占比，
        就填 normal/low/very_low/high/very_high 五档（三档的 TAR/TBR 由系统加，
        你不用算）；报告写了「低血糖风险 高/中/低/最低」，就填 lbgi_level。
        存完告诉患者「这份报告我记在血糖记录里了」。
        """

        try:
            start = date.fromisoformat(period_start)
            end = date.fromisoformat(period_end)
        except ValueError as error:
            raise ValueError(
                "日期要写成 2024-05-30 这种格式：先问清监测的起止日期，再存这份报告。"
            ) from error
        if end < start:
            raise ValueError(
                "监测区间的结束日不能早于开始日。先跟患者确认这两个日期，再存。"
            )
        if end > datetime.now(UTC).date() + timedelta(days=1):
            raise ValueError(
                "结束日在将来，这份报告的时间还没到。先问清是哪一段时间的报告。"
            )
        generated: date | None = None
        if report_generated_at:
            try:
                generated = date.fromisoformat(report_generated_at)
            except ValueError as error:
                raise ValueError(
                    "报告生成日期要写成 2025-07-31 这种格式；读不准就留空。"
                ) from error
            if generated > datetime.now(UTC).date() + timedelta(days=1):
                raise ValueError("报告生成日期在将来，先跟患者核对一遍。")
        metrics = [
            mean_mmol,
            sd_mmol,
            cv_percent,
            ehba1c_percent,
            tir_percent,
            tar_percent,
            tbr_percent,
            normal_percent,
            low_percent,
            very_low_percent,
            high_percent,
            very_high_percent,
        ]
        if all(value is None for value in metrics):
            raise ValueError(
                "一个指标都没给：至少要读出一个（平均值、TIR、eHbA1c 都可以）。"
                "读不清就跟患者说你没读清，不要存空壳。"
            )

        async with sessions() as session:
            report = await save_glucose_report(
                session,
                user_id=runtime.context.user_id,
                period_start=start,
                period_end=end,
                device=device[:64],
                device_serial=device_serial[:32],
                report_generated_at=generated,
                mean_mmol=mean_mmol,
                sd_mmol=sd_mmol,
                cv_percent=cv_percent,
                ehba1c_percent=ehba1c_percent,
                tir_percent=tir_percent,
                tar_percent=tar_percent,
                tbr_percent=tbr_percent,
                normal_percent=normal_percent,
                low_percent=low_percent,
                very_low_percent=very_low_percent,
                high_percent=high_percent,
                very_high_percent=very_high_percent,
                lbgi_level=lbgi_level,
                note=(note or None) and note[:200],
            )
            await session.commit()
            report_id = str(report.id)

        return {
            "recorded": True,
            "id": report_id,
            "period": f"{start.isoformat()}~{end.isoformat()}",
            "note": (
                "这份报告的速览已经存进血糖记录，患者能在记录页看到；"
                "解释的时候按报告自己的目标范围说。"
            ),
        }

    return record_glucose_report
