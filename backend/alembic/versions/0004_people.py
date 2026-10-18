"""audit_log, widen role/journal-source checks, people module (Milestone 3)

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _add_tenant_rls(table: str) -> None:
    # Same pattern as every table since 0001: forced RLS applies even to the
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
    # --- widen two existing core CHECK constraints ---
    op.execute("ALTER TABLE app_user DROP CONSTRAINT ck_app_user_role")
    op.execute(
        "ALTER TABLE app_user ADD CONSTRAINT ck_app_user_role "
        "CHECK (role in ('owner','accountant','member','hr','manager'))"
    )
    op.execute("ALTER TABLE journal DROP CONSTRAINT ck_journal_source_type")
    op.execute(
        "ALTER TABLE journal ADD CONSTRAINT ck_journal_source_type "
        "CHECK (source_type in ('invoice_issue','invoice_cancel','payment',"
        "'expense_claim','expense_reimbursement'))"
    )

    # --- audit_log (core facility) ---
    op.create_table(
        "audit_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenant.id"), nullable=False
        ),
        sa.Column(
            "user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("app_user.id"), nullable=True
        ),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("table_name", sa.Text(), nullable=False),
        sa.Column("record_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("field_names", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "action in ('create','update','state_change','read')", name="ck_audit_log_action"
        ),
    )
    op.create_index("ix_audit_log_tenant_id", "audit_log", ["tenant_id"])
    op.create_index("ix_audit_log_record", "audit_log", ["table_name", "record_id"])

    # --- people: masters ---
    op.create_table(
        "department",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenant.id"), nullable=False
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("tenant_id", "name", name="uq_department_tenant_name"),
    )

    op.create_table(
        "designation",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenant.id"), nullable=False
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("tenant_id", "name", name="uq_designation_tenant_name"),
    )

    op.create_table(
        "employee",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenant.id"), nullable=False
        ),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("work_email", sa.Text(), nullable=False),
        sa.Column("phone", sa.Text(), nullable=True),
        sa.Column(
            "department_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("department.id"),
            nullable=True,
        ),
        sa.Column(
            "designation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("designation.id"),
            nullable=True,
        ),
        sa.Column(
            "manager_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("employee.id"), nullable=True
        ),
        sa.Column("join_date", sa.Date(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="active"),
        sa.Column("employment_type", sa.Text(), nullable=False, server_default="full_time"),
        sa.Column(
            "user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("app_user.id"),
            nullable=True, unique=True,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("tenant_id", "code", name="uq_employee_tenant_code"),
        sa.CheckConstraint("status in ('active','inactive')", name="ck_employee_status"),
        sa.CheckConstraint(
            "employment_type in ('full_time','part_time','contract','intern')",
            name="ck_employee_employment_type",
        ),
    )
    op.create_index("ix_employee_tenant_id", "employee", ["tenant_id"])
    op.create_index("ix_employee_manager_id", "employee", ["manager_id"])

    # --- holiday lists ---
    op.create_table(
        "holiday_list",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenant.id"), nullable=False
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("state_code", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_holiday_list_tenant_id", "holiday_list", ["tenant_id"])

    op.create_table(
        "holiday",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenant.id"), nullable=False
        ),
        sa.Column(
            "holiday_list_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("holiday_list.id"),
            nullable=False,
        ),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.UniqueConstraint("holiday_list_id", "date", name="uq_holiday_list_date"),
    )
    op.create_index("ix_holiday_tenant_id", "holiday", ["tenant_id"])
    op.create_index("ix_holiday_holiday_list_id", "holiday", ["holiday_list_id"])

    # --- leave types, policies, allocations, applications, ledger ---
    op.create_table(
        "leave_type",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenant.id"), nullable=False
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("exclude_weekends", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("exclude_holidays", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("tenant_id", "name", name="uq_leave_type_tenant_name"),
    )

    op.create_table(
        "leave_policy",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenant.id"), nullable=False
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_leave_policy_tenant_id", "leave_policy", ["tenant_id"])

    op.create_table(
        "leave_policy_type",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenant.id"), nullable=False
        ),
        sa.Column(
            "policy_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("leave_policy.id"),
            nullable=False,
        ),
        sa.Column(
            "leave_type_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("leave_type.id"),
            nullable=False,
        ),
        sa.Column("annual_days", sa.Integer(), nullable=False),
        sa.UniqueConstraint("policy_id", "leave_type_id", name="uq_leave_policy_type"),
    )
    op.create_index("ix_leave_policy_type_tenant_id", "leave_policy_type", ["tenant_id"])

    op.create_table(
        "leave_allocation",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenant.id"), nullable=False
        ),
        sa.Column(
            "employee_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("employee.id"),
            nullable=False,
        ),
        sa.Column(
            "leave_type_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("leave_type.id"),
            nullable=False,
        ),
        sa.Column("financial_year", sa.Text(), nullable=False),
        sa.Column("allocated_days", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint(
            "employee_id", "leave_type_id", "financial_year", name="uq_leave_allocation"
        ),
    )
    op.create_index("ix_leave_allocation_tenant_id", "leave_allocation", ["tenant_id"])

    op.create_table(
        "leave_application",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenant.id"), nullable=False
        ),
        sa.Column(
            "employee_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("employee.id"),
            nullable=False,
        ),
        sa.Column(
            "leave_type_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("leave_type.id"),
            nullable=False,
        ),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("days", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.Text(), nullable=False, server_default="draft"),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column(
            "approver_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("app_user.id"),
            nullable=True,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status in ('draft','submitted','approved','rejected','cancelled')",
            name="ck_leave_application_status",
        ),
    )
    op.create_index("ix_leave_application_tenant_id", "leave_application", ["tenant_id"])
    op.create_index("ix_leave_application_employee_id", "leave_application", ["employee_id"])

    op.create_table(
        "leave_ledger_entry",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenant.id"), nullable=False
        ),
        sa.Column(
            "employee_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("employee.id"),
            nullable=False,
        ),
        sa.Column(
            "leave_type_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("leave_type.id"),
            nullable=False,
        ),
        sa.Column("source_type", sa.Text(), nullable=False),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("days_delta", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "source_type in ('allocation','application','reversal')",
            name="ck_leave_ledger_entry_source_type",
        ),
    )
    op.create_index("ix_leave_ledger_entry_tenant_id", "leave_ledger_entry", ["tenant_id"])
    op.create_index(
        "ix_leave_ledger_entry_employee_leave_type",
        "leave_ledger_entry",
        ["employee_id", "leave_type_id"],
    )
    # Append-only: reuses the forbid_ledger_mutation() function 0003 already
    # defined for the financial ledger -- the function body is fully generic.
    op.execute(
        "CREATE TRIGGER trg_leave_ledger_entry_append_only "
        "BEFORE UPDATE OR DELETE ON leave_ledger_entry "
        "FOR EACH ROW EXECUTE FUNCTION forbid_ledger_mutation()"
    )

    # --- attendance ---
    op.create_table(
        "attendance",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenant.id"), nullable=False
        ),
        sa.Column(
            "employee_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("employee.id"),
            nullable=False,
        ),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("employee_id", "date", name="uq_attendance_employee_date"),
        sa.CheckConstraint(
            "status in ('present','absent','half_day','on_leave','holiday')",
            name="ck_attendance_status",
        ),
    )
    op.create_index("ix_attendance_tenant_id", "attendance", ["tenant_id"])

    # --- expense claims ---
    op.create_table(
        "expense_claim",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenant.id"), nullable=False
        ),
        sa.Column(
            "employee_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("employee.id"),
            nullable=False,
        ),
        sa.Column("status", sa.Text(), nullable=False, server_default="draft"),
        sa.Column("total_paise", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column(
            "approver_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("app_user.id"),
            nullable=True,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status in ('draft','submitted','approved','rejected')", name="ck_expense_claim_status"
        ),
    )
    op.create_index("ix_expense_claim_tenant_id", "expense_claim", ["tenant_id"])
    op.create_index("ix_expense_claim_employee_id", "expense_claim", ["employee_id"])

    op.create_table(
        "expense_claim_line",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenant.id"), nullable=False
        ),
        sa.Column(
            "claim_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("expense_claim.id"),
            nullable=False,
        ),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("amount_paise", sa.BigInteger(), nullable=False),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("attachment_url", sa.Text(), nullable=True),
    )
    op.create_index("ix_expense_claim_line_tenant_id", "expense_claim_line", ["tenant_id"])
    op.create_index("ix_expense_claim_line_claim_id", "expense_claim_line", ["claim_id"])

    op.create_table(
        "expense_reimbursement",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenant.id"), nullable=False
        ),
        sa.Column(
            "claim_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("expense_claim.id"),
            nullable=False,
        ),
        sa.Column("amount_paise", sa.BigInteger(), nullable=False),
        sa.Column("method", sa.Text(), nullable=False),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_expense_reimbursement_tenant_id", "expense_reimbursement", ["tenant_id"])
    op.create_index(
        "ix_expense_reimbursement_claim_id", "expense_reimbursement", ["claim_id"]
    )

    for table in (
        "audit_log",
        "department",
        "designation",
        "employee",
        "holiday_list",
        "holiday",
        "leave_type",
        "leave_policy",
        "leave_policy_type",
        "leave_allocation",
        "leave_application",
        "leave_ledger_entry",
        "attendance",
        "expense_claim",
        "expense_claim_line",
        "expense_reimbursement",
    ):
        _add_tenant_rls(table)


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS trg_leave_ledger_entry_append_only ON leave_ledger_entry"
    )
    op.drop_table("expense_reimbursement")
    op.drop_table("expense_claim_line")
    op.drop_table("expense_claim")
    op.drop_table("attendance")
    op.drop_table("leave_ledger_entry")
    op.drop_table("leave_application")
    op.drop_table("leave_allocation")
    op.drop_table("leave_policy_type")
    op.drop_table("leave_policy")
    op.drop_table("leave_type")
    op.drop_table("holiday")
    op.drop_table("holiday_list")
    op.drop_table("employee")
    op.drop_table("designation")
    op.drop_table("department")
    op.drop_table("audit_log")

    op.execute("ALTER TABLE journal DROP CONSTRAINT ck_journal_source_type")
    op.execute(
        "ALTER TABLE journal ADD CONSTRAINT ck_journal_source_type "
        "CHECK (source_type in ('invoice_issue','invoice_cancel','payment'))"
    )
    op.execute("ALTER TABLE app_user DROP CONSTRAINT ck_app_user_role")
    op.execute(
        "ALTER TABLE app_user ADD CONSTRAINT ck_app_user_role "
        "CHECK (role in ('owner','accountant','member'))"
    )
