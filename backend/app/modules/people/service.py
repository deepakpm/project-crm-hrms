"""Business logic for the people module. Internal to this package -- other
modules reach the people module only through people.public, never this file."""

import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ledger import (
    CASH_AND_BANK,
    EMPLOYEE_REIMBURSEMENTS_PAYABLE,
    OPERATING_EXPENSES,
    post_journal,
)
from app.modules.people.models import (
    Attendance,
    Employee,
    ExpenseClaim,
    ExpenseReimbursement,
    Holiday,
    LeaveAllocation,
    LeaveApplication,
    LeaveLedgerEntry,
    LeavePolicy,
    LeaveType,
)


def can_act_as_employee(db: Session, role: str, user_id: uuid.UUID, employee_id: uuid.UUID) -> bool:
    """True if this user may submit/cancel/apply as this employee: owner/hr
    always can, otherwise only the employee acting as themselves."""
    if role in ("owner", "hr"):
        return True
    employee = db.get(Employee, employee_id)
    return employee is not None and employee.user_id == user_id


def scoped_employee_ids(
    db: Session, role: str, user_id: uuid.UUID
) -> list[uuid.UUID] | None:
    """None means "no scoping needed, see everything" (owner/hr/accountant --
    accountant reads everything but writes nothing, gated separately by
    require_roles on the write endpoints). Otherwise the list of employee ids
    this user may act on: self, or self+direct-reports for a manager."""
    if role in ("owner", "hr", "accountant"):
        return None
    own_id = db.scalar(select(Employee.id).where(Employee.user_id == user_id))
    if own_id is None:
        return []
    if role == "manager":
        reports = list(db.scalars(select(Employee.id).where(Employee.manager_id == own_id)))
        return [own_id, *reports]
    return [own_id]


def get_employee_or_404(db: Session, employee_id: uuid.UUID) -> Employee:
    employee = db.get(Employee, employee_id)
    if employee is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="employee not found")
    return employee


def _working_days(
    db: Session, leave_type: LeaveType, start_date: date, end_date: date
) -> list[date]:
    """Calendar days in range, dropping weekends/holidays per the leave
    type's own flags -- configuration as data, not a hard-coded rule."""
    holiday_dates: set[date] = set()
    if leave_type.exclude_holidays:
        holiday_dates = set(
            db.scalars(select(Holiday.date).where(Holiday.date.between(start_date, end_date)))
        )

    out = []
    current = start_date
    while current <= end_date:
        is_weekend = leave_type.exclude_weekends and current.weekday() >= 5
        is_holiday = current in holiday_dates
        if not is_weekend and not is_holiday:
            out.append(current)
        current += timedelta(days=1)
    return out


def compute_leave_days(
    db: Session, leave_type: LeaveType, start_date: date, end_date: date, half_day: bool = False
) -> Decimal:
    """half_day only applies to a single-day application (enforced by the
    half_day_single_day CHECK constraint) and halves that one day's count."""
    working_days = _working_days(db, leave_type, start_date, end_date)
    if half_day:
        return Decimal("0.5") if working_days else Decimal("0")
    return Decimal(len(working_days))


def leave_balance(db: Session, employee_id: uuid.UUID, leave_type_id: uuid.UUID) -> Decimal:
    rows = db.scalars(
        select(LeaveLedgerEntry.days_delta).where(
            LeaveLedgerEntry.employee_id == employee_id,
            LeaveLedgerEntry.leave_type_id == leave_type_id,
        )
    )
    return sum(rows, Decimal("0"))


def has_overlapping_leave(
    db: Session,
    employee_id: uuid.UUID,
    start_date: date,
    end_date: date,
    exclude_application_id: uuid.UUID | None = None,
) -> bool:
    query = select(LeaveApplication).where(
        LeaveApplication.employee_id == employee_id,
        LeaveApplication.status.in_(("submitted", "approved")),
        LeaveApplication.start_date <= end_date,
        LeaveApplication.end_date >= start_date,
    )
    if exclude_application_id is not None:
        query = query.where(LeaveApplication.id != exclude_application_id)
    return db.scalar(query) is not None


def submit_leave_application(db: Session, application: LeaveApplication) -> LeaveApplication:
    if application.status != "draft":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="only a draft application can be submitted"
        )
    if has_overlapping_leave(
        db, application.employee_id, application.start_date, application.end_date, application.id
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="overlaps an existing leave application"
        )

    leave_type = db.get(LeaveType, application.leave_type_id)
    assert leave_type is not None
    days = compute_leave_days(
        db, leave_type, application.start_date, application.end_date, application.half_day
    )
    if days == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="selected range has no working days -- entirely weekend/holiday",
        )

    balance = leave_balance(db, application.employee_id, application.leave_type_id)
    if days > balance:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"insufficient leave balance: have {balance}, need {days}",
        )

    application.days = days
    application.status = "submitted"
    db.flush()
    return application


