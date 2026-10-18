import uuid

from sqlalchemy.orm import Session

from app.models import AuditLog


def record(
    db: Session,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID | None,
    action: str,
    table_name: str,
    record_id: uuid.UUID,
    field_names: list[str] | None = None,
) -> None:
    """Every module calls this the same way -- no field *values* are ever
    accepted here, so this facility cannot leak personal data even by mistake."""
    db.add(
        AuditLog(
            tenant_id=tenant_id,
            user_id=user_id,
            action=action,
            table_name=table_name,
            record_id=record_id,
            field_names=",".join(field_names) if field_names else None,
        )
    )
