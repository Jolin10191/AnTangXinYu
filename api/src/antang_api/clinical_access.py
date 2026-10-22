"""医护统一密码只扩大只读查询范围，不能替代个人登录或修改业务角色。"""
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from secrets import token_urlsafe

from fastapi import HTTPException
from sqlalchemy import delete, func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from antang_api.models import PatientAccessAudit, User, UserRole
from antang_api.models.clinical_access import ClinicalAccessSession, ClinicalAccessSettings
from antang_api.patient_access import require_role
from antang_api.routers.auth import AuthenticatedSession
from antang_api.security import hash_password, verify_password


async def clinical_session(session: AsyncSession, auth: AuthenticatedSession, token: str | None) -> ClinicalAccessSession | None:
    require_role(auth.user, UserRole.CLINICIAN)
    if not token or len(token) > 256:
        return None
    return await session.scalar(
        select(ClinicalAccessSession)
        .join(ClinicalAccessSettings, ClinicalAccessSettings.id == 1)
        .where(
            ClinicalAccessSession.token_hash == sha256(token.encode()).hexdigest(),
            ClinicalAccessSession.user_id == auth.user.id,
            ClinicalAccessSession.login_session_id == auth.login_session.id,
            ClinicalAccessSession.password_revision == ClinicalAccessSettings.revision,
            or_(ClinicalAccessSession.expires_at.is_(None), ClinicalAccessSession.expires_at > datetime.now(UTC)),
        )
    )


async def require_all_patients(session: AsyncSession, auth: AuthenticatedSession, token: str | None) -> None:
    if await clinical_session(session, auth, token) is None:
        session.add(PatientAccessAudit(actor_user_id=auth.user.id, action="clinical:all:denied"))
        await session.commit()
        raise HTTPException(403, "全部患者视图尚未解锁或已失效，请重新验证统一密码")


async def unlock_all_patients(session: AsyncSession, auth: AuthenticatedSession, password: str) -> ClinicalAccessSession:
    require_role(auth.user, UserRole.CLINICIAN)
    # 同一医护的并发猜测按个人账户串行，避免锁住全体医护。
    user = await session.scalar(select(User).where(User.id == auth.user.id).with_for_update().execution_options(populate_existing=True))
    if user is None or not user.is_active or user.role != UserRole.CLINICIAN:
        raise HTTPException(403, "当前账号没有医护权限")
    now = datetime.now(UTC)
    failures = await session.scalar(select(func.count()).select_from(PatientAccessAudit).where(
        PatientAccessAudit.actor_user_id == user.id,
        PatientAccessAudit.action == "clinical:unlock:denied",
        PatientAccessAudit.created_at >= now - timedelta(minutes=15),
    ))
    if failures is not None and failures >= 5:
        raise HTTPException(429, "验证失败次数较多，请 15 分钟后再试")
    settings = await session.get(ClinicalAccessSettings, 1)
    if settings is None:
        raise HTTPException(409, "统一密码尚未设置，请联系研发管理人员")
    if not await run_in_threadpool(verify_password, password, settings.password_hash):
        session.add(PatientAccessAudit(actor_user_id=user.id, action="clinical:unlock:denied"))
        await session.commit()
        raise HTTPException(403, "统一密码不正确")
    await session.execute(delete(ClinicalAccessSession).where(ClinicalAccessSession.expires_at <= now))
    access = ClinicalAccessSession(
        user_id=user.id, login_session_id=auth.login_session.id,
        token_hash="", password_revision=settings.revision,
        expires_at=None,
    )
    # 明文令牌由路由生成并只返回一次，数据库只存哈希。
    return access


async def rotate_clinical_password(session: AsyncSession, user: User, account_password: str, new_password: str) -> None:
    require_role(user, UserRole.RESEARCHER)
    if not await run_in_threadpool(verify_password, account_password, user.password_hash):
        raise HTTPException(403, "个人账号密码不正确，统一密码未修改")
    password_hash = await run_in_threadpool(hash_password, new_password)
    await session.execute(insert(ClinicalAccessSettings).values(
        id=1, password_hash=password_hash, revision=1,
        updated_by=user.id, updated_at=datetime.now(UTC),
    ).on_conflict_do_update(index_elements=[ClinicalAccessSettings.id], set_={
        "password_hash": password_hash,
        "revision": ClinicalAccessSettings.revision + 1,
        "updated_by": user.id,
        "updated_at": datetime.now(UTC),
    }))
    await session.execute(delete(ClinicalAccessSession))
    session.add(PatientAccessAudit(actor_user_id=user.id, action="clinical:password:rotate"))
    await session.commit()


def assign_unlock_token(access: ClinicalAccessSession) -> str:
    token = token_urlsafe(32)
    access.token_hash = sha256(token.encode()).hexdigest()
    return token
