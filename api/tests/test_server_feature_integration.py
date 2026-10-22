"""Verify actual overlaps between deployed health features and reviewed roles."""

from datetime import UTC, datetime
from uuid import uuid4

from antang_api.models import UserRole
from antang_api.patient_access import set_user_role


async def signup(client, **extra):
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "username": "unified_" + uuid4().hex[:12],
            "password": "unified-password",
            "full_name": "同名体验患者",
            "consent_accepted": True,
            **extra,
        },
    )
    assert response.status_code == 201, response.text
    account = response.json()
    return account, {"Authorization": "Bearer " + account["access_token"]}


async def test_registration_retains_server_consent_and_local_clinician_approval(client):
    payload = {
        "username": "consent_" + uuid4().hex[:12],
        "password": "unified-password",
    }
    assert (await client.post("/api/v1/auth/register", json=payload)).status_code == 422
    assert (
        await client.post(
            "/api/v1/auth/register", json={**payload, "consent_accepted": False}
        )
    ).status_code == 422
    applicant, _ = await signup(
        client, registration_kind="clinician", organization="测试机构"
    )
    assert applicant["user"]["role"] == "patient"
    assert applicant["user"]["application_status"] == "pending"


async def test_added_patient_health_routes_respect_roles_and_preserve_existing_data(
    client, db_session
):
    patient, headers = await signup(client)
    _, second_headers = await signup(client)
    recorded = await client.post(
        "/api/v1/health-profile/glucose-readings",
        headers=headers,
        json={
            "value_mg_dl": 105,
            "measured_at": datetime.now(UTC).isoformat(),
            "context": "fasting",
        },
    )
    assert recorded.status_code == 201, recorded.text
    assert (
        len(
            (
                await client.get(
                    "/api/v1/health-profile/glucose-readings", headers=headers
                )
            ).json()
        )
        == 1
    )
    assert (
        await client.get(
            "/api/v1/health-profile/glucose-readings", headers=second_headers
        )
    ).json() == []
    for role in (UserRole.CLINICIAN, UserRole.RESEARCHER):
        await set_user_role(
            db_session,
            username=patient["user"]["username"],
            role=role,
            maintainer="test-sync",
        )
        for path in ("glucose-readings", "fear-summary", "fear-behavior"):
            assert (
                await client.get("/api/v1/health-profile/" + path, headers=headers)
            ).status_code == 403
        assert (
            await client.post(
                "/api/v1/voice/transcribe",
                headers=headers,
                files={"file": ("voice.wav", b"test-only", "audio/wav")},
            )
        ).status_code == 403


async def test_server_account_deletion_remains_available_with_new_roles(client):
    account, headers = await signup(client)
    response = await client.request(
        "DELETE",
        "/api/v1/auth/account",
        headers=headers,
        json={"password": "unified-password"},
    )
    assert response.status_code == 204, response.text
    assert (
        await client.post(
            "/api/v1/auth/login",
            json={
                "username": account["user"]["username"],
                "password": "unified-password",
            },
        )
    ).status_code == 401
