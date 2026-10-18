import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.deps import CurrentUser, get_current_user, get_tenant_db
from app.models import Item
from app.schemas import ItemIn, ItemOut

router = APIRouter(prefix="/items", tags=["items"])


@router.post("", response_model=ItemOut, status_code=status.HTTP_201_CREATED)
def create_item(
    body: ItemIn,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_tenant_db),
) -> Item:
    item = Item(tenant_id=current_user.tenant_id, **body.model_dump())
    db.add(item)
    db.flush()
    return item


@router.get("", response_model=list[ItemOut])
def list_items(db: Session = Depends(get_tenant_db)) -> list[Item]:
    return list(db.scalars(select(Item)))


@router.get("/{item_id}", response_model=ItemOut)
def get_item(item_id: uuid.UUID, db: Session = Depends(get_tenant_db)) -> Item:
    item = db.get(Item, item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="item not found")
    return item
