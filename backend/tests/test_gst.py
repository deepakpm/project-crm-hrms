from app.gst import compute_line_tax, financial_year_label


def test_financial_year_april_start() -> None:
    assert financial_year_label(2026, 4) == "2026-27"


def test_financial_year_march_belongs_to_previous_fy() -> None:
    assert financial_year_label(2026, 3) == "2025-26"


def test_intra_state_splits_into_cgst_and_sgst() -> None:
    # Rs 1,000.00 taxable at 18% intra-state -> Rs 90 CGST + Rs 90 SGST, no IGST.
    tax = compute_line_tax(taxable_paise=100_000, rate_bps=1800, same_state=True)
    assert tax.cgst_paise == 9_000
    assert tax.sgst_paise == 9_000
    assert tax.igst_paise == 0
    assert tax.total_paise == 18_000


def test_inter_state_charges_igst_only() -> None:
    # Same Rs 1,000.00 at 18% inter-state -> Rs 180 IGST, no CGST/SGST.
    tax = compute_line_tax(taxable_paise=100_000, rate_bps=1800, same_state=False)
    assert tax.cgst_paise == 0
    assert tax.sgst_paise == 0
    assert tax.igst_paise == 18_000
    assert tax.total_paise == 18_000


def test_rounding_half_up_on_odd_paise() -> None:
    # Rs 33.33 (3333 paise) at 18% intra-state: half-rate 9% of 3333 = 299.97 paise,
    # each of CGST and SGST rounds independently to 300 paise (round-half-up).
    tax = compute_line_tax(taxable_paise=3_333, rate_bps=1800, same_state=True)
    assert tax.cgst_paise == 300
    assert tax.sgst_paise == 300
    assert tax.total_paise == 600


def test_rounding_half_up_inter_state() -> None:
    # Rs 10.05 (1005 paise) at 5% inter-state: 1005 * 0.05 = 50.25 paise -> rounds to 50.
    tax = compute_line_tax(taxable_paise=1_005, rate_bps=500, same_state=False)
    assert tax.igst_paise == 50


def test_rounding_half_up_exactly_half_paise_rounds_up() -> None:
    # Rs 0.50 (50 paise) at 5% inter-state: 50 * 0.05 = 2.5 paise -> half-up rounds to 3.
    tax = compute_line_tax(taxable_paise=50, rate_bps=500, same_state=False)
    assert tax.igst_paise == 3
