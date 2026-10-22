"""研发账号的医护管理；不提供患者健康资料查询。"""

from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from antang_api.database import get_session
from antang_api.models import (
    ApplicationStatus,
    ClinicianApplication,
    PatientAccessAudit,
    PersonalProfile,
    ProactiveCareSettings,
    User,
    UserRole,
)
from antang_api.patient_access import (
    get_patient_user,
    get_researcher_user,
    set_user_role,
)
from antang_api.routers.auth import get_current_user
from antang_api.schemas.administration import (
    ApplicationsResponse,
    ClinicianApplicationRequest,
    ClinicianApplicationResponse,
    CreateClinicianRequest,
    OverviewResponse,
    OwnApplicationResponse,
    ReviewRequest,
)
from antang_api.schemas.auth import UsernameRequest, UserResponse
from antang_api.schemas.patient_access import PatientsResponse
from antang_api.security import hash_password

router = APIRouter(prefix="/api/v1", tags=["clinician-management"])
Database = Annotated[AsyncSession, Depends(get_session)]
Developer = Annotated[User, Depends(get_researcher_user)]
Patient = Annotated[User, Depends(get_patient_user)]


def application_response(
    application: ClinicianApplication, user: User
) -> ClinicianApplicationResponse:
    return ClinicianApplicationResponse(
        id=application.id,
        applicant=UserResponse.model_validate(user),
        full_name=application.full_name,
        organization=application.organization,
        status=application.status,
        created_at=application.created_at,
        reviewed_at=application.reviewed_at,
        rejection_reason=application.rejection_reason,
    )


@router.get("/clinician-applications/me", response_model=OwnApplicationResponse)
async def own_application(
    user: Annotated[User, Depends(get_current_user)], session: Database
) -> OwnApplicationResponse:
    application = await session.scalar(
        select(ClinicianApplication)
        .where(ClinicianApplication.user_id == user.id)
        .order_by(
            ClinicianApplication.created_at.desc(), ClinicianApplication.id.desc()
        )
        .limit(1)
    )
    return OwnApplicationResponse(
        application=application_response(application, user) if application else None
    )


@router.post(
    "/clinician-applications",
    response_model=ClinicianApplicationResponse,
    status_code=201,
)
async def submit_application(
    request: ClinicianApplicationRequest, user: Patient, session: Database
) -> ClinicianApplicationResponse:
    await session.refresh(user, with_for_update=True)
    if not user.is_active or user.role != UserRole.PATIENT:
        raise HTTPException(403, "当前账号不能提交医护申请")
    user.full_name = request.full_name
    application = ClinicianApplication(
        user_id=user.id, full_name=request.full_name, organization=request.organization
    )
    session.add(application)
    session.add(
        PatientAccessAudit(
            actor_user_id=user.id,
            target_user_id=user.id,
            action="clinician_application:submit",
        )
    )
    try:
        await session.commit()
    except IntegrityError as error:
        await session.rollback()
        raise HTTPException(409, "已有待审批申请，请勿重复提交") from error
    return application_response(application, user)


@router.get("/admin/overview", response_model=OverviewResponse)
async def overview(user: Developer, session: Database) -> OverviewResponse:
    pending = (
        select(func.count(ClinicianApplication.id))
        .join(User, User.id == ClinicianApplication.user_id)
        .where(
            ClinicianApplication.status == ApplicationStatus.PENDING,
            User.role == UserRole.PATIENT,
            User.is_active.is_(True),
        )
        .correlate(None)
        .scalar_subquery()
    )
    row = (
        await session.execute(
            select(
                func.count(User.id),
                func.count(User.id).filter(User.role == UserRole.PATIENT),
                func.count(User.id).filter(User.role == UserRole.CLINICIAN),
                func.count(User.id).filter(User.role == UserRole.RESEARCHER),
                pending,
            )
        )
    ).one()
    return OverviewResponse(
        total_users=row[0],
        patients=row[1],
        clinicians=row[2],
        collaborators=row[3],
        pending_applications=row[4],
    )


@router.get("/admin/clinician-applications", response_model=ApplicationsResponse)
async def applications(
    user: Developer,
    session: Database,
    status: ApplicationStatus = ApplicationStatus.PENDING,
    after: UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
) -> ApplicationsResponse:
    query = (
        select(ClinicianApplication, User)
        .join(User, User.id == ClinicianApplication.user_id)
        .where(ClinicianApplication.status == status)
    )
    if status == ApplicationStatus.PENDING:
        query = query.where(User.is_active.is_(True), User.role == UserRole.PATIENT)
    if after is not None:
        query = query.where(ClinicianApplication.id > after)
    rows = (
        await session.execute(query.order_by(ClinicianApplication.id).limit(limit + 1))
    ).all()
    return ApplicationsResponse(
        applications=[application_response(a, u) for a, u in rows[:limit]],
        next_after=rows[limit - 1][0].id if len(rows) > limit else None,
    )


