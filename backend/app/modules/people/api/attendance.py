import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import extract, select
from sqlalchemy.orm import Session

from app.deps import CurrentUser, get_current_user, get_tenant_db
from app.modules.people.models import Attendance
from app.modules.people.schemas import AttendanceMarkIn, AttendanceOut
from app.modules.people.service import get_employee_or_404, mark_attendance, scoped_employee_ids

router = APIRouter(prefix="/people/attendance", tags=["people"])


@router.post("", response_model=AttendanceOut, status_code=status.HTTP_201_CREATED)
def mark(
    body: AttendanceMarkIn,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_tenant_db),
) -> Attendance:
    scoped_ids = scoped_employee_ids(db, current_user.role, current_user.user_id)
    if scoped_ids is not None and body.employee_id not in scoped_ids:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="not authorized")
    get_employee_or_404(db, body.employee_id)
    return mark_attendance(db, current_user.tenant_id, body.employee_id, body.date, body.status)


@router.get("/{employee_id}", response_model=list[AttendanceOut])
def monthly_calendar(
    employee_id: uuid.UUID,
    year: int,
    month: int,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_tenant_db),
) -> list[Attendance]:
    scoped_ids = scoped_employee_ids(db, current_user.role, current_user.user_id)
    if scoped_ids is not None and employee_id not in scoped_ids:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="not authorized")
    get_employee_or_404(db, employee_id)
    return list(
        db.scalars(
            select(Attendance).where(
                Attendance.employee_id == employee_id,
                extract("year", Attendance.date) == year,
                extract("month", Attendance.date) == month,
            )
        )
    )
