"""company, customer, item, quote(+line), invoice(+line), invoice_sequence with RLS

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _add_tenant_rls(table: str) -> None:
    # Same pattern as app_user in 0001: forced RLS means it applies even to the
    # owning role, since ledgerly_app is deliberately not a superuser.
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""
        CREATE POLICY tenant_isolation ON {table}
        USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
        WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid)
        """
    )


def upgrade() -> None:
    op.create_table(
        "company",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenant.id"), nullable=False
        ),
        sa.Column("legal_name", sa.Text(), nullable=False),
        sa.Column("gstin", sa.Text(), nullable=False),
        sa.Column("state_code", sa.Text(), nullable=False),
        sa.Column("address", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("tenant_id", name="uq_company_tenant"),
    )

    op.create_table(
        "customer",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenant.id"), nullable=False
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("gstin", sa.Text(), nullable=True),
        sa.Column("state_code", sa.Text(), nullable=False),
        sa.Column("billing_address", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_customer_tenant_id", "customer", ["tenant_id"])

    op.create_table(
        "item",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenant.id"), nullable=False
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("hsn_sac", sa.Text(), nullable=False),
        sa.Column("unit", sa.Text(), nullable=False, server_default="unit"),
        sa.Column("unit_price_paise", sa.BigInteger(), nullable=False),
        sa.Column("gst_rate_bps", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_item_tenant_id", "item", ["tenant_id"])

    op.create_table(
        "quote",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenant.id"), nullable=False
        ),
        sa.Column(
            "customer_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("customer.id"),
            nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_quote_tenant_id", "quote", ["tenant_id"])

    op.create_table(
        "quote_line",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenant.id"), nullable=False
        ),
        sa.Column(
            "quote_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("quote.id"), nullable=False
        ),
        sa.Column(
            "item_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("item.id"), nullable=False
        ),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price_paise", sa.BigInteger(), nullable=False),
        sa.Column("gst_rate_bps", sa.Integer(), nullable=False),
    )
    op.create_index("ix_quote_line_tenant_id", "quote_line", ["tenant_id"])
    op.create_index("ix_quote_line_quote_id", "quote_line", ["quote_id"])

    op.create_table(
        "invoice",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenant.id"), nullable=False
        ),
        sa.Column(
            "customer_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("customer.id"),
            nullable=False,
        ),
        sa.Column(
            "quote_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("quote.id"), nullable=True
        ),
        sa.Column("status", sa.Text(), nullable=False, server_default="draft"),
        sa.Column("financial_year", sa.Text(), nullable=True),
        sa.Column("number", sa.Integer(), nullable=True),
        sa.Column("place_of_supply_state_code", sa.Text(), nullable=False),
        sa.Column("subtotal_paise", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("cgst_paise", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("sgst_paise", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("igst_paise", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("grand_total_paise", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("status in ('draft','issued','cancelled')", name="ck_invoice_status"),
        sa.UniqueConstraint(
            "tenant_id", "financial_year", "number", name="uq_invoice_tenant_fy_number"
        ),
    )
    op.create_index("ix_invoice_tenant_id", "invoice", ["tenant_id"])

    op.create_table(
        "invoice_line",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenant.id"), nullable=False
        ),
        sa.Column(
            "invoice_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("invoice.id"),
            nullable=False,
        ),
        sa.Column(
            "item_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("item.id"), nullable=False
        ),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("hsn_sac", sa.Text(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price_paise", sa.BigInteger(), nullable=False),
        sa.Column("gst_rate_bps", sa.Integer(), nullable=False),
        sa.Column("taxable_paise", sa.BigInteger(), nullable=False),
        sa.Column("cgst_paise", sa.BigInteger(), nullable=False),
        sa.Column("sgst_paise", sa.BigInteger(), nullable=False),
        sa.Column("igst_paise", sa.BigInteger(), nullable=False),
    )
    op.create_index("ix_invoice_line_tenant_id", "invoice_line", ["tenant_id"])
    op.create_index("ix_invoice_line_invoice_id", "invoice_line", ["invoice_id"])

    op.create_table(
        "invoice_sequence",
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenant.id"),
            primary_key=True,
        ),
        sa.Column("financial_year", sa.Text(), primary_key=True),
        sa.Column("next_number", sa.Integer(), nullable=False, server_default="1"),
    )

    for table in (
        "company",
        "customer",
        "item",
        "quote",
        "quote_line",
        "invoice",
        "invoice_line",
        "invoice_sequence",
    ):
        _add_tenant_rls(table)


def downgrade() -> None:
    op.drop_table("invoice_sequence")
    op.drop_table("invoice_line")
    op.drop_table("invoice")
    op.drop_table("quote_line")
    op.drop_table("quote")
    op.drop_table("item")
    op.drop_table("customer")
    op.drop_table("company")
