import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, EmailStr, Field

ReasonCode = Literal["personal", "medical", "family", "bereavement", "travel", "other"]
AccrualFrequency = Literal["none", "monthly", "yearly"]


class DepartmentIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class DepartmentOut(DepartmentIn):
    model_config = {"from_attributes": True}
    id: uuid.UUID


class DesignationIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class DesignationOut(DesignationIn):
    model_config = {"from_attributes": True}
    id: uuid.UUID


class EmployeeIn(BaseModel):
    code: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=200)
    work_email: EmailStr
    phone: str | None = None
    department_id: uuid.UUID | None = None
    designation_id: uuid.UUID | None = None
    manager_id: uuid.UUID | None = None
    join_date: date
    status: str = "active"
    employment_type: str = "full_time"
    user_id: uuid.UUID | None = None  # links this employee to a login for self-service


class EmployeeListOut(BaseModel):
    """List view: no phone/work_email -- those are the "sensitive fields" that
    only the detail endpoint exposes (and audits)."""

    model_config = {"from_attributes": True}
    id: uuid.UUID
    code: str
    name: str
    department_id: uuid.UUID | None
    designation_id: uuid.UUID | None
    status: str
    # Not personal data -- an internal reference, safe here (unlike phone/email)
    # and needed so the UI can tell which row in a list is "me".
    user_id: uuid.UUID | None


class EmployeeDetailOut(BaseModel):
    model_config = {"from_attributes": True}
    id: uuid.UUID
    code: str
    name: str
    work_email: str
    phone: str | None
    department_id: uuid.UUID | None
    designation_id: uuid.UUID | None
    manager_id: uuid.UUID | None
    join_date: date
    status: str
    employment_type: str
    user_id: uuid.UUID | None


class HolidayIn(BaseModel):
    date: date
    description: str = Field(min_length=1, max_length=200)


class HolidayListIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    state_code: str | None = None


class HolidayOut(HolidayIn):
    model_config = {"from_attributes": True}
    id: uuid.UUID


class HolidayListOut(HolidayListIn):
    model_config = {"from_attributes": True}
    id: uuid.UUID
    holidays: list[HolidayOut]


class LeaveTypeIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    exclude_weekends: bool = True
    exclude_holidays: bool = True
    accrual_frequency: AccrualFrequency = "none"


class LeaveTypeOut(LeaveTypeIn):
    model_config = {"from_attributes": True}
    id: uuid.UUID


class LeavePolicyTypeIn(BaseModel):
    leave_type_id: uuid.UUID
    annual_days: Decimal = Field(gt=0, multiple_of=0.5)


class LeavePolicyIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    types: list[LeavePolicyTypeIn] = Field(min_length=1)


class LeavePolicyTypeOut(BaseModel):
    model_config = {"from_attributes": True}
    leave_type_id: uuid.UUID
    annual_days: Decimal


class LeavePolicyOut(BaseModel):
    model_config = {"from_attributes": True}
    id: uuid.UUID
    name: str
    types: list[LeavePolicyTypeOut]


class ApplyPolicyIn(BaseModel):
    employee_id: uuid.UUID
    financial_year: str = Field(min_length=1, max_length=10)


class LeaveAllocationOut(BaseModel):
    model_config = {"from_attributes": True}
    id: uuid.UUID
    employee_id: uuid.UUID
    leave_type_id: uuid.UUID
    financial_year: str
    allocated_days: Decimal
    last_accrued_on: date | None


class LeaveApplicationIn(BaseModel):
    employee_id: uuid.UUID
    leave_type_id: uuid.UUID
    start_date: date
    end_date: date
    half_day: bool = False
    reason_code: ReasonCode | None = None
    comment: str | None = Field(default=None, max_length=1000)


class LeaveApplicationOut(BaseModel):
    model_config = {"from_attributes": True}
    id: uuid.UUID
    employee_id: uuid.UUID
    leave_type_id: uuid.UUID
    start_date: date
    end_date: date
    days: Decimal
    half_day: bool
    status: str
    reason_code: str | None
    comment: str | None
    approver_id: uuid.UUID | None


class LeaveBalanceOut(BaseModel):
    leave_type_id: uuid.UUID
    balance_days: Decimal


class AttendanceMarkIn(BaseModel):
    employee_id: uuid.UUID
    date: date
    status: str


class AttendanceOut(BaseModel):
    model_config = {"from_attributes": True}
    id: uuid.UUID
    employee_id: uuid.UUID
    date: date
    status: str
    # Set when a leave approval created this row -- the UI uses this to grey
    # out manual editing instead of letting it drift from the leave record.
    leave_application_id: uuid.UUID | None


class ExpenseClaimLineIn(BaseModel):
    description: str = Field(min_length=1, max_length=200)
    amount_paise: int = Field(gt=0)
    category: str = Field(min_length=1, max_length=50)
    attachment_url: str | None = None


class ExpenseClaimIn(BaseModel):
    employee_id: uuid.UUID
    lines: list[ExpenseClaimLineIn] = Field(min_length=1)


class ExpenseClaimLineOut(BaseModel):
    model_config = {"from_attributes": True}
    id: uuid.UUID
    description: str
    amount_paise: int
    category: str
    attachment_url: str | None


class ExpenseClaimOut(BaseModel):
    model_config = {"from_attributes": True}
    id: uuid.UUID
    employee_id: uuid.UUID
    status: str
    total_paise: int
    outstanding_paise: int
    approver_id: uuid.UUID | None
    lines: list[ExpenseClaimLineOut]


class ReimbursementIn(BaseModel):
    amount_paise: int = Field(gt=0)
    method: str = Field(min_length=1, max_length=50)


class ReimbursementOut(BaseModel):
    model_config = {"from_attributes": True}
    id: uuid.UUID
    claim_id: uuid.UUID
    amount_paise: int
    method: str
    paid_at: datetime
