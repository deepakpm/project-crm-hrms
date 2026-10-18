import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import record as audit_record
from app.deps import CurrentUser, get_current_user, get_tenant_db, require_roles
from app.modules.people.models import Department, Designation, Employee
from app.modules.people.public import is_manager_of
from app.modules.people.schemas import (
    DepartmentIn,
    DepartmentOut,
    DesignationIn,
    DesignationOut,
    EmployeeDetailOut,
    EmployeeIn,
    EmployeeListOut,
)
from app.modules.people.service import get_employee_or_404, scoped_employee_ids

router = APIRouter(prefix="/people/employees", tags=["people"])
departments_router = APIRouter(prefix="/people/departments", tags=["people"])
designations_router = APIRouter(prefix="/people/designations", tags=["people"])


def _can_view_employee(db: Session, current_user: CurrentUser, employee: Employee) -> bool:
    if current_user.role in ("owner", "hr"):
        return True
    if employee.user_id == current_user.user_id:
        return True
    return is_manager_of(db, current_user.user_id, employee.id)


@router.post("", response_model=EmployeeDetailOut, status_code=status.HTTP_201_CREATED)
def create_employee(
    body: EmployeeIn,
    current_user: CurrentUser = Depends(require_roles("owner", "hr")),
    db: Session = Depends(get_tenant_db),
) -> Employee:
    employee = Employee(tenant_id=current_user.tenant_id, **body.model_dump())
    db.add(employee)
    db.flush()
    audit_record(
        db, current_user.tenant_id, current_user.user_id, "create", "employee", employee.id
    )
    return employee


@router.get("", response_model=list[EmployeeListOut])
def list_employees(
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_tenant_db),
) -> list[Employee]:
    scoped_ids = scoped_employee_ids(db, current_user.role, current_user.user_id)
    if scoped_ids is None:
        return list(db.scalars(select(Employee)))
    if not scoped_ids:
        return []
    return list(db.scalars(select(Employee).where(Employee.id.in_(scoped_ids))))


@router.get("/{employee_id}", response_model=EmployeeDetailOut)
def get_employee(
    employee_id: uuid.UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_tenant_db),
) -> Employee:
    employee = get_employee_or_404(db, employee_id)
    if not _can_view_employee(db, current_user, employee):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="not authorized")
    audit_record(
        db, current_user.tenant_id, current_user.user_id, "read", "employee", employee.id
    )
    return employee


@router.put("/{employee_id}", response_model=EmployeeDetailOut)
def update_employee(
    employee_id: uuid.UUID,
    body: EmployeeIn,
    current_user: CurrentUser = Depends(require_roles("owner", "hr")),
    db: Session = Depends(get_tenant_db),
) -> Employee:
    employee = get_employee_or_404(db, employee_id)
    changed = [
        field
        for field, value in body.model_dump().items()
        if getattr(employee, field) != value
    ]
    for field, value in body.model_dump().items():
        setattr(employee, field, value)
    db.flush()
    if changed:
        audit_record(
            db,
            current_user.tenant_id,
            current_user.user_id,
            "update",
            "employee",
            employee.id,
            changed,
        )
    return employee


@departments_router.post("", response_model=DepartmentOut, status_code=status.HTTP_201_CREATED)
def create_department(
    body: DepartmentIn,
    current_user: CurrentUser = Depends(require_roles("owner", "hr")),
    db: Session = Depends(get_tenant_db),
) -> Department:
    department = Department(tenant_id=current_user.tenant_id, **body.model_dump())
    db.add(department)
    db.flush()
    return department


@departments_router.get("", response_model=list[DepartmentOut])
def list_departments(db: Session = Depends(get_tenant_db)) -> list[Department]:
    return list(db.scalars(select(Department)))


@designations_router.post("", response_model=DesignationOut, status_code=status.HTTP_201_CREATED)
def create_designation(
    body: DesignationIn,
    current_user: CurrentUser = Depends(require_roles("owner", "hr")),
    db: Session = Depends(get_tenant_db),
) -> Designation:
    designation = Designation(tenant_id=current_user.tenant_id, **body.model_dump())
    db.add(designation)
    db.flush()
    return designation


@designations_router.get("", response_model=list[DesignationOut])
def list_designations(db: Session = Depends(get_tenant_db)) -> list[Designation]:
    return list(db.scalars(select(Designation)))
