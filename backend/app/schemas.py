"""Request and response shapes for the API."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    email: str
    role: str


class ControlIn(BaseModel):
    instrument: str = Field(min_length=1, max_length=100)
    analyte: str = Field(min_length=1, max_length=100)
    level: str = Field(min_length=1, max_length=50)
    lot: str = Field(min_length=1, max_length=50)
    target_mean: float
    target_sd: float = Field(gt=0)
    units: str = ""


class ControlOut(ControlIn):
    model_config = ConfigDict(from_attributes=True)
    id: int
    active: bool
    latest_status: str | None = None
    open_violations: int = 0


class ResultIn(BaseModel):
    value: float
    run_id: str = Field(min_length=1, max_length=50)
    measured_at: datetime | None = None


class RunIn(BaseModel):
    """Several control levels measured in the same run."""
    run_id: str = Field(min_length=1, max_length=50)
    measured_at: datetime | None = None
    values: dict[int, float]  # control id -> value


class ViolationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    rule: str
    scope: str
    corrective_action: str | None
    reviewed_at: datetime | None


class ResultOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    control_id: int
    value: float
    z: float
    run_id: str
    measured_at: datetime
    status: str
    violations: list[ViolationOut]


class ViolationDetail(ViolationOut):
    result_id: int
    control_id: int
    control_label: str
    value: float
    measured_at: datetime
    reviewed_by: str | None


class CorrectiveActionIn(BaseModel):
    corrective_action: str = Field(min_length=3, max_length=2000)


class ImportSummary(BaseModel):
    imported: int
    warnings: int
    rejects: int
    errors: list[str]
