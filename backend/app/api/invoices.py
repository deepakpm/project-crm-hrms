import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.deps import CurrentUser, get_current_user, get_tenant_db, require_roles
from app.gst import compute_line_tax, financial_year_label
from app.ledger import (
    ACCOUNTS_RECEIVABLE,
    OUTPUT_CGST_PAYABLE,
    OUTPUT_IGST_PAYABLE,
    OUTPUT_SGST_PAYABLE,
    SALES_REVENUE,
    post_journal,
    reverse_journal,
)
from app.models import Company, Customer, Invoice, InvoiceLine, Item, Journal
from app.pdf import render_invoice_pdf
from app.schemas import InvoiceIn, InvoiceOut, InvoicePreviewOut, LineIn

router = APIRouter(prefix="/invoices", tags=["invoices"])


def _get_company_or_400(db: Session) -> Company:
    company = db.scalar(select(Company))
    if company is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="set up company profile first"
        )
    return company  # type: ignore[no-any-return]  # db.scalar(select(...)) is untyped past Optional


def _get_customer_or_400(db: Session, customer_id: uuid.UUID) -> Customer:
    customer = db.get(Customer, customer_id)
    if customer is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="unknown customer")
    return customer


@dataclass
class _PricedLine:
    item_id: uuid.UUID
    description: str
    hsn_sac: str
    quantity: int
    unit_price_paise: int
    gst_rate_bps: int
    taxable_paise: int
    cgst_paise: int
    sgst_paise: int
    igst_paise: int


def _price_lines(db: Session, lines_in: list[LineIn], same_state: bool) -> list[_PricedLine]:
    """The one place invoice GST math happens -- used by both create and preview,
    so the browser never has to (and can't) duplicate the tax logic."""
    priced = []
    for line_in in lines_in:
        item = db.get(Item, line_in.item_id)
        if item is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="unknown item")
        taxable_paise = line_in.quantity * item.unit_price_paise
        tax = compute_line_tax(taxable_paise, item.gst_rate_bps, same_state)
        priced.append(
            _PricedLine(
                item_id=item.id,
                description=item.name,
                hsn_sac=item.hsn_sac,
                quantity=line_in.quantity,
                unit_price_paise=item.unit_price_paise,
                gst_rate_bps=item.gst_rate_bps,
                taxable_paise=taxable_paise,
                cgst_paise=tax.cgst_paise,
                sgst_paise=tax.sgst_paise,
                igst_paise=tax.igst_paise,
            )
        )
    return priced


def _totals(lines: list[_PricedLine]) -> tuple[int, int, int, int]:
    return (
        sum(line.taxable_paise for line in lines),
        sum(line.cgst_paise for line in lines),
        sum(line.sgst_paise for line in lines),
        sum(line.igst_paise for line in lines),
    )


@router.post("/preview", response_model=InvoicePreviewOut)
def preview_invoice(
    body: InvoiceIn,
    db: Session = Depends(get_tenant_db),
) -> InvoicePreviewOut:
    """Read-only: computes the same GST totals create_invoice would, without
    writing anything. Lets the invoice editor show live totals as lines change."""
    company = _get_company_or_400(db)
    customer = _get_customer_or_400(db, body.customer_id)
    same_state = customer.state_code == company.state_code

    priced = _price_lines(db, body.lines, same_state)
    subtotal, cgst_total, sgst_total, igst_total = _totals(priced)
    return InvoicePreviewOut(
        place_of_supply_state_code=customer.state_code,
        subtotal_paise=subtotal,
        cgst_paise=cgst_total,
        sgst_paise=sgst_total,
        igst_paise=igst_total,
        grand_total_paise=subtotal + cgst_total + sgst_total + igst_total,
        lines=list(priced),  # type: ignore[arg-type]  # InvoiceLineOut reads matching fields off the dataclass
    )


@router.post("", response_model=InvoiceOut, status_code=status.HTTP_201_CREATED)
def create_invoice(
    body: InvoiceIn,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_tenant_db),
) -> Invoice:
    company = _get_company_or_400(db)
    customer = _get_customer_or_400(db, body.customer_id)
    same_state = customer.state_code == company.state_code

    invoice = Invoice(
        tenant_id=current_user.tenant_id,
        customer_id=customer.id,
        quote_id=body.quote_id,
        status="draft",
        place_of_supply_state_code=customer.state_code,
    )
    db.add(invoice)
    db.flush()

    priced = _price_lines(db, body.lines, same_state)
    for line in priced:
        db.add(
            InvoiceLine(
                tenant_id=current_user.tenant_id,
                invoice_id=invoice.id,
                item_id=line.item_id,
                description=line.description,
                hsn_sac=line.hsn_sac,
                quantity=line.quantity,
                unit_price_paise=line.unit_price_paise,
                gst_rate_bps=line.gst_rate_bps,
                taxable_paise=line.taxable_paise,
                cgst_paise=line.cgst_paise,
                sgst_paise=line.sgst_paise,
                igst_paise=line.igst_paise,
            )
        )

    subtotal, cgst_total, sgst_total, igst_total = _totals(priced)
    invoice.subtotal_paise = subtotal
    invoice.cgst_paise = cgst_total
    invoice.sgst_paise = sgst_total
    invoice.igst_paise = igst_total
    invoice.grand_total_paise = subtotal + cgst_total + sgst_total + igst_total
    db.flush()
    db.refresh(invoice)
    return invoice


