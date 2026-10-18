from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.deps import get_tenant_db
from app.models import Account, Customer, Invoice, LedgerEntry, Payment
from app.schemas import AgeingRow, TrialBalanceRow

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/trial-balance", response_model=list[TrialBalanceRow])
def trial_balance(db: Session = Depends(get_tenant_db)) -> list[TrialBalanceRow]:
    rows = db.execute(
        select(
            Account.code,
            Account.name,
            Account.type,
            func.coalesce(func.sum(LedgerEntry.debit_paise), 0),
            func.coalesce(func.sum(LedgerEntry.credit_paise), 0),
        )
        .select_from(Account)
        .outerjoin(LedgerEntry, LedgerEntry.account_id == Account.id)
        .group_by(Account.id, Account.code, Account.name, Account.type)
        .order_by(Account.code)
    ).all()
    return [
        TrialBalanceRow(
            account_code=code,
            account_name=name,
            account_type=account_type,
            debit_paise=int(debit),
            credit_paise=int(credit),
        )
        for code, name, account_type, debit, credit in rows
    ]


@router.get("/receivables-ageing", response_model=list[AgeingRow])
def receivables_ageing(db: Session = Depends(get_tenant_db)) -> list[AgeingRow]:
    invoices = db.scalars(select(Invoice).where(Invoice.status == "issued")).all()
    today = datetime.now(UTC).date()
    rows = []
    for invoice in invoices:
        paid = db.scalar(
            select(func.coalesce(func.sum(Payment.amount_paise), 0)).where(
                Payment.invoice_id == invoice.id
            )
        )
        outstanding = invoice.grand_total_paise - int(paid or 0)
        if outstanding <= 0:
            continue
        customer = db.get(Customer, invoice.customer_id)
        assert customer is not None
        assert invoice.issued_at is not None  # status == "issued" guarantees this
        days_overdue = (today - invoice.issued_at.date()).days
        rows.append(
            AgeingRow(
                invoice_id=invoice.id,
                financial_year=invoice.financial_year,
                number=invoice.number,
                customer_name=customer.name,
                outstanding_paise=outstanding,
                days_overdue=days_overdue,
                bucket=_ageing_bucket(days_overdue),
            )
        )
    return rows


def _ageing_bucket(days_overdue: int) -> str:
    if days_overdue <= 30:
        return "0-30"
    if days_overdue <= 60:
        return "31-60"
    if days_overdue <= 90:
        return "61-90"
    return "90+"
