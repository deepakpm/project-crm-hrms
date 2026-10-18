import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import record as audit_record
from app.deps import CurrentUser, get_current_user, get_tenant_db, require_roles
from app.modules.people.models import (
    Holiday,
    HolidayList,
    LeaveAllocation,
    LeaveApplication,
    LeavePolicy,
    LeavePolicyType,
    LeaveType,
)
from app.modules.people.schemas import (
    ApplyPolicyIn,
    HolidayIn,
    HolidayListIn,
    HolidayListOut,
    LeaveAllocationOut,
    LeaveApplicationIn,
    LeaveApplicationOut,
    LeaveBalanceOut,
    LeavePolicyIn,
    LeavePolicyOut,
    LeaveTypeIn,
    LeaveTypeOut,
)
from app.modules.people.service import (
    accrue_leave_allocation,
    apply_leave_policy,
    approve_leave_application,
    can_act_as_employee,
    can_approve,
    cancel_leave_application,
    get_employee_or_404,
    leave_balance,
    reject_leave_application,
    scoped_employee_ids,
    submit_leave_application,
)

router = APIRouter(prefix="/people/leave", tags=["people"])


def _get_application_or_404(db: Session, application_id: uuid.UUID) -> LeaveApplication:
    application = db.get(LeaveApplication, application_id)
    if application is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="application not found")
    return application


def _audit_state_change(db: Session, current_user: CurrentUser, application_id: uuid.UUID) -> None:
    audit_record(
        db,
        current_user.tenant_id,
        current_user.user_id,
        "state_change",
        "leave_application",
        application_id,
    )


# --- holiday lists ---


@router.post("/holiday-lists", response_model=HolidayListOut, status_code=status.HTTP_201_CREATED)
def create_holiday_list(
    body: HolidayListIn,
    current_user: CurrentUser = Depends(require_roles("owner", "hr")),
    db: Session = Depends(get_tenant_db),
) -> HolidayList:
    holiday_list = HolidayList(tenant_id=current_user.tenant_id, **body.model_dump())
    db.add(holiday_list)
    db.flush()
    return holiday_list


@router.get("/holiday-lists", response_model=list[HolidayListOut])
def list_holiday_lists(db: Session = Depends(get_tenant_db)) -> list[HolidayList]:
    return list(db.scalars(select(HolidayList)))


@router.post(
    "/holiday-lists/{holiday_list_id}/holidays",
    response_model=HolidayListOut,
    status_code=status.HTTP_201_CREATED,
)
def add_holiday(
    holiday_list_id: uuid.UUID,
    body: HolidayIn,
    current_user: CurrentUser = Depends(require_roles("owner", "hr")),
    db: Session = Depends(get_tenant_db),
) -> HolidayList:
    holiday_list = db.get(HolidayList, holiday_list_id)
    if holiday_list is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="holiday list not found")
    db.add(
        Holiday(
            tenant_id=current_user.tenant_id, holiday_list_id=holiday_list.id, **body.model_dump()
        )
    )
    db.flush()
    db.refresh(holiday_list)
    return holiday_list


# --- leave types ---


@router.post("/types", response_model=LeaveTypeOut, status_code=status.HTTP_201_CREATED)
def create_leave_type(
    body: LeaveTypeIn,
    current_user: CurrentUser = Depends(require_roles("owner", "hr")),
    db: Session = Depends(get_tenant_db),
) -> LeaveType:
    leave_type = LeaveType(tenant_id=current_user.tenant_id, **body.model_dump())
    db.add(leave_type)
    db.flush()
    return leave_type


@router.get("/types", response_model=list[LeaveTypeOut])
def list_leave_types(db: Session = Depends(get_tenant_db)) -> list[LeaveType]:
    return list(db.scalars(select(LeaveType)))


# --- leave policies ---


@router.post("/policies", response_model=LeavePolicyOut, status_code=status.HTTP_201_CREATED)
def create_leave_policy(
    body: LeavePolicyIn,
    current_user: CurrentUser = Depends(require_roles("owner", "hr")),
    db: Session = Depends(get_tenant_db),
) -> LeavePolicy:
    policy = LeavePolicy(tenant_id=current_user.tenant_id, name=body.name)
    db.add(policy)
    db.flush()
    for policy_type in body.types:
        db.add(
            LeavePolicyType(
                tenant_id=current_user.tenant_id,
                policy_id=policy.id,
                leave_type_id=policy_type.leave_type_id,
                annual_days=policy_type.annual_days,
            )
        )
    db.flush()
    db.refresh(policy)
    return policy


@router.get("/policies", response_model=list[LeavePolicyOut])
def list_leave_policies(db: Session = Depends(get_tenant_db)) -> list[LeavePolicy]:
    return list(db.scalars(select(LeavePolicy)))


@router.post("/policies/{policy_id}/apply", response_model=list[LeaveAllocationOut])
def apply_policy(
    policy_id: uuid.UUID,
    body: ApplyPolicyIn,
    current_user: CurrentUser = Depends(require_roles("owner", "hr")),
    db: Session = Depends(get_tenant_db),
) -> list[LeaveAllocation]:
    policy = db.get(LeavePolicy, policy_id)
    if policy is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="policy not found")
    get_employee_or_404(db, body.employee_id)
    return apply_leave_policy(
        db, current_user.tenant_id, policy, body.employee_id, body.financial_year
    )


