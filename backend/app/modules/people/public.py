"""The only surface other modules (timesheets, projects, inventory) may import
from. Nothing else in app.modules.people is a stable contract -- enforced by
tests/test_module_boundaries.py."""

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.people.models import Employee


@dataclass(frozen=True)
class EmployeeSummary:
    id: uuid.UUID
    code: str
    name: str
    manager_id: uuid.UUID | None
    department_id: uuid.UUID | None
    user_id: uuid.UUID | None


def get_employee(db: Session, employee_id: uuid.UUID) -> EmployeeSummary | None:
    emp = db.get(Employee, employee_id)
    if emp is None:
        return None
    return EmployeeSummary(
        id=emp.id,
        code=emp.code,
        name=emp.name,
        manager_id=emp.manager_id,
        department_id=emp.department_id,
        user_id=emp.user_id,
    )


def get_employee_id_for_user(db: Session, user_id: uuid.UUID) -> uuid.UUID | None:
    return db.scalar(select(Employee.id).where(Employee.user_id == user_id))


def is_manager_of(db: Session, user_id: uuid.UUID, employee_id: uuid.UUID) -> bool:
    """True if user_id is the app_user linked to employee_id's manager."""
    employee = db.get(Employee, employee_id)
    if employee is None or employee.manager_id is None:
        return False
    manager = db.get(Employee, employee.manager_id)
    return manager is not None and manager.user_id == user_id
