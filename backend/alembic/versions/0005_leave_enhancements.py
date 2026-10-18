"""leave enhancements: half-day, reason dropdown + comment, accrual, holiday
block, attendance<->leave link

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_DAYS_COLUMNS = (
    ("leave_policy_type", "annual_days"),
    ("leave_allocation", "allocated_days"),
    ("leave_application", "days"),
    ("leave_ledger_entry", "days_delta"),
)


def upgrade() -> None:
    # --- half-day granularity: whole int days -> exact 0.5-step decimal ---
    for table, column in _DAYS_COLUMNS:
        op.alter_column(
            table, column, type_=sa.Numeric(6, 1), postgresql_using=f"{column}::numeric(6,1)"
        )

    # --- accrual config on leave_type (default 'none' preserves existing
    # lump-sum-at-allocation behaviour) ---
    op.add_column(
        "leave_type",
        sa.Column("accrual_frequency", sa.Text(), nullable=False, server_default="none"),
    )
    op.execute(
        "ALTER TABLE leave_type ADD CONSTRAINT ck_leave_type_accrual_frequency "
        "CHECK (accrual_frequency in ('none','monthly','yearly'))"
    )

    # --- idempotency marker for the manual accrual-run endpoint ---
    op.add_column("leave_allocation", sa.Column("last_accrued_on", sa.Date(), nullable=True))

    # --- leave_application: half_day + reason becomes a dropdown code + free comment ---
    op.add_column(
        "leave_application",
        sa.Column("half_day", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.execute(
        "ALTER TABLE leave_application ADD CONSTRAINT ck_leave_application_half_day_single_day "
        "CHECK (NOT half_day OR start_date = end_date)"
    )
    op.alter_column("leave_application", "reason", new_column_name="reason_code")
    op.execute(
        "ALTER TABLE leave_application ADD CONSTRAINT ck_leave_application_reason_code "
        "CHECK (reason_code is null or reason_code in "
        "('personal','medical','family','bereavement','travel','other'))"
    )
    op.add_column("leave_application", sa.Column("comment", sa.Text(), nullable=True))

    # --- attendance <-> leave link: rows the approval flow creates are
    # tagged so cancellation can remove exactly those, never a manually
    # marked day ---
    op.add_column(
        "attendance",
        sa.Column(
            "leave_application_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("leave_application.id"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_attendance_leave_application_id", "attendance", ["leave_application_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_attendance_leave_application_id", table_name="attendance")
    op.drop_column("attendance", "leave_application_id")

    op.drop_column("leave_application", "comment")
    op.execute(
        "ALTER TABLE leave_application DROP CONSTRAINT ck_leave_application_reason_code"
    )
    op.alter_column("leave_application", "reason_code", new_column_name="reason")
    op.execute(
        "ALTER TABLE leave_application DROP CONSTRAINT ck_leave_application_half_day_single_day"
    )
    op.drop_column("leave_application", "half_day")

    op.drop_column("leave_allocation", "last_accrued_on")

    op.execute("ALTER TABLE leave_type DROP CONSTRAINT ck_leave_type_accrual_frequency")
    op.drop_column("leave_type", "accrual_frequency")

    for table, column in _DAYS_COLUMNS:
        op.alter_column(
            table, column, type_=sa.Integer(), postgresql_using=f"round({column})::integer"
        )