@router.post("/allocations/{allocation_id}/accrue", response_model=LeaveAllocationOut)
def accrue_allocation(
    allocation_id: uuid.UUID,
    current_user: CurrentUser = Depends(require_roles("owner", "hr")),
    db: Session = Depends(get_tenant_db),
) -> LeaveAllocation:
    allocation = db.get(LeaveAllocation, allocation_id)
    if allocation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="allocation not found")
    entry = accrue_leave_allocation(db, allocation)
    if entry is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="nothing to accrue -- not accruing, cap reached, or already run this period",
        )
    return allocation


@router.get("/allocations/{employee_id}", response_model=list[LeaveAllocationOut])
def list_allocations(
    employee_id: uuid.UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_tenant_db),
) -> list[LeaveAllocation]:
    scoped_ids = scoped_employee_ids(db, current_user.role, current_user.user_id)
    if scoped_ids is not None and employee_id not in scoped_ids:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="not authorized")
    get_employee_or_404(db, employee_id)
    query = select(LeaveAllocation).where(LeaveAllocation.employee_id == employee_id)
    return list(db.scalars(query))


# --- balances ---


@router.get("/balances/{employee_id}", response_model=list[LeaveBalanceOut])
def get_balances(
    employee_id: uuid.UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_tenant_db),
) -> list[LeaveBalanceOut]:
    scoped_ids = scoped_employee_ids(db, current_user.role, current_user.user_id)
    if scoped_ids is not None and employee_id not in scoped_ids:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="not authorized")
    get_employee_or_404(db, employee_id)
    leave_type_ids = db.scalars(select(LeaveType.id))
    return [
        LeaveBalanceOut(leave_type_id=lt_id, balance_days=leave_balance(db, employee_id, lt_id))
        for lt_id in leave_type_ids
    ]


# --- applications ---


@router.post(
    "/applications", response_model=LeaveApplicationOut, status_code=status.HTTP_201_CREATED
)
def create_application(
    body: LeaveApplicationIn,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_tenant_db),
) -> LeaveApplication:
    if not can_act_as_employee(db, current_user.role, current_user.user_id, body.employee_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="not authorized")
    get_employee_or_404(db, body.employee_id)
    application = LeaveApplication(
        tenant_id=current_user.tenant_id, status="draft", days=0, **body.model_dump()
    )
    db.add(application)
    db.flush()
    return application


@router.get("/applications", response_model=list[LeaveApplicationOut])
def list_applications(
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_tenant_db),
) -> list[LeaveApplication]:
    employee_ids = scoped_employee_ids(db, current_user.role, current_user.user_id)
    query = select(LeaveApplication)
    if employee_ids is not None:
        if not employee_ids:
            return []
        query = query.where(LeaveApplication.employee_id.in_(employee_ids))
    return list(db.scalars(query))


@router.get("/applications/{application_id}", response_model=LeaveApplicationOut)
def get_application(
    application_id: uuid.UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_tenant_db),
) -> LeaveApplication:
    application = _get_application_or_404(db, application_id)
    employee = get_employee_or_404(db, application.employee_id)
    can_view = can_act_as_employee(
        db, current_user.role, current_user.user_id, application.employee_id
    ) or can_approve(db, current_user.role, current_user.user_id, employee)
    if not can_view:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="not authorized")
    return application


@router.post("/applications/{application_id}/submit", response_model=LeaveApplicationOut)
def submit_application(
    application_id: uuid.UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_tenant_db),
) -> LeaveApplication:
    application = _get_application_or_404(db, application_id)
    allowed = can_act_as_employee(
        db, current_user.role, current_user.user_id, application.employee_id
    )
    if not allowed:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="not authorized")
    result = submit_leave_application(db, application)
    _audit_state_change(db, current_user, result.id)
    return result


@router.post("/applications/{application_id}/approve", response_model=LeaveApplicationOut)
def approve_application(
    application_id: uuid.UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_tenant_db),
) -> LeaveApplication:
    application = _get_application_or_404(db, application_id)
    employee = get_employee_or_404(db, application.employee_id)
    if not can_approve(db, current_user.role, current_user.user_id, employee):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="not authorized")
    result = approve_leave_application(db, application, current_user.user_id)
    _audit_state_change(db, current_user, result.id)
    return result


@router.post("/applications/{application_id}/reject", response_model=LeaveApplicationOut)
def reject_application(
    application_id: uuid.UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_tenant_db),
) -> LeaveApplication:
    application = _get_application_or_404(db, application_id)
    employee = get_employee_or_404(db, application.employee_id)
    if not can_approve(db, current_user.role, current_user.user_id, employee):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="not authorized")
    result = reject_leave_application(db, application, current_user.user_id)
    _audit_state_change(db, current_user, result.id)
    return result


@router.post("/applications/{application_id}/cancel", response_model=LeaveApplicationOut)
def cancel_application(
    application_id: uuid.UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_tenant_db),
) -> LeaveApplication:
    application = _get_application_or_404(db, application_id)
    allowed = can_act_as_employee(
        db, current_user.role, current_user.user_id, application.employee_id
    )
    if not allowed:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="not authorized")
    result = cancel_leave_application(db, application)
    _audit_state_change(db, current_user, result.id)
    return result