@router.get("", response_model=list[InvoiceOut])
def list_invoices(db: Session = Depends(get_tenant_db)) -> list[Invoice]:
    return list(db.scalars(select(Invoice).order_by(Invoice.created_at.desc())))


@router.get("/{invoice_id}", response_model=InvoiceOut)
def get_invoice(invoice_id: uuid.UUID, db: Session = Depends(get_tenant_db)) -> Invoice:
    invoice = db.get(Invoice, invoice_id)
    if invoice is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="invoice not found")
    return invoice


@router.post("/{invoice_id}/issue", response_model=InvoiceOut)
def issue_invoice(
    invoice_id: uuid.UUID,
    current_user: CurrentUser = Depends(require_roles("owner", "accountant")),
    db: Session = Depends(get_tenant_db),
) -> Invoice:
    invoice = db.get(Invoice, invoice_id)
    if invoice is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="invoice not found")
    if invoice.status != "draft":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="only a draft invoice can be issued"
        )

    now = datetime.now(UTC)
    fy = financial_year_label(now.year, now.month)
    # Atomic fetch-and-increment: the INSERT..ON CONFLICT row lock is what makes
    # numbering gapless and race-free without an app-level lock (ledger posting
    # itself is milestone 2's job, not this one).
    number = db.execute(
        text(
            """
            INSERT INTO invoice_sequence (tenant_id, financial_year, next_number)
            VALUES (:tid, :fy, 2)
            ON CONFLICT (tenant_id, financial_year)
            DO UPDATE SET next_number = invoice_sequence.next_number + 1
            RETURNING next_number - 1
            """
        ),
        {"tid": str(current_user.tenant_id), "fy": fy},
    ).scalar_one()

    invoice.status = "issued"
    invoice.financial_year = fy
    invoice.number = number
    invoice.issued_at = now
    db.flush()

    post_journal(
        db,
        current_user.tenant_id,
        "invoice_issue",
        invoice.id,
        now.date(),
        f"Invoice {fy}/{number} issued",
        lines=[
            (ACCOUNTS_RECEIVABLE, invoice.grand_total_paise, 0),
            (SALES_REVENUE, 0, invoice.subtotal_paise),
            (OUTPUT_CGST_PAYABLE, 0, invoice.cgst_paise),
            (OUTPUT_SGST_PAYABLE, 0, invoice.sgst_paise),
            (OUTPUT_IGST_PAYABLE, 0, invoice.igst_paise),
        ],
    )
    db.flush()
    db.refresh(invoice)
    return invoice


@router.post("/{invoice_id}/cancel", response_model=InvoiceOut)
def cancel_invoice(
    invoice_id: uuid.UUID,
    current_user: CurrentUser = Depends(require_roles("owner", "accountant")),
    db: Session = Depends(get_tenant_db),
) -> Invoice:
    invoice = db.get(Invoice, invoice_id)
    if invoice is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="invoice not found")
    if invoice.status != "issued":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="only an issued invoice can be cancelled"
        )
    original_journal = db.scalar(
        select(Journal).where(
            Journal.source_type == "invoice_issue", Journal.source_id == invoice.id
        )
    )
    assert original_journal is not None  # every issued invoice has one, set at issue time

    invoice.status = "cancelled"
    now = datetime.now(UTC)
    invoice.cancelled_at = now
    db.flush()

    reverse_journal(
        db,
        current_user.tenant_id,
        original_journal,
        "invoice_cancel",
        now.date(),
        f"Invoice {invoice.financial_year}/{invoice.number} cancelled",
    )
    db.flush()
    db.refresh(invoice)
    return invoice


@router.get("/{invoice_id}/pdf")
def get_invoice_pdf(invoice_id: uuid.UUID, db: Session = Depends(get_tenant_db)) -> Response:
    invoice = db.get(Invoice, invoice_id)
    if invoice is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="invoice not found")
    if invoice.status != "issued":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="invoice is not issued yet"
        )
    company = _get_company_or_400(db)
    customer = db.get(Customer, invoice.customer_id)
    assert customer is not None
    pdf_bytes = render_invoice_pdf(company, customer, invoice, invoice.lines)
    return Response(content=pdf_bytes, media_type="application/pdf")