def can_approve(
    db: Session, approver_role: str, approver_user_id: uuid.UUID, employee: Employee
) -> bool:
    if approver_role in ("owner", "hr"):
        return True
    if employee.manager_id is None:
        return False
    manager = db.get(Employee, employee.manager_id)
    return manager is not None and manager.user_id == approver_user_id


def approve_leave_application(
    db: Session, application: LeaveApplication, approver_app_user_id: uuid.UUID
) -> LeaveApplication:
    if application.status != "submitted":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="only a submitted application can be approved",
        )
    db.add(
        LeaveLedgerEntry(
            tenant_id=application.tenant_id,
            employee_id=application.employee_id,
            leave_type_id=application.leave_type_id,
            source_type="application",
            source_id=application.id,
            days_delta=-application.days,
        )
    )
    application.status = "approved"
    application.approver_id = approver_app_user_id
    application.decided_at = datetime.now(UTC)
    db.flush()

    leave_type = db.get(LeaveType, application.leave_type_id)
    assert leave_type is not None
    for day in _working_days(db, leave_type, application.start_date, application.end_date):
        existing = db.scalar(
            select(Attendance).where(
                Attendance.employee_id == application.employee_id, Attendance.date == day
            )
        )
        if existing is None:
            db.add(
                Attendance(
                    tenant_id=application.tenant_id,
                    employee_id=application.employee_id,
                    date=day,
                    status="on_leave",
                    leave_application_id=application.id,
                )
            )
        else:
            existing.status = "on_leave"
            existing.leave_application_id = application.id
    db.flush()
    return application


def reject_leave_application(
    db: Session, application: LeaveApplication, approver_app_user_id: uuid.UUID
) -> LeaveApplication:
    if application.status != "submitted":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="only a submitted application can be rejected",
        )
    application.status = "rejected"
    application.approver_id = approver_app_user_id
    application.decided_at = datetime.now(UTC)
    db.flush()
    return application


def cancel_leave_application(db: Session, application: LeaveApplication) -> LeaveApplication:
    if application.status != "approved":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="only an approved application can be cancelled",
        )
    db.add(
        LeaveLedgerEntry(
            tenant_id=application.tenant_id,
            employee_id=application.employee_id,
            leave_type_id=application.leave_type_id,
            source_type="reversal",
            source_id=application.id,
            days_delta=application.days,
        )
    )
    application.status = "cancelled"
    db.flush()

    # Only remove rows this application created -- never a manual mark that
    # happens to share a date (e.g. half-day present + half-day leave edge cases).
    for row in db.scalars(
        select(Attendance).where(Attendance.leave_application_id == application.id)
    ):
        db.delete(row)
    db.flush()
    return application


def apply_leave_policy(
    db: Session,
    tenant_id: uuid.UUID,
    policy: LeavePolicy,
    employee_id: uuid.UUID,
    financial_year: str,
) -> list[LeaveAllocation]:
    existing = set(
        db.scalars(
            select(LeaveAllocation.leave_type_id).where(
                LeaveAllocation.employee_id == employee_id,
                LeaveAllocation.financial_year == financial_year,
            )
        )
    )
    allocations = []
    for policy_type in policy.types:
        if policy_type.leave_type_id in existing:
            continue  # already allocated this FY -- applying a policy twice is a no-op
        allocation = LeaveAllocation(
            tenant_id=tenant_id,
            employee_id=employee_id,
            leave_type_id=policy_type.leave_type_id,
            financial_year=financial_year,
            allocated_days=policy_type.annual_days,
        )
        db.add(allocation)
        db.flush()

        leave_type = db.get(LeaveType, policy_type.leave_type_id)
        assert leave_type is not None
        if leave_type.accrual_frequency == "none":
            # Lump-sum: credit the full cap now, same as before this feature existed.
            db.add(
                LeaveLedgerEntry(
                    tenant_id=tenant_id,
                    employee_id=employee_id,
                    leave_type_id=policy_type.leave_type_id,
                    source_type="allocation",
                    source_id=allocation.id,
                    days_delta=policy_type.annual_days,
                )
            )
        # else: accruing type -- balance starts at 0, credited incrementally
        # by accrue_leave_allocation() (owner/hr-triggered; no cron in this stack).
        allocations.append(allocation)
    db.flush()
    return allocations


