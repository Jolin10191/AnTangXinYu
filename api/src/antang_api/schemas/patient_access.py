from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from antang_api.schemas.auth import UsernameRequest, UserResponse


class ResolveClinicianRequest(UsernameRequest):
    model_config = ConfigDict(extra="forbid")


class GrantRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    clinician_id: UUID


class GrantResponse(BaseModel):
    id: UUID
    clinician: UserResponse
    granted_at: datetime
    revoked_at: datetime | None
    available: bool


class GrantsResponse(BaseModel):
    grants: list[GrantResponse]


class PatientsResponse(BaseModel):
    patients: list[UserResponse]
    next_after: UUID | None
