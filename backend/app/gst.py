from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal


def financial_year_label(year: int, month: int) -> str:
    """India's FY runs Apr-Mar: a Jan-Mar date belongs to the FY that started last April."""
    start_year = year if month >= 4 else year - 1
    return f"{start_year}-{(start_year + 1) % 100:02d}"


def _round_paise(value: Decimal) -> int:
    return int(value.to_integral_value(rounding=ROUND_HALF_UP))


@dataclass(frozen=True)
class LineTax:
    cgst_paise: int
    sgst_paise: int
    igst_paise: int

    @property
    def total_paise(self) -> int:
        return self.cgst_paise + self.sgst_paise + self.igst_paise


def compute_line_tax(taxable_paise: int, rate_bps: int, same_state: bool) -> LineTax:
    """rate_bps is the full GST rate in basis points (1800 = 18%).

    Same state (CGST+SGST): each half of the rate is rounded independently, which is
    how real GST invoices compute it -- CGST and SGST on one line can differ by up to
    1 paise from each other as a result.
    Different state (IGST): the full rate, rounded once.
    """
    taxable = Decimal(taxable_paise)
    if same_state:
        half_rate = Decimal(rate_bps) / Decimal(2) / Decimal(10000)
        cgst = _round_paise(taxable * half_rate)
        sgst = _round_paise(taxable * half_rate)
        return LineTax(cgst_paise=cgst, sgst_paise=sgst, igst_paise=0)

    full_rate = Decimal(rate_bps) / Decimal(10000)
    igst = _round_paise(taxable * full_rate)
    return LineTax(cgst_paise=0, sgst_paise=0, igst_paise=igst)
