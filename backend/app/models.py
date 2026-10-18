import uuid
from datetime import date, datetime

from sqlalchemy import CheckConstraint, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    pass


class Tenant(Base):
    __tablename__ = "tenant"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(nullable=False)
    slug: Mapped[str] = mapped_column(nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)


class AppUser(Base):
    __tablename__ = "app_user"
    __table_args__ = (
        UniqueConstraint("tenant_id", "email", name="uq_app_user_tenant_email"),
        CheckConstraint(
            "role in ('owner','accountant','member','hr','manager')", name="ck_app_user_role"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenant.id"), nullable=False
    )
    email: Mapped[str] = mapped_column(nullable=False)
    password_hash: Mapped[str] = mapped_column(nullable=False)
    role: Mapped[str] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)


class RefreshToken(Base):
    __tablename__ = "refresh_token"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenant.id"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("app_user.id"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)


class Company(Base):
    """One row per tenant: the business issuing invoices. Multi-company is out of
    scope for a solo-founder MVP (YAGNI) -- enforced here by a unique tenant_id."""

    __tablename__ = "company"
    __table_args__ = (UniqueConstraint("tenant_id", name="uq_company_tenant"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenant.id"), nullable=False
    )
    legal_name: Mapped[str] = mapped_column(nullable=False)
    gstin: Mapped[str] = mapped_column(nullable=False)
    state_code: Mapped[str] = mapped_column(nullable=False)
    address: Mapped[str] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)


class Customer(Base):
    __tablename__ = "customer"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenant.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(nullable=False)
    gstin: Mapped[str | None] = mapped_column(nullable=True)  # null for B2C
    state_code: Mapped[str] = mapped_column(nullable=False)  # drives place-of-supply
    billing_address: Mapped[str] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)


class Item(Base):
    __tablename__ = "item"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenant.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(nullable=False)
    hsn_sac: Mapped[str] = mapped_column(nullable=False)
    unit: Mapped[str] = mapped_column(nullable=False, default="unit")
    unit_price_paise: Mapped[int] = mapped_column(nullable=False)
    gst_rate_bps: Mapped[int] = mapped_column(nullable=False)  # 1800 = 18.00%
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)


class Quote(Base):
    __tablename__ = "quote"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenant.id"), nullable=False
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customer.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)

    lines: Mapped[list["QuoteLine"]] = relationship(
        back_populates="quote", cascade="all, delete-orphan"
    )


class QuoteLine(Base):
    __tablename__ = "quote_line"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenant.id"), nullable=False
    )
    quote_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("quote.id"), nullable=False
    )
    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("item.id"), nullable=False
    )
    quantity: Mapped[int] = mapped_column(nullable=False)
    unit_price_paise: Mapped[int] = mapped_column(nullable=False)  # copied from item at quote time
    gst_rate_bps: Mapped[int] = mapped_column(nullable=False)

    quote: Mapped["Quote"] = relationship(back_populates="lines")


class Invoice(Base):
    __tablename__ = "invoice"
    __table_args__ = (
        CheckConstraint("status in ('draft','issued','cancelled')", name="ck_invoice_status"),
        UniqueConstraint(
            "tenant_id", "financial_year", "number", name="uq_invoice_tenant_fy_number"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenant.id"), nullable=False
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customer.id"), nullable=False
    )
    quote_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("quote.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(nullable=False, default="draft")
    financial_year: Mapped[str | None] = mapped_column(nullable=True)  # set only on issue
    number: Mapped[int | None] = mapped_column(nullable=True)  # set only on issue
    place_of_supply_state_code: Mapped[str] = mapped_column(nullable=False)
    subtotal_paise: Mapped[int] = mapped_column(nullable=False, default=0)
    cgst_paise: Mapped[int] = mapped_column(nullable=False, default=0)
    sgst_paise: Mapped[int] = mapped_column(nullable=False, default=0)
    igst_paise: Mapped[int] = mapped_column(nullable=False, default=0)
    grand_total_paise: Mapped[int] = mapped_column(nullable=False, default=0)
    issued_at: Mapped[datetime | None] = mapped_column(nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)

    lines: Mapped[list["InvoiceLine"]] = relationship(
        back_populates="invoice", cascade="all, delete-orphan"
    )


class InvoiceLine(Base):
    __tablename__ = "invoice_line"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenant.id"), nullable=False
    )
    invoice_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("invoice.id"), nullable=False
    )
    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("item.id"), nullable=False
    )
    description: Mapped[str] = mapped_column(nullable=False)  # copied from item at invoice time
    hsn_sac: Mapped[str] = mapped_column(nullable=False)
    quantity: Mapped[int] = mapped_column(nullable=False)
    unit_price_paise: Mapped[int] = mapped_column(nullable=False)
    gst_rate_bps: Mapped[int] = mapped_column(nullable=False)
    taxable_paise: Mapped[int] = mapped_column(nullable=False)
    cgst_paise: Mapped[int] = mapped_column(nullable=False)
    sgst_paise: Mapped[int] = mapped_column(nullable=False)
    igst_paise: Mapped[int] = mapped_column(nullable=False)

    invoice: Mapped["Invoice"] = relationship(back_populates="lines")


