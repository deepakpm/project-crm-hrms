import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import record as audit_record
from app.deps import CurrentUser, get_current_user, get_tenant_db, require_roles
from app.modules.people.models import ExpenseClaim, ExpenseClaimLine, ExpenseReimbursement
from app.modules.people.schemas import (
    ExpenseClaimIn,
    ExpenseClaimOut,
    ReimbursementIn,
    ReimbursementOut,
)
from app.modules.people.service import (
    approve_expense_claim,
    can_act_as_employee,
    can_approve,
    expense_claim_outstanding_paise,
    get_employee_or_404,
    reimburse_expense_claim,
    reject_expense_claim,
    scoped_employee_ids,
    submit_expense_claim,
)

router = APIRouter(prefix="/people/expenses", tags=["people"])


def _get_claim_or_404(db: Session, claim_id: uuid.UUID) -> ExpenseClaim:
    claim = db.get(ExpenseClaim, claim_id)
    if claim is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="expense claim not found")
    return claim


def _with_outstanding(db: Session, claim: ExpenseClaim) -> ExpenseClaim:
    claim.outstanding_paise = expense_claim_outstanding_paise(db, claim)  # type: ignore[attr-defined]
    return claim


@router.post("", response_model=ExpenseClaimOut, status_code=status.HTTP_201_CREATED)
def create_claim(
    body: ExpenseClaimIn,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_tenant_db),
) -> ExpenseClaim:
    if not can_act_as_employee(db, current_user.role, current_user.user_id, body.employee_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="not authorized")
    get_employee_or_404(db, body.employee_id)

    claim = ExpenseClaim(
        tenant_id=current_user.tenant_id, employee_id=body.employee_id, status="draft"
    )
    db.add(claim)
    db.flush()
    for line in body.lines:
        db.add(
            ExpenseClaimLine(
                tenant_id=current_user.tenant_id, claim_id=claim.id, **line.model_dump()
            )
        )
    db.flush()
    db.refresh(claim)
    return _with_outstanding(db, claim)


@router.get("", response_model=list[ExpenseClaimOut])
def list_claims(
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_tenant_db),
) -> list[ExpenseClaim]:
    scoped_ids = scoped_employee_ids(db, current_user.role, current_user.user_id)
    query = select(ExpenseClaim)
    if scoped_ids is not None:
        if not scoped_ids:
            return []
        query = query.where(ExpenseClaim.employee_id.in_(scoped_ids))
    return [_with_outstanding(db, c) for c in db.scalars(query)]


@router.get("/{claim_id}", response_model=ExpenseClaimOut)
def get_claim(
    claim_id: uuid.UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_tenant_db),
) -> ExpenseClaim:
    claim = _get_claim_or_404(db, claim_id)
    employee = get_employee_or_404(db, claim.employee_id)
    can_view = can_act_as_employee(
        db, current_user.role, current_user.user_id, claim.employee_id
    ) or can_approve(db, current_user.role, current_user.user_id, employee)
    if not can_view:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="not authorized")
    return _with_outstanding(db, claim)


@router.post("/{claim_id}/submit", response_model=ExpenseClaimOut)
def submit_claim(
    claim_id: uuid.UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_tenant_db),
) -> ExpenseClaim:
    claim = _get_claim_or_404(db, claim_id)
    if not can_act_as_employee(db, current_user.role, current_user.user_id, claim.employee_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="not authorized")
    result = submit_expense_claim(db, claim)
    audit_record(
        db, current_user.tenant_id, current_user.user_id, "state_change", "expense_claim", result.id
    )
    return _with_outstanding(db, result)


@router.post("/{claim_id}/approve", response_model=ExpenseClaimOut)
def approve_claim(
    claim_id: uuid.UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_tenant_db),
) -> ExpenseClaim:
    claim = _get_claim_or_404(db, claim_id)
    employee = get_employee_or_404(db, claim.employee_id)
    if not can_approve(db, current_user.role, current_user.user_id, employee):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="not authorized")
    result = approve_expense_claim(db, claim, current_user.user_id)
    audit_record(
        db, current_user.tenant_id, current_user.user_id, "state_change", "expense_claim", result.id
    )
    return _with_outstanding(db, result)


@router.post("/{claim_id}/reject", response_model=ExpenseClaimOut)
def reject_claim(
    claim_id: uuid.UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_tenant_db),
) -> ExpenseClaim:
    claim = _get_claim_or_404(db, claim_id)
    employee = get_employee_or_404(db, claim.employee_id)
    if not can_approve(db, current_user.role, current_user.user_id, employee):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="not authorized")
    result = reject_expense_claim(db, claim, current_user.user_id)
    audit_record(
        db, current_user.tenant_id, current_user.user_id, "state_change", "expense_claim", result.id
    )
    return _with_outstanding(db, result)


@router.post("/{claim_id}/reimburse", response_model=ReimbursementOut)
def reimburse_claim(
    claim_id: uuid.UUID,
    body: ReimbursementIn,
    current_user: CurrentUser = Depends(require_roles("owner", "hr", "accountant")),
    db: Session = Depends(get_tenant_db),
) -> ExpenseReimbursement:
    claim = _get_claim_or_404(db, claim_id)
    return reimburse_expense_claim(db, claim, body.amount_paise, body.method)
