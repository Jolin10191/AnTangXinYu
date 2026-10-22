"""Use real authentication and isolated PostgreSQL for the clinical read boundary."""
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import select

from antang_api.models import PatientAccessAudit, UserRole
from antang_api.models.clinical_access import ClinicalAccessSession
from antang_api.patient_access import set_user_role

PASSWORD = "clinical-account-password"
SHARED = "shared-clinical-password"


async def account(client, session, role=UserRole.PATIENT):
    name = "clinical_" + uuid4().hex[:12]
    response = await client.post("/api/v1/auth/register", json={"username": name, "password": PASSWORD, "full_name": "工作台测试患者", "consent_accepted": True})
    assert response.status_code == 201
    data = response.json()
    if role != UserRole.PATIENT:
        await set_user_role(session, username=name, role=role, maintainer="test-clinical")
    return data, {"Authorization": "Bearer " + data["access_token"]}


async def configure(client, admin, password=SHARED):
    response = await client.put("/api/v1/admin/clinical-access-password", headers=admin, json={"account_password": PASSWORD, "new_password": password})
    assert response.status_code == 204, response.text


async def unlock(client, clinician, password=SHARED):
    response = await client.post("/api/v1/clinical/access/unlock", headers=clinician, json={"password": password})
    assert response.status_code == 200, response.text
    return {**clinician, "X-Clinical-Unlock": response.json()["token"]}


async def test_granted_timeline_uses_real_window_and_revocation(client, db_session):
    patient, patient_headers = await account(client, db_session)
    other, other_headers = await account(client, db_session)
    doctor, doctor_headers = await account(client, db_session, UserRole.CLINICIAN)
    root = "/api/v1/clinical/patients/" + patient["user"]["id"] + "/overview"
    assert (await client.get(root, headers=doctor_headers)).status_code == 403
    grant = await client.post("/api/v1/patient-access-grants", headers=patient_headers, json={"clinician_id": doctor["user"]["id"]})
    assert grant.status_code == 201
    now = datetime.now(UTC)
    for value, day in ((90, 2), (150, 1), (300, 40), (400, 1)):
        reading = await client.post("/api/v1/health-profile/glucose-readings", headers=patient_headers, json={"value_mg_dl": value, "measured_at": (now - timedelta(days=day)).isoformat()})
        assert reading.status_code == 201
        if value == 400:
            assert (await client.delete("/api/v1/health-profile/glucose-readings/" + reading.json()["id"], headers=patient_headers)).status_code == 204
    await client.post("/api/v1/health-profile/glucose-readings", headers=other_headers, json={"value_mg_dl": 500, "measured_at": now.isoformat()})
    response = await client.get(root, headers=doctor_headers, params={"start": (now - timedelta(days=7)).isoformat(), "end": (now + timedelta(seconds=1)).isoformat()})
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    data = response.json()
    assert [p["value_mg_dl"] for p in data["glucose"]["points"]] == [90, 150]
    assert data["glucose"]["summary"] == {"count": 2, "average_mg_dl": 120.0, "minimum_mg_dl": 90, "maximum_mg_dl": 150}
    assert data["wearable"]["period_start"] == data["period_start"]
    assert data["wearable"]["period_end"] == data["period_end"]
    assert data["wearable"]["sources"] == []
    assert (await client.get("/api/v1/clinical/patients/" + other["user"]["id"] + "/overview", headers=doctor_headers)).status_code == 403
    await client.delete("/api/v1/patient-access-grants/" + grant.json()["id"], headers=patient_headers)
    assert (await client.get(root, headers=doctor_headers)).status_code == 403
    assert (await client.get("/api/v1/clinical/patients", headers=doctor_headers)).json()["total"] == 0


