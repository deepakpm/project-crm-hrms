import uuid

# Aliased: this module has columns literally named `date` (Holiday, Attendance).
# SQLAlchemy's Mapped[] annotation resolver reads the class's own namespace
# first, so `Mapped[_date]` on a column named `date` resolves to the column
# itself, not datetime.date -- aliasing the import sidesteps the collision.
from datetime import date as _date
from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, ForeignKey, Numeric, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

# Same declarative Base as the rest of the app -- one metadata, one Alembic
# target, consistent with how every other module-ish file (ledger, pdf) works.
from app.models import Base


class Department(Base):
    __tablename__ = "department"
    __table_args__ = (UniqueConstraint("tenant_id", "name", name="uq_department_tenant_name"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenant.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)


class Designation(Base):
    __tablename__ = "designation"
    __table_args__ = (UniqueConstraint("tenant_id", "name", name="uq_designation_tenant_name"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenant.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)


class Employee(Base):
    __tablename__ = "employee"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_employee_tenant_code"),
        CheckConstraint("status in ('active','inactive')", name="ck_employee_status"),
        CheckConstraint(
            "employment_type in ('full_time','part_time','contract','intern')",
            name="ck_employee_employment_type",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenant.id"), nullable=False
    )
    code: Mapped[str] = mapped_column(nullable=False)
    name: Mapped[str] = mapped_column(nullable=False)
    work_email: Mapped[str] = mapped_column(nullable=False)
    phone: Mapped[str | None] = mapped_column(nullable=True)
    department_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("department.id"), nullable=True
    )
    designation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("designation.id"), nullable=True
    )
    manager_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("employee.id"), nullable=True
    )
    join_date: Mapped[_date] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(nullable=False, default="active")
    employment_type: Mapped[str] = mapped_column(nullable=False, default="full_time")
    # Nullable: contractors/employees without self-service login are still valid rows.
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("app_user.id"), unique=True, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)


class HolidayList(Base):
    __tablename__ = "holiday_list"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenant.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(nullable=False)
    state_code: Mapped[str | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)

    holidays: Mapped[list["Holiday"]] = relationship(
        back_populates="holiday_list", cascade="all, delete-orphan"
    )


class Holiday(Base):
    __tablename__ = "holiday"
    __table_args__ = (UniqueConstraint("holiday_list_id", "date", name="uq_holiday_list_date"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenant.id"), nullable=False
    )
    holiday_list_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("holiday_list.id"), nullable=False
    )
    date: Mapped[_date] = mapped_column(nullable=False)
    description: Mapped[str] = mapped_column(nullable=False)

    holiday_list: Mapped["HolidayList"] = relationship(back_populates="holidays")


class LeaveType(Base):
    __tablename__ = "leave_type"
    __table_args__ = (UniqueConstraint("tenant_id", "name", name="uq_leave_type_tenant_name"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenant.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(nullable=False)
    exclude_weekends: Mapped[bool] = mapped_column(nullable=False, default=True)
    exclude_holidays: Mapped[bool] = mapped_column(nullable=False, default=True)
    # 'none' = allocation credits the full amount upfront (existing behaviour).
    # 'monthly'/'yearly' = credited incrementally via the manual accrual-run
    # endpoint -- no cron infra in this stack, so accrual is operator-triggered.
    accrual_frequency: Mapped[str] = mapped_column(nullable=False, default="none")
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)


class LeavePolicy(Base):
    __tablename__ = "leave_policy"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenant.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)

    types: Mapped[list["LeavePolicyType"]] = relationship(
        back_populates="policy", cascade="all, delete-orphan"
    )


class LeavePolicyType(Base):
    __tablename__ = "leave_policy_type"
    __table_args__ = (
        UniqueConstraint("policy_id", "leave_type_id", name="uq_leave_policy_type"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenant.id"), nullable=False
    )
    policy_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("leave_policy.id"), nullable=False
    )
    leave_type_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("leave_type.id"), nullable=False
    )
    annual_days: Mapped[Decimal] = mapped_column(Numeric(6, 1), nullable=False)

    policy: Mapped["LeavePolicy"] = relationship(back_populates="types")


