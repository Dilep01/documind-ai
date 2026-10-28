from datetime import date
from decimal import Decimal

from pydantic import Field

from documind_ai.schemas import Contract, Money


class EditableItem(Contract):
    description: str = Field(min_length=1, max_length=500)
    quantity: Decimal = Field(gt=0, le=1_000_000, decimal_places=3, allow_inf_nan=False)
    unit_price: Money = Field(ge=0)
    amount: Money = Field(ge=0)


class InvoiceData(Contract):
    vendor_name: str | None = Field(default=None, max_length=256)
    customer_name: str | None = Field(default=None, max_length=256)
    invoice_number: str | None = Field(default=None, max_length=256)
    invoice_date: date | None = None
    due_date: date | None = None
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    subtotal: Money | None = Field(default=None, ge=0)
    discount: Money | None = Field(default=None, ge=0)
    tax: Money | None = Field(default=None, ge=0)
    shipping: Money | None = Field(default=None, ge=0)
    total: Money | None = Field(default=None, ge=0)
    amount_due: Money | None = Field(default=None, ge=0)
    totals_mode: str = Field(default="unknown", pattern=r"^(tax_exclusive|tax_inclusive|unknown)$")
    line_items: list[EditableItem] = Field(default_factory=list, max_length=300)


class EditRequest(Contract):
    expected_version: int = Field(ge=1)
    reason: str = Field(min_length=3, max_length=500)
    data: InvoiceData


class ApprovalRequest(Contract):
    expected_version: int = Field(ge=1)
    decision: str = Field(pattern=r"^(approved|rejected)$")
    reason: str = Field(min_length=5, max_length=500)
    acknowledge_warnings: bool = False


def validate_invoice(data: InvoiceData, *, duplicate: bool = False) -> list[dict]:
    issues = []

    def add(code, message, field=None, severity="error"):
        issues.append({"code": code, "message": message, "field": field, "severity": severity})

    for field in ("vendor_name", "invoice_number", "invoice_date", "currency", "total"):
        value = getattr(data, field)
        if value is None or (isinstance(value, str) and not value.strip()):
            add("required_field", "A reviewed value is required.", field)
    if data.currency and data.currency != "INR":
        add("unsupported_currency", "This release supports INR invoices.", "currency")
    if data.invoice_date and data.due_date and data.due_date < data.invoice_date:
        add("date_order", "Due date is before invoice date.", "due_date")
    if not data.line_items:
        add("missing_items", "Add or verify the invoice's line items.", "line_items")
    for index, item in enumerate(data.line_items):
        expected = (item.quantity * item.unit_price).quantize(Decimal("0.01"))
        if abs(expected - item.amount) > Decimal("0.01"):
            add(
                "line_amount_mismatch",
                f"Row {index + 1}: quantity × price differs from amount.",
                "line_items",
            )
    if data.line_items and data.subtotal is not None:
        if abs(sum(item.amount for item in data.line_items) - data.subtotal) > Decimal("0.01"):
            add("subtotal_mismatch", "Line-item sum differs from the printed subtotal.", "subtotal")
    components = (data.subtotal, data.discount, data.tax, data.shipping, data.total)
    if all(value is not None for value in components) and data.totals_mode != "unknown":
        expected = data.subtotal - data.discount + data.shipping
        if data.totals_mode == "tax_exclusive":
            expected += data.tax
        if abs(expected - data.total) > Decimal("0.01"):
            add(
                "total_mismatch",
                "Printed total differs from the selected totals calculation.",
                "total",
            )
    else:
        add(
            "incomplete_totals_check",
            "All totals components and an explicit tax mode are needed to check arithmetic.",
            "total",
            "warning",
        )
    if duplicate:
        add(
            "possible_duplicate",
            "This file or invoice identity matches another record. Verify before approving.",
            None,
            "warning",
        )
    return issues
