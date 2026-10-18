import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Account, Journal, LedgerEntry

# Minimal chart of accounts: only what the invoice and payment flows actually
# post to. Not a general-purpose chart -- add accounts when a new flow needs one.
ACCOUNTS_RECEIVABLE = "1100"
SALES_REVENUE = "4000"
OUTPUT_CGST_PAYABLE = "2100"
OUTPUT_SGST_PAYABLE = "2200"
OUTPUT_IGST_PAYABLE = "2300"
CASH_AND_BANK = "1000"
OPERATING_EXPENSES = "5100"
EMPLOYEE_REIMBURSEMENTS_PAYABLE = "2400"

DEFAULT_ACCOUNTS: list[tuple[str, str, str]] = [
    (ACCOUNTS_RECEIVABLE, "Accounts Receivable", "asset"),
    (SALES_REVENUE, "Sales Revenue", "income"),
    (OUTPUT_CGST_PAYABLE, "Output CGST Payable", "liability"),
    (OUTPUT_SGST_PAYABLE, "Output SGST Payable", "liability"),
    (OUTPUT_IGST_PAYABLE, "Output IGST Payable", "liability"),
    (CASH_AND_BANK, "Cash and Bank", "asset"),
    (OPERATING_EXPENSES, "Operating Expenses", "expense"),
    (EMPLOYEE_REIMBURSEMENTS_PAYABLE, "Employee Reimbursements Payable", "liability"),
]


def seed_chart_of_accounts(db: Session, tenant_id: uuid.UUID) -> None:
    if db.scalar(select(Account).limit(1)) is not None:
        return
    for code, name, account_type in DEFAULT_ACCOUNTS:
        db.add(Account(tenant_id=tenant_id, code=code, name=name, type=account_type))
    db.flush()


def _account_id(db: Session, code: str) -> uuid.UUID:
    account = db.scalar(select(Account).where(Account.code == code))
    if account is None:
        raise RuntimeError(f"chart of accounts missing account {code!r}")
    return account.id


def post_journal(
    db: Session,
    tenant_id: uuid.UUID,
    source_type: str,
    source_id: uuid.UUID,
    journal_date: date,
    description: str,
    lines: list[tuple[str, int, int]],  # (account_code, debit_paise, credit_paise)
) -> Journal:
    """Zero-amount lines are skipped (e.g. IGST on an intra-state invoice). The
    deferred balance trigger on ledger_entry is the real backstop -- it fires at
    commit, so an unbalanced set of lines never becomes an unbalanced journal."""
    journal = Journal(
        tenant_id=tenant_id,
        journal_date=journal_date,
        source_type=source_type,
        source_id=source_id,
        description=description,
    )
    db.add(journal)
    db.flush()

    for account_code, debit_paise, credit_paise in lines:
        if debit_paise == 0 and credit_paise == 0:
            continue
        db.add(
            LedgerEntry(
                tenant_id=tenant_id,
                journal_id=journal.id,
                account_id=_account_id(db, account_code),
                debit_paise=debit_paise,
                credit_paise=credit_paise,
            )
        )
    db.flush()
    return journal


def reverse_journal(
    db: Session,
    tenant_id: uuid.UUID,
    original: Journal,
    source_type: str,
    journal_date: date,
    description: str,
) -> Journal:
    """Exact reversal: same lines, debit and credit swapped. This is the
    'corrections are reversing journals, never edits' rule in code."""
    reversal = Journal(
        tenant_id=tenant_id,
        journal_date=journal_date,
        source_type=source_type,
        source_id=original.source_id,
        description=description,
    )
    db.add(reversal)
    db.flush()

    for entry in original.entries:
        db.add(
            LedgerEntry(
                tenant_id=tenant_id,
                journal_id=reversal.id,
                account_id=entry.account_id,
                debit_paise=entry.credit_paise,
                credit_paise=entry.debit_paise,
            )
        )
    db.flush()
    return reversal