class LeaveAllocation(Base):
    __tablename__ = "leave_allocation"
    __table_args__ = (
        UniqueConstraint(
            "employee_id", "leave_type_id", "financial_year", name="uq_leave_allocation"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenant.id"), nullable=False
    )
    employee_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("employee.id"), nullable=False
    )
    leave_type_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("leave_type.id"), nullable=False
    )
    financial_year: Mapped[str] = mapped_column(nullable=False)
    allocated_days: Mapped[Decimal] = mapped_column(Numeric(6, 1), nullable=False)
    # Set by the manual accrual-run endpoint; None until the first run.
    last_accrued_on: Mapped[_date | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)


class LeaveApplication(Base):
    __tablename__ = "leave_application"
    __table_args__ = (
        CheckConstraint(
            "status in ('draft','submitted','approved','rejected','cancelled')",
            name="ck_leave_application_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenant.id"), nullable=False
    )
    employee_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("employee.id"), nullable=False
    )
    leave_type_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("leave_type.id"), nullable=False
    )
    start_date: Mapped[_date] = mapped_column(nullable=False)
    end_date: Mapped[_date] = mapped_column(nullable=False)
    days: Mapped[Decimal] = mapped_column(Numeric(6, 1), nullable=False, default=0)
    half_day: Mapped[bool] = mapped_column(nullable=False, default=False)
    status: Mapped[str] = mapped_column(nullable=False, default="draft")
    reason_code: Mapped[str | None] = mapped_column(nullable=True)
    comment: Mapped[str | None] = mapped_column(nullable=True)
    approver_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("app_user.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
    decided_at: Mapped[datetime | None] = mapped_column(nullable=True)


class LeaveLedgerEntry(Base):
    """Append-only; see the 0004 migration's trigger (reuses the same
    forbid_ledger_mutation() function the financial ledger already defined)."""

    __tablename__ = "leave_ledger_entry"
    __table_args__ = (
        CheckConstraint(
            "source_type in ('allocation','application','reversal')",
            name="ck_leave_ledger_entry_source_type",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenant.id"), nullable=False
    )
    employee_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("employee.id"), nullable=False
    )
    leave_type_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("leave_type.id"), nullable=False
    )
    source_type: Mapped[str] = mapped_column(nullable=False)
    source_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    days_delta: Mapped[Decimal] = mapped_column(Numeric(6, 1), nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)


class Attendance(Base):
    __tablename__ = "attendance"
    __table_args__ = (
        UniqueConstraint("employee_id", "date", name="uq_attendance_employee_date"),
        CheckConstraint(
            "status in ('present','absent','half_day','on_leave','holiday')",
            name="ck_attendance_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenant.id"), nullable=False
    )
    employee_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("employee.id"), nullable=False
    )
    date: Mapped[_date] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(nullable=False)
    # Set when this row was auto-created by a leave approval, so cancellation
    # can remove exactly the rows it created and never a manual mark.
    leave_application_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("leave_application.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)


class ExpenseClaim(Base):
    __tablename__ = "expense_claim"
    __table_args__ = (
        CheckConstraint(
            "status in ('draft','submitted','approved','rejected')",
            name="ck_expense_claim_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenant.id"), nullable=False
    )
    employee_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("employee.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(nullable=False, default="draft")
    total_paise: Mapped[int] = mapped_column(nullable=False, default=0)
    approver_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("app_user.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
    decided_at: Mapped[datetime | None] = mapped_column(nullable=True)

    lines: Mapped[list["ExpenseClaimLine"]] = relationship(
        back_populates="claim", cascade="all, delete-orphan"
    )


class ExpenseClaimLine(Base):
    __tablename__ = "expense_claim_line"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenant.id"), nullable=False
    )
    claim_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("expense_claim.id"), nullable=False
    )
    description: Mapped[str] = mapped_column(nullable=False)
    amount_paise: Mapped[int] = mapped_column(nullable=False)
    category: Mapped[str] = mapped_column(nullable=False)
    # Pasted URL, not an upload: no file-storage infra exists yet in this app.
    attachment_url: Mapped[str | None] = mapped_column(nullable=True)

    claim: Mapped["ExpenseClaim"] = relationship(back_populates="lines")


class ExpenseReimbursement(Base):
    """Deliberately separate from the core `payment` table (which is FK'd
    NOT NULL to invoice) rather than widening a core table to be polymorphic --
    keeps the people module's own concern inside its own package."""

    __tablename__ = "expense_reimbursement"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenant.id"), nullable=False
    )
    claim_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("expense_claim.id"), nullable=False
    )
    amount_paise: Mapped[int] = mapped_column(nullable=False)
    method: Mapped[str] = mapped_column(nullable=False)
    paid_at: Mapped[datetime] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