async def test_shared_password_scope_is_personal_session_bound_and_revocable(client, db_session):
    patient, _ = await account(client, db_session)
    doctor, headers = await account(client, db_session, UserRole.CLINICIAN)
    _, admin = await account(client, db_session, UserRole.RESEARCHER)
    await configure(client, admin)
    root = "/api/v1/clinical/patients/" + patient["user"]["id"] + "/overview?scope=all"
    assert (await client.get(root, headers=headers)).status_code == 403
    opened = await unlock(client, headers)
    assert (await client.get(root, headers=opened)).status_code == 200
    page = await client.get("/api/v1/clinical/patients?scope=all", headers=opened)
    assert patient["user"]["id"] in [p["id"] for p in page.json()["patients"]]
    assert (await client.get("/api/v1/clinical/patients?scope=granted", headers=opened)).json()["total"] == 0
    # Knowing someone else's secondary token cannot expand a different login session.
    second_login = (await client.post("/api/v1/auth/login", json={"username": doctor["user"]["username"], "password": PASSWORD})).json()
    borrowed = {"Authorization": "Bearer " + second_login["access_token"], "X-Clinical-Unlock": opened["X-Clinical-Unlock"]}
    assert (await client.get(root, headers=borrowed)).status_code == 403
    await configure(client, admin, "rotated-clinical-password")
    assert (await client.get(root, headers=opened)).status_code == 403
    assert (await client.post("/api/v1/clinical/access/unlock", headers=headers, json={"password": SHARED})).status_code == 403
    opened = await unlock(client, headers, "rotated-clinical-password")
    assert (await client.get(root, headers=opened)).status_code == 200
    assert (await client.post("/api/v1/clinical/access/lock", headers=opened)).status_code == 204
    assert (await client.get(root, headers=opened)).status_code == 403
    audits = list(await db_session.scalars(select(PatientAccessAudit).where(PatientAccessAudit.actor_user_id == doctor["user"]["id"], PatientAccessAudit.patient_id == patient["user"]["id"], PatientAccessAudit.action == "clinical:all:overview")))
    assert len(audits) >= 1


async def test_patient_researcher_cannot_use_clinician_unlock_and_admin_changes_need_personal_password(client, db_session):
    _, patient = await account(client, db_session)
    _, admin = await account(client, db_session, UserRole.RESEARCHER)
    await configure(client, admin)
    for headers in (patient, admin):
        assert (await client.post("/api/v1/clinical/access/unlock", headers=headers, json={"password": SHARED})).status_code == 403
        assert (await client.get("/api/v1/clinical/patients?scope=all", headers=headers)).status_code == 403
    assert (await client.put("/api/v1/admin/clinical-access-password", headers=patient, json={"account_password": PASSWORD, "new_password": SHARED})).status_code == 403
    assert (await client.put("/api/v1/admin/clinical-access-password", headers=admin, json={"account_password": "wrong-password", "new_password": SHARED})).status_code == 403


async def test_unlock_expiry_role_change_and_rate_limit(client, db_session):
    doctor, headers = await account(client, db_session, UserRole.CLINICIAN)
    _, admin = await account(client, db_session, UserRole.RESEARCHER)
    await configure(client, admin)
    opened = await unlock(client, headers)
    access = await db_session.scalar(select(ClinicalAccessSession).where(ClinicalAccessSession.user_id == doctor["user"]["id"]))
    assert access is not None
    assert access.expires_at is None
    assert (await client.get("/api/v1/clinical/patients?scope=all", headers=opened)).status_code == 200
    access.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    await db_session.commit()
    assert (await client.get("/api/v1/clinical/patients?scope=all", headers=opened)).status_code == 403
    for _ in range(5):
        assert (await client.post("/api/v1/clinical/access/unlock", headers=headers, json={"password": "wrong-password"})).status_code == 403
    assert (await client.post("/api/v1/clinical/access/unlock", headers=headers, json={"password": SHARED})).status_code == 429
    await set_user_role(db_session, username=doctor["user"]["username"], role=UserRole.RESEARCHER, maintainer="test-clinical")
    assert (await client.get("/api/v1/clinical/patients", headers=headers)).status_code == 403


async def test_web_entry_and_invalid_time_windows(client, db_session):
    response = await client.get("/clinician")
    assert response.status_code == 200
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
    assert "医护工作台" in response.text
    patient, patient_headers = await account(client, db_session)
    doctor, headers = await account(client, db_session, UserRole.CLINICIAN)
    await client.post("/api/v1/patient-access-grants", headers=patient_headers, json={"clinician_id": doctor["user"]["id"]})
    path = "/api/v1/clinical/patients/" + patient["user"]["id"] + "/overview"
    for params in ({"start": "2026-01-01T00:00:00", "end": "2026-01-02T00:00:00"}, {"start": "2026-01-01T00:00:00Z", "end": "2026-05-01T00:00:00Z"}):
        assert (await client.get(path, headers=headers, params=params)).status_code == 422
