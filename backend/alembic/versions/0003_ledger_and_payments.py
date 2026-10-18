"""chart of accounts, journal, ledger_entry (append-only + balance-checked), payment

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _add_tenant_rls(table: str) -> None:
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
        "account",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenant.id"), nullable=False
        ),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("tenant_id", "code", name="uq_account_tenant_code"),
    )

    op.create_table(
        "journal",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenant.id"), nullable=False
        ),
        sa.Column("journal_date", sa.Date(), nullable=False),
        sa.Column("source_type", sa.Text(), nullable=False),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "source_type in ('invoice_issue','invoice_cancel','payment')",
            name="ck_journal_source_type",
        ),
    )
    op.create_index("ix_journal_tenant_id", "journal", ["tenant_id"])
    op.create_index("ix_journal_source", "journal", ["source_type", "source_id"])

    op.create_table(
        "ledger_entry",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenant.id"), nullable=False
        ),
        sa.Column(
            "journal_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("journal.id"), nullable=False
        ),
        sa.Column(
            "account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("account.id"), nullable=False
        ),
        sa.Column("debit_paise", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("credit_paise", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "(debit_paise > 0 AND credit_paise = 0) OR (credit_paise > 0 AND debit_paise = 0)",
            name="ck_ledger_entry_one_sided",
        ),
    )
    op.create_index("ix_ledger_entry_tenant_id", "ledger_entry", ["tenant_id"])
    op.create_index("ix_ledger_entry_journal_id", "ledger_entry", ["journal_id"])
    op.create_index("ix_ledger_entry_account_id", "ledger_entry", ["account_id"])

    op.create_table(
        "payment",
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
        sa.Column("amount_paise", sa.BigInteger(), nullable=False),
        sa.Column("method", sa.Text(), nullable=False),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("amount_paise > 0", name="ck_payment_amount_positive"),
    )
    op.create_index("ix_payment_tenant_id", "payment", ["tenant_id"])
    op.create_index("ix_payment_invoice_id", "payment", ["invoice_id"])

    # Append-only: corrections are reversing journals (app/ledger.py), never edits.
    op.execute(
        """
        CREATE FUNCTION forbid_ledger_mutation() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'journal and ledger_entry rows are append-only';
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        "CREATE TRIGGER trg_journal_append_only BEFORE UPDATE OR DELETE ON journal "
        "FOR EACH ROW EXECUTE FUNCTION forbid_ledger_mutation()"
    )
    op.execute(
        "CREATE TRIGGER trg_ledger_entry_append_only BEFORE UPDATE OR DELETE ON ledger_entry "
        "FOR EACH ROW EXECUTE FUNCTION forbid_ledger_mutation()"
    )

    # Balance check, deferred to commit: a journal's debits must equal its credits.
    # INSERT-only trigger -- UPDATE/DELETE on ledger_entry are already blocked above.
    op.execute(
        """
        CREATE FUNCTION check_journal_balance() RETURNS trigger AS $$
        DECLARE
            total_debit bigint;
            total_credit bigint;
        BEGIN
            SELECT COALESCE(SUM(debit_paise), 0), COALESCE(SUM(credit_paise), 0)
            INTO total_debit, total_credit
            FROM ledger_entry WHERE journal_id = NEW.journal_id;

            IF total_debit <> total_credit THEN
                RAISE EXCEPTION 'journal % does not balance: debit=% credit=%',
                    NEW.journal_id, total_debit, total_credit;
            END IF;
            RETURN NULL;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        "CREATE CONSTRAINT TRIGGER trg_journal_balance AFTER INSERT ON ledger_entry "
        "DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION check_journal_balance()"
    )

    for table in ("account", "journal", "ledger_entry", "payment"):
        _add_tenant_rls(table)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_journal_balance ON ledger_entry")
    op.execute("DROP FUNCTION IF EXISTS check_journal_balance")
    op.execute("DROP TRIGGER IF EXISTS trg_ledger_entry_append_only ON ledger_entry")
    op.execute("DROP TRIGGER IF EXISTS trg_journal_append_only ON journal")
    op.execute("DROP FUNCTION IF EXISTS forbid_ledger_mutation")
    op.drop_table("payment")
    op.drop_table("ledger_entry")
    op.drop_table("journal")
    op.drop_table("account")
