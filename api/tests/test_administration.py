from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from antang_api.models import ClinicianApplication, PatientAccessAudit, UserRole
from antang_api.patient_access import set_user_role


async def account(
    client: AsyncClient,
    session: AsyncSession,
    role: UserRole = UserRole.PATIENT,
    **extra,
):
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "consent_accepted": True,
            "username": "manage_" + uuid4().hex[:12],
            "password": "review-password",
            **extra,
        },
    )
    assert response.status_code == 201, response.text
    result = response.json()
    if role != UserRole.PATIENT:
        await set_user_role(
            session, username=result["user"]["username"], role=role, maintainer="test"
        )
    return result, {"Authorization": "Bearer " + result["access_token"]}


async def test_registration_approval_uses_current_role_and_requires_patient_consent(
    client, db_session
):
    developer, admin = await account(client, db_session, UserRole.RESEARCHER)
    patient, p_headers = await account(client, db_session, full_name="患者姓名")
    applicant, c_headers = await account(
        client,
        db_session,
        full_name="医护姓名",
        registration_kind="clinician",
        organization="联调机构",
    )
    assert applicant["user"]["role"] == "patient"
    assert applicant["user"]["application_status"] == "pending"
    assert (await client.get("/api/v1/patients", headers=c_headers)).status_code == 403
    pending = (
        await client.get("/api/v1/admin/clinician-applications", headers=admin)
    ).json()
    application = next(
        a
        for a in pending["applications"]
        if a["applicant"]["id"] == applicant["user"]["id"]
    )
    assert application["full_name"] == "医护姓名"
    approved = await client.post(
        f"/api/v1/admin/clinician-applications/{application['id']}/review",
        headers=admin,
        json={"decision": "approve"},
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"
    me = (await client.get("/api/v1/auth/me", headers=c_headers)).json()
    assert me["role"] == "clinician" and me["application_status"] == "approved"
    assert (await client.get("/api/v1/patients", headers=c_headers)).json()[
        "patients"
    ] == []
    assert (
        await client.get(
            f"/api/v1/patients/{patient['user']['id']}/health-profile",
            headers=c_headers,
        )
    ).status_code == 403
    grant = await client.post(
        "/api/v1/patient-access-grants",
        headers=p_headers,
        json={"clinician_id": applicant["user"]["id"]},
    )
    assert grant.status_code == 201
    visible = (await client.get("/api/v1/patients", headers=c_headers)).json()[
        "patients"
    ]
    assert visible[0]["full_name"] == "患者姓名"
    assert (
        await client.get(
            f"/api/v1/patients/{patient['user']['id']}/health-profile",
            headers=c_headers,
        )
    ).status_code == 200
    assert (await client.get("/api/v1/patients", headers=admin)).status_code == 403
    assert (
        await client.post(
            f"/api/v1/admin/clinician-applications/{application['id']}/review",
            headers=admin,
            json={"decision": "approve"},
        )
    ).status_code == 409
    row = await db_session.get(ClinicianApplication, application["id"])
    assert str(row.reviewed_by) == developer["user"]["id"]


async def test_rejection_reapplication_and_pending_uniqueness(client, db_session):
    _, admin = await account(client, db_session, UserRole.RESEARCHER)
    _, headers = await account(client, db_session)
    body = {"full_name": "申请人", "organization": "待核对机构"}
    submitted = await client.post(
        "/api/v1/clinician-applications", headers=headers, json=body
    )
    assert submitted.status_code == 201
    assert (
        await client.post("/api/v1/clinician-applications", headers=headers, json=body)
    ).status_code == 409
    path = f"/api/v1/admin/clinician-applications/{submitted.json()['id']}/review"
    assert (
        await client.post(path, headers=headers, json={"decision": "approve"})
    ).status_code == 403
    assert (
        await client.post(path, headers=admin, json={"decision": "reject"})
    ).status_code == 422
    rejected = await client.post(
        path, headers=admin, json={"decision": "reject", "reason": "请核对所属机构"}
    )
    assert rejected.status_code == 200
    assert rejected.json()["rejection_reason"] == "请核对所属机构"
    assert (await client.get("/api/v1/auth/me", headers=headers)).json()[
        "application_status"
    ] == "rejected"
    assert (
        await client.post(
            "/api/v1/clinician-applications",
            headers=headers,
            json={**body, "organization": "已补充机构"},
        )
    ).status_code == 201
    mine = (
        await client.get("/api/v1/clinician-applications/me", headers=headers)
    ).json()["application"]
    assert mine["status"] == "pending" and mine["organization"] == "已补充机构"


async def test_admin_create_assign_counts_and_old_grants_end(client, db_session):
    _, admin = await account(client, db_session, UserRole.RESEARCHER)
    patient, headers = await account(client, db_session)
    old_clinician, c_headers = await account(client, db_session, UserRole.CLINICIAN)
    before = (await client.get("/api/v1/admin/overview", headers=admin)).json()
    assert (
        before["total_users"]
        == before["patients"] + before["clinicians"] + before["collaborators"]
    )
    username = "new_doc_" + uuid4().hex[:8]
    created = await client.post(
        "/api/v1/admin/clinicians",
        headers=admin,
        json={
            "username": username,
            "password": "created-password",
            "full_name": "新增医护",
        },
    )
    assert created.status_code == 201
    assert "password" not in created.text
    assert (
        await client.post(
            "/api/v1/auth/login",
            json={"username": username, "password": "created-password"},
        )
    ).json()["user"]["role"] == "clinician"
    assert (
        await client.post(
            "/api/v1/patient-access-grants",
            headers=headers,
            json={"clinician_id": old_clinician["user"]["id"]},
        )
    ).status_code == 201
    assigned = await client.post(
        "/api/v1/admin/clinicians/assign",
        headers=admin,
        json={"username": patient["user"]["username"]},
    )
    assert assigned.status_code == 200 and assigned.json()["role"] == "clinician"
    assert (
        await client.get(
            f"/api/v1/patients/{patient['user']['id']}/health-profile",
            headers=c_headers,
        )
    ).status_code == 403
    after = (await client.get("/api/v1/admin/overview", headers=admin)).json()
    assert after["total_users"] == before["total_users"] + 1
    assert after["clinicians"] == before["clinicians"] + 2
    assert after["patients"] == before["patients"] - 1
    audit = await db_session.scalar(
        select(PatientAccessAudit).where(
            PatientAccessAudit.action == "clinician:create"
        )
    )
    assert audit.actor_user_id is not None


@pytest.mark.parametrize("role", [UserRole.PATIENT, UserRole.CLINICIAN])
async def test_management_is_not_available_to_other_roles(client, db_session, role):
    _, headers = await account(client, db_session, role)
    for path in (
        "/admin/overview",
        "/admin/clinicians",
        "/admin/clinician-applications",
    ):
        assert (await client.get("/api/v1" + path, headers=headers)).status_code == 403
    assert (
        await client.post(
            "/api/v1/admin/clinicians",
            headers=headers,
            json={
                "username": "not_allowed",
                "password": "not-allowed-password",
                "full_name": "不允许",
            },
        )
    ).status_code == 403


async def test_name_can_be_updated_without_role_escalation(client, db_session):
    _, headers = await account(client, db_session)
    response = await client.patch(
        "/api/v1/auth/me", headers=headers, json={"full_name": "已填写姓名"}
    )
    assert response.status_code == 200 and response.json()["full_name"] == "已填写姓名"
    assert (
        await client.patch(
            "/api/v1/auth/me",
            headers=headers,
            json={"full_name": "另一个姓名", "role": "researcher"},
        )
    ).status_code == 422
    assert (
        await client.post(
            "/api/v1/auth/register",
            json={
                "consent_accepted": True,
                "username": "invalid_" + uuid4().hex[:8],
                "password": "invalid-password",
                "registration_kind": "clinician",
            },
        )
    ).status_code == 422
