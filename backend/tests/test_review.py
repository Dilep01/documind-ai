from decimal import Decimal

import pytest
from documind_ai.review import InvoiceData, validate_invoice
from documind_ai.services import export_content, safe_csv
from pydantic import ValidationError


@pytest.fixture
def valid_data():
    return InvoiceData(
        vendor_name="Fictional Vendor",
        invoice_number="INV-001",
        invoice_date="2026-10-28",
        currency="INR",
        subtotal="100.00",
        discount="0.00",
        tax="18.00",
        shipping="0.00",
        total="118.00",
        totals_mode="tax_exclusive",
        line_items=[
            {"description": "Example", "quantity": "2", "unit_price": "50.00", "amount": "100.00"}
        ],
    )


def test_arithmetic_modes_and_missing_values(valid_data):
    assert validate_invoice(valid_data) == []
    altered = valid_data.model_copy(update={"total": Decimal("120.00")})
    assert any(issue["code"] == "total_mismatch" for issue in validate_invoice(altered))
    inclusive = valid_data.model_copy(
        update={"totals_mode": "tax_inclusive", "total": Decimal("100.00")}
    )
    assert validate_invoice(inclusive) == []
    omitted_mode = InvoiceData.model_validate(inclusive.model_dump(exclude={"totals_mode"}))
    omitted_issues = validate_invoice(omitted_mode)
    assert any(issue["code"] == "incomplete_totals_check" for issue in omitted_issues)
    assert not any(issue["code"] == "total_mismatch" for issue in omitted_issues)
    assert any(issue["severity"] == "error" for issue in validate_invoice(InvoiceData()))


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-1", "0.001"])
def test_invalid_review_amounts(value):
    with pytest.raises(ValidationError):
        InvoiceData(total=value)


@pytest.mark.parametrize(
    "value", ["=SUM(A1:A2)", "+command", "-command", "@command", "  =formula", "\tbad"]
)
def test_spreadsheet_injection(value):
    assert safe_csv(value).startswith("'")


def test_csv_and_json_exports_are_distinct():
    rows = [
        {
            "revision_id": "r",
            "document_id": "d",
            "vendor_name": "=formula",
            "invoice_number": "00001",
            "total": "1.00",
        }
    ]
    assert "'=formula" in export_content(rows, "csv")
    assert '"invoice_number": "00001"' in export_content(rows, "json")
