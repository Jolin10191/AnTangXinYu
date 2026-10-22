"""按当前数据库状态检查角色和资源关系，不从 JWT 推断权限。"""

from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from antang_api.models import PatientAccessAudit, PatientAccessGrant, User, UserRole
from antang_api.routers.auth import get_current_user


def require_role(user: User, role: UserRole) -> User:
    if user.role != role:
        raise HTTPException(403, "当前账号没有此操作权限")
    return user


async def get_patient_user(user: Annotated[User, Depends(get_current_user)]) -> User:
    return require_role(user, UserRole.PATIENT)


async def get_clinician_user(user: Annotated[User, Depends(get_current_user)]) -> User:
    return require_role(user, UserRole.CLINICIAN)


async def get_researcher_user(user: Annotated[User, Depends(get_current_user)]) -> User:
    return require_role(user, UserRole.RESEARCHER)


async def check_patient_access(
    session: AsyncSession,
    *,
    clinician: User,
    patient_id: UUID,
    resource: str,
) -> None:
    """每次读取均验证有效患者及授权；拒绝也提交元数据审计。"""
    require_role(clinician, UserRole.CLINICIAN)
    grant = await session.scalar(
        select(PatientAccessGrant)
        .join(User, User.id == PatientAccessGrant.patient_id)
        .where(
            PatientAccessGrant.patient_id == patient_id,
            PatientAccessGrant.clinician_id == clinician.id,
            PatientAccessGrant.revoked_at.is_(None),
            User.is_active.is_(True),
            User.role == UserRole.PATIENT,
        )
    )
    session.add(
        PatientAccessAudit(
            actor_user_id=clinician.id,
            patient_id=patient_id,
            grant_id=grant.id if grant else None,
            action=f"{resource}:{'allowed' if grant else 'denied'}",
        )
    )
    if grant is None:
        await session.commit()
        raise HTTPException(403, "未获得该患者的有效授权，或授权已撤销")


async def set_user_role(
    session: AsyncSession,
    *,
    username: str,
    role: UserRole,
    maintainer: str,
    actor_user_id: UUID | None = None,
    commit: bool = True,
) -> User:
    """维护者命令专用；角色变更同时终止旧授权，恢复角色不恢复授权。"""
    user = await session.scalar(
        select(User)
        .where(
            User.username_normalized == username.strip().casefold(),
        )
        .with_for_update()
    )
    if user is None:
        raise ValueError("账号不存在，请先注册")
    if user.role == role:
        return user
    previous = user.role
    grants = await session.scalars(
        select(PatientAccessGrant)
        .where(
            or_(
                PatientAccessGrant.patient_id == user.id,
                PatientAccessGrant.clinician_id == user.id,
            ),
            PatientAccessGrant.revoked_at.is_(None),
        )
        .with_for_update()
    )
    for grant in grants:
        grant.revoked_at = datetime.now(UTC)
        session.add(
            PatientAccessAudit(
                actor_user_id=actor_user_id,
                maintainer=maintainer,
                patient_id=grant.patient_id,
                target_user_id=user.id,
                grant_id=grant.id,
                action="role_change:revoke",
            )
        )
    user.role = role
    session.add(
        PatientAccessAudit(
            actor_user_id=actor_user_id,
            maintainer=maintainer,
            target_user_id=user.id,
            action=f"role:{previous.value}:{role.value}",
        )
    )
    if commit:
        await session.commit()
    return user
