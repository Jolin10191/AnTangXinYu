from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, StringConstraints

from antang_api.models import ApplicationStatus
from antang_api.schemas.auth import (
    FullName,
    Organization,
    Password,
    UsernameRequest,
    UserResponse,
)


class ClinicianApplicationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    full_name: FullName
    organization: Organization


class ClinicianApplicationResponse(BaseModel):
    id: UUID
    applicant: UserResponse
    full_name: str
    organization: str
    status: ApplicationStatus
    created_at: datetime
    reviewed_at: datetime | None
    rejection_reason: str | None


class OwnApplicationResponse(BaseModel):
    application: ClinicianApplicationResponse | None


class ApplicationsResponse(BaseModel):
    applications: list[ClinicianApplicationResponse]
    next_after: UUID | None


class ReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: Literal["approve", "reject"]
    reason: (
        Annotated[
            str, StringConstraints(strip_whitespace=True, min_length=1, max_length=512)
        ]
        | None
    ) = None


class CreateClinicianRequest(UsernameRequest):
    model_config = ConfigDict(extra="forbid")
    password: Password
    full_name: FullName


class OverviewResponse(BaseModel):
    total_users: int
    patients: int
    clinicians: int
    collaborators: int
    pending_applications: int