def accrue_leave_allocation(db: Session, allocation: LeaveAllocation) -> LeaveLedgerEntry | None:
    """One accrual installment for this allocation, idempotent per day.
    Returns None (no-op) if the type doesn't accrue, the cap is already
    reached, or this period was already credited."""
    leave_type = db.get(LeaveType, allocation.leave_type_id)
    assert leave_type is not None
    if leave_type.accrual_frequency == "none":
        return None

    today = datetime.now(UTC).date()
    periods_per_year = 12 if leave_type.accrual_frequency == "monthly" else 1
    installment = (allocation.allocated_days / periods_per_year).quantize(Decimal("0.1"))

    already_credited = sum(
        db.scalars(
            select(LeaveLedgerEntry.days_delta).where(
                LeaveLedgerEntry.employee_id == allocation.employee_id,
                LeaveLedgerEntry.leave_type_id == allocation.leave_type_id,
                LeaveLedgerEntry.source_type == "allocation",
                LeaveLedgerEntry.source_id == allocation.id,
            )
        ),
        Decimal("0"),
    )
    remaining_cap = allocation.allocated_days - already_credited
    if remaining_cap <= 0:
        return None

    if allocation.last_accrued_on is not None:
        same_month = (
            allocation.last_accrued_on.year == today.year
            and allocation.last_accrued_on.month == today.month
        )
        same_year = allocation.last_accrued_on.year == today.year
        if (periods_per_year == 12 and same_month) or (periods_per_year == 1 and same_year):
            return None  # already accrued this period

    credit = min(installment, remaining_cap)
    entry = LeaveLedgerEntry(
        tenant_id=allocation.tenant_id,
        employee_id=allocation.employee_id,
        leave_type_id=allocation.leave_type_id,
        source_type="allocation",
        source_id=allocation.id,
        days_delta=credit,
    )
    db.add(entry)
    allocation.last_accrued_on = today
    db.flush()
    return entry


def submit_expense_claim(db: Session, claim: ExpenseClaim) -> ExpenseClaim:
    if claim.status != "draft":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="only a draft claim can be submitted"
        )
    claim.total_paise = sum(line.amount_paise for line in claim.lines)
    claim.status = "submitted"
    db.flush()
    return claim


def approve_expense_claim(
    db: Session, claim: ExpenseClaim, approver_app_user_id: uuid.UUID
) -> ExpenseClaim:
    if claim.status != "submitted":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="only a submitted claim can be approved"
        )
    claim.status = "approved"
    claim.approver_id = approver_app_user_id
    claim.decided_at = datetime.now(UTC)
    db.flush()

    post_journal(
        db,
        claim.tenant_id,
        "expense_claim",
        claim.id,
        claim.decided_at.date(),
        f"Expense claim {claim.id} approved",
        lines=[
            (OPERATING_EXPENSES, claim.total_paise, 0),
            (EMPLOYEE_REIMBURSEMENTS_PAYABLE, 0, claim.total_paise),
        ],
    )
    db.flush()
    return claim


def reject_expense_claim(
    db: Session, claim: ExpenseClaim, approver_app_user_id: uuid.UUID
) -> ExpenseClaim:
    if claim.status != "submitted":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="only a submitted claim can be rejected"
        )
    claim.status = "rejected"
    claim.approver_id = approver_app_user_id
    claim.decided_at = datetime.now(UTC)
    db.flush()
    return claim


def expense_claim_outstanding_paise(db: Session, claim: ExpenseClaim) -> int:
    if claim.status != "approved":
        return 0
    already_paid = sum(
        db.scalars(
            select(ExpenseReimbursement.amount_paise).where(
                ExpenseReimbursement.claim_id == claim.id
            )
        )
    )
    return claim.total_paise - already_paid


def reimburse_expense_claim(
    db: Session, claim: ExpenseClaim, amount_paise: int, method: str
) -> ExpenseReimbursement:
    if claim.status != "approved":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="only an approved claim can be reimbursed"
        )
    outstanding = expense_claim_outstanding_paise(db, claim)
    if amount_paise > outstanding:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"amount exceeds outstanding balance of {outstanding} paise",
        )

    paid_at = datetime.now(UTC)
    reimbursement = ExpenseReimbursement(
        tenant_id=claim.tenant_id,
        claim_id=claim.id,
        amount_paise=amount_paise,
        method=method,
        paid_at=paid_at,
    )
    db.add(reimbursement)
    db.flush()

    post_journal(
        db,
        claim.tenant_id,
        "expense_reimbursement",
        reimbursement.id,
        paid_at.date(),
        f"Reimbursement for expense claim {claim.id}",
        lines=[
            (EMPLOYEE_REIMBURSEMENTS_PAYABLE, amount_paise, 0),
            (CASH_AND_BANK, 0, amount_paise),
        ],
    )
    db.flush()
    return reimbursement


def mark_attendance(
    db: Session,
    tenant_id: uuid.UUID,
    employee_id: uuid.UUID,
    mark_date: date,
    attendance_status: str,
) -> Attendance:
    existing = db.scalar(
        select(Attendance).where(
            Attendance.employee_id == employee_id, Attendance.date == mark_date
        )
    )
    if existing is not None:
        if existing.leave_application_id is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="this day is set by an approved leave application -- cancel it to change",
            )
        existing.status = attendance_status
        db.flush()
        return existing
    attendance = Attendance(
        tenant_id=tenant_id, employee_id=employee_id, date=mark_date, status=attendance_status
    )
    db.add(attendance)
    db.flush()
    return attendance