class InvoiceSequence(Base):
    """One row per (tenant, financial_year). next_number is incremented by an atomic
    INSERT ... ON CONFLICT DO UPDATE, which is what makes numbering gapless and safe
    under concurrent issuance without an app-level lock."""

    __tablename__ = "invoice_sequence"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenant.id"), primary_key=True
    )
    financial_year: Mapped[str] = mapped_column(primary_key=True)
    next_number: Mapped[int] = mapped_column(nullable=False, default=1)


class Account(Base):
    __tablename__ = "account"
    __table_args__ = (UniqueConstraint("tenant_id", "code", name="uq_account_tenant_code"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenant.id"), nullable=False
    )
    code: Mapped[str] = mapped_column(nullable=False)
    name: Mapped[str] = mapped_column(nullable=False)
    type: Mapped[str] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)


class Journal(Base):
    """Append-only; see the 0003 migration's triggers. Corrections are new
    reversing journals, never edits to one of these rows."""

    __tablename__ = "journal"
    __table_args__ = (
        CheckConstraint(
            "source_type in ('invoice_issue','invoice_cancel','payment',"
            "'expense_claim','expense_reimbursement')",
            name="ck_journal_source_type",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenant.id"), nullable=False
    )
    journal_date: Mapped[date] = mapped_column(nullable=False)
    source_type: Mapped[str] = mapped_column(nullable=False)
    source_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    description: Mapped[str] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)

    entries: Mapped[list["LedgerEntry"]] = relationship(back_populates="journal")


class LedgerEntry(Base):
    """Append-only; a deferred constraint trigger enforces that each journal's
    debits equal its credits at commit time (see the 0003 migration)."""

    __tablename__ = "ledger_entry"
    __table_args__ = (
        CheckConstraint(
            "(debit_paise > 0 AND credit_paise = 0) OR (credit_paise > 0 AND debit_paise = 0)",
            name="ck_ledger_entry_one_sided",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenant.id"), nullable=False
    )
    journal_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("journal.id"), nullable=False
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("account.id"), nullable=False
    )
    debit_paise: Mapped[int] = mapped_column(nullable=False, default=0)
    credit_paise: Mapped[int] = mapped_column(nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)

    journal: Mapped["Journal"] = relationship(back_populates="entries")


class Payment(Base):
    __tablename__ = "payment"
    __table_args__ = (CheckConstraint("amount_paise > 0", name="ck_payment_amount_positive"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenant.id"), nullable=False
    )
    invoice_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("invoice.id"), nullable=False
    )
    amount_paise: Mapped[int] = mapped_column(nullable=False)
    method: Mapped[str] = mapped_column(nullable=False)
    paid_at: Mapped[datetime] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)


class AuditLog(Base):
    """Shared core facility, not people-specific -- any module records through
    this. Never stores field values, only field names, so it can never itself
    leak personal data."""

    __tablename__ = "audit_log"
    __table_args__ = (
        CheckConstraint(
            "action in ('create','update','state_change','read')", name="ck_audit_log_action"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenant.id"), nullable=False
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("app_user.id"), nullable=True
    )
    action: Mapped[str] = mapped_column(nullable=False)
    table_name: Mapped[str] = mapped_column(nullable=False)
    record_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    field_names: Mapped[str | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
