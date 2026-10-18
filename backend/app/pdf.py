import io
from collections.abc import Sequence

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.models import Company, Customer, Invoice, InvoiceLine


def _rupees(paise: int) -> str:
    return f"Rs {paise / 100:,.2f}"


def render_invoice_pdf(
    company: Company, customer: Customer, invoice: Invoice, lines: Sequence[InvoiceLine]
) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4)
    styles = getSampleStyleSheet()

    elements = [
        Paragraph(company.legal_name, styles["Title"]),
        Paragraph(f"GSTIN: {company.gstin} | {company.address}", styles["Normal"]),
        Spacer(1, 10 * mm),
        Paragraph(f"Invoice {invoice.financial_year}/{invoice.number}", styles["Heading2"]),
        Paragraph(f"Bill to: {customer.name} ({customer.gstin or 'B2C'})", styles["Normal"]),
        Paragraph(customer.billing_address, styles["Normal"]),
        Paragraph(f"Place of supply: {invoice.place_of_supply_state_code}", styles["Normal"]),
        Spacer(1, 6 * mm),
    ]

    table_data = [["Description", "HSN/SAC", "Qty", "Rate", "Taxable", "CGST", "SGST", "IGST"]]
    for line in lines:
        table_data.append(
            [
                line.description,
                line.hsn_sac,
                str(line.quantity),
                _rupees(line.unit_price_paise),
                _rupees(line.taxable_paise),
                _rupees(line.cgst_paise),
                _rupees(line.sgst_paise),
                _rupees(line.igst_paise),
            ]
        )
    table = Table(table_data, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
            ]
        )
    )
    elements.append(table)
    elements.append(Spacer(1, 6 * mm))
    elements.append(
        Paragraph(f"Grand total: {_rupees(invoice.grand_total_paise)}", styles["Heading3"])
    )

    doc.build(elements)
    return buf.getvalue()