@router.post(
    "/admin/clinician-applications/{application_id}/review",
    response_model=ClinicianApplicationResponse,
)
async def review(
    application_id: UUID, request: ReviewRequest, user: Developer, session: Database
) -> ClinicianApplicationResponse:
    if request.decision == "reject" and not request.reason:
        raise HTTPException(422, "拒绝申请须填写原因")
    application = await session.get(ClinicianApplication, application_id)
    if application is None:
        raise HTTPException(404, "申请不存在")
    applicant = await session.scalar(
        select(User)
        .where(User.id == application.user_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    # 所有入口统一先锁账号、再锁申请，避免审批与直接添加相互等待。
    await session.refresh(application, with_for_update=True)
    if application.status != ApplicationStatus.PENDING:
        raise HTTPException(409, "申请已处理，请刷新列表")
    if (
        applicant is None
        or not applicant.is_active
        or applicant.role != UserRole.PATIENT
    ):
        raise HTTPException(409, "申请人当前身份或账号状态已变化，请核对账号")
    if request.decision == "approve":
        await set_user_role(
            session,
            username=applicant.username,
            role=UserRole.CLINICIAN,
            maintainer=f"researcher:{user.id}",
            actor_user_id=user.id,
            commit=False,
        )
        application.status = ApplicationStatus.APPROVED
    else:
        application.status = ApplicationStatus.REJECTED
        application.rejection_reason = request.reason
    application.reviewed_by = user.id
    application.reviewed_at = datetime.now(UTC)
    session.add(
        PatientAccessAudit(
            actor_user_id=user.id,
            target_user_id=applicant.id,
            action=f"clinician_application:{request.decision}",
        )
    )
    await session.commit()
    return application_response(application, applicant)


@router.get("/admin/clinicians", response_model=PatientsResponse)
async def clinicians(
    user: Developer,
    session: Database,
    after: UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
) -> PatientsResponse:
    query = select(User).where(User.role == UserRole.CLINICIAN)
    if after is not None:
        query = query.where(User.id > after)
    rows = list(await session.scalars(query.order_by(User.id).limit(limit + 1)))
    return PatientsResponse(
        patients=[UserResponse.model_validate(u) for u in rows[:limit]],
        next_after=rows[limit - 1].id if len(rows) > limit else None,
    )


@router.post("/admin/clinicians", response_model=UserResponse, status_code=201)
async def create_clinician(
    request: CreateClinicianRequest, user: Developer, session: Database
) -> UserResponse:
    clinician = User(
        username=request.username,
        username_normalized=request.username.casefold(),
        full_name=request.full_name,
        role=UserRole.CLINICIAN,
        password_hash=await run_in_threadpool(hash_password, request.password),
    )
    session.add(clinician)
    try:
        await session.flush()
        session.add_all(
            [
                PersonalProfile(user_id=clinician.id),
                ProactiveCareSettings(user_id=clinician.id),
                PatientAccessAudit(
                    actor_user_id=user.id,
                    target_user_id=clinician.id,
                    action="clinician:create",
                ),
            ]
        )
        await session.commit()
    except IntegrityError as error:
        await session.rollback()
        raise HTTPException(
            409, "用户名已存在，请使用添加已有账号或更换用户名"
        ) from error
    return UserResponse.model_validate(clinician)


@router.post("/admin/clinicians/assign", response_model=UserResponse)
async def assign_clinician(
    request: UsernameRequest, user: Developer, session: Database
) -> UserResponse:
    target = await session.scalar(
        select(User)
        .where(User.username_normalized == request.username.casefold())
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if target is None:
        raise HTTPException(404, "账号不存在，请先注册或创建医护账号")
    if not target.is_active or target.role != UserRole.PATIENT:
        raise HTTPException(409, "只能将启用中的患者账号添加为医护")
    await set_user_role(
        session,
        username=target.username,
        role=UserRole.CLINICIAN,
        maintainer=f"researcher:{user.id}",
        actor_user_id=user.id,
        commit=False,
    )
    pending = await session.scalar(
        select(ClinicianApplication)
        .where(
            ClinicianApplication.user_id == target.id,
            ClinicianApplication.status == ApplicationStatus.PENDING,
        )
        .with_for_update()
    )
    if pending is not None:
        pending.status = ApplicationStatus.APPROVED
        pending.reviewed_by = user.id
        pending.reviewed_at = datetime.now(UTC)
    await session.commit()
    return UserResponse.model_validate(target)
