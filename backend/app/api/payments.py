import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.deps import CurrentUser, get_tenant_db, require_roles
from app.ledger import ACCOUNTS_RECEIVABLE, CASH_AND_BANK, post_journal
from app.models import Invoice, Payment
from app.schemas import PaymentIn, PaymentOut

router = APIRouter(prefix="/payments", tags=["payments"])


def outstanding_paise(db: Session, invoice: Invoice) -> int:
    paid = db.scalar(
        select(func.coalesce(func.sum(Payment.amount_paise), 0)).where(
            Payment.invoice_id == invoice.id
        )
    )
    return invoice.grand_total_paise - int(paid or 0)


@router.post("", response_model=PaymentOut, status_code=status.HTTP_201_CREATED)
def create_payment(
    body: PaymentIn,
    current_user: CurrentUser = Depends(require_roles("owner", "accountant")),
    db: Session = Depends(get_tenant_db),
) -> Payment:
    invoice = db.get(Invoice, body.invoice_id)
    if invoice is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="unknown invoice")
    if invoice.status != "issued":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="invoice is not issued"
        )

    outstanding = outstanding_paise(db, invoice)
    if body.amount_paise > outstanding:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"amount exceeds outstanding balance of {outstanding} paise",
        )

    paid_at = body.paid_at or datetime.now(UTC)
    payment = Payment(
        tenant_id=current_user.tenant_id,
        invoice_id=invoice.id,
        amount_paise=body.amount_paise,
        method=body.method,
        paid_at=paid_at,
    )
    db.add(payment)
    db.flush()

    post_journal(
        db,
        current_user.tenant_id,
        "payment",
        payment.id,
        paid_at.date(),
        f"Payment received for invoice {invoice.financial_year}/{invoice.number}",
        lines=[
            (CASH_AND_BANK, body.amount_paise, 0),
            (ACCOUNTS_RECEIVABLE, 0, body.amount_paise),
        ],
    )
    db.flush()
    db.refresh(payment)
    return payment


@router.get("/{payment_id}", response_model=PaymentOut)
def get_payment(payment_id: uuid.UUID, db: Session = Depends(get_tenant_db)) -> Payment:
    payment = db.get(Payment, payment_id)
    if payment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="payment not found")
    return payment
