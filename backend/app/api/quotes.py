import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.deps import CurrentUser, get_current_user, get_tenant_db
from app.models import Item, Quote, QuoteLine
from app.schemas import QuoteIn, QuoteOut

router = APIRouter(prefix="/quotes", tags=["quotes"])


@router.post("", response_model=QuoteOut, status_code=status.HTTP_201_CREATED)
def create_quote(
    body: QuoteIn,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_tenant_db),
) -> Quote:
    quote = Quote(tenant_id=current_user.tenant_id, customer_id=body.customer_id)
    db.add(quote)
    db.flush()

    for line_in in body.lines:
        item = db.get(Item, line_in.item_id)
        if item is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="unknown item")
        db.add(
            QuoteLine(
                tenant_id=current_user.tenant_id,
                quote_id=quote.id,
                item_id=item.id,
                quantity=line_in.quantity,
                unit_price_paise=item.unit_price_paise,
                gst_rate_bps=item.gst_rate_bps,
            )
        )
    db.flush()
    db.refresh(quote)
    return quote


@router.get("/{quote_id}", response_model=QuoteOut)
def get_quote(quote_id: uuid.UUID, db: Session = Depends(get_tenant_db)) -> Quote:
    quote = db.get(Quote, quote_id)
    if quote is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="quote not found")
    return quote
