from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.deps import CurrentUser, get_current_user, get_tenant_db
from app.ledger import seed_chart_of_accounts
from app.models import Company
from app.schemas import CompanyIn, CompanyOut

router = APIRouter(prefix="/company", tags=["company"])


@router.get("", response_model=CompanyOut)
def get_company(db: Session = Depends(get_tenant_db)) -> Company:
    company = db.scalar(select(Company))
    if company is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="company profile not set"
        )
    return company  # type: ignore[no-any-return]  # db.scalar(select(...)) is untyped past Optional


@router.put("", response_model=CompanyOut)
def upsert_company(
    body: CompanyIn,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_tenant_db),
) -> Company:
    company = db.scalar(select(Company))
    if company is None:
        company = Company(tenant_id=current_user.tenant_id, **body.model_dump())
        db.add(company)
        seed_chart_of_accounts(db, current_user.tenant_id)
    else:
        for field, value in body.model_dump().items():
            setattr(company, field, value)
    db.flush()
    return company
