"""A deliberately narrow baseline: one labelled header field per text line."""

import re
from collections.abc import Callable, Iterator
from typing import Any

from documind_ai.normalization import (
    AmbiguousDateError,
    parse_currency,
    parse_date,
    parse_money,
    parse_text,
)
from documind_ai.schemas import (
    BoundingBox,
    InvoiceFields,
    PageText,
    SourceEvidence,
    ValidationIssue,
    WordToken,
)

# Labels must be followed by a colon. A new layout can extend this explicit baseline.
DEFINITIONS: dict[str, tuple[tuple[str, ...], Callable[[str], Any]]] = {
    "vendor_name": (("Vendor", "Vendor Name", "Supplier"), parse_text),
    "customer_name": (("Customer", "Customer Name", "Bill To"), parse_text),
    "invoice_number": (("Invoice Number", "Invoice No.", "Invoice No", "Invoice #"), parse_text),
    "invoice_date": (("Invoice Date", "Date Issued"), parse_date),
    "due_date": (("Due Date", "Pay By"), parse_date),
    "currency": (("Currency",), parse_currency),
    "subtotal": (("Subtotal", "Net Amount"), parse_money),
    "discount": (("Discount",), parse_money),
    "tax": (("Tax", "Tax Amount"), parse_money),
    "shipping": (("Shipping",), parse_money),
    "total": (("Total", "Grand Total", "Invoice Total"), parse_money),
    "amount_due": (("Amount Due", "Balance Due"), parse_money),
}
REQUIRED_FIELDS = ("vendor_name", "invoice_number", "invoice_date", "currency", "total")


def text_lines(page: PageText) -> Iterator[list[WordToken]]:
    if page.extraction_method == "ocr":
        grouped: dict[str, list[WordToken]] = {}
        for token in page.tokens:
            grouped.setdefault(token.line_id or str(token.token_id), []).append(token)
        yield from grouped.values()
        return
    line: list[WordToken] = []
    anchor = 0.0
    for token in sorted(page.tokens, key=lambda token: (token.box.top, token.box.x0)):
        if line and abs(token.box.top - anchor) > 3:
            yield sorted(line, key=lambda token: token.box.x0)
            line = []
        if not line:
            anchor = token.box.top
        line.append(token)
    if line:
        yield sorted(line, key=lambda token: token.box.x0)


def line_evidence(page: PageText, tokens: list[WordToken], quote: str) -> SourceEvidence:
    return SourceEvidence(
        page_number=page.page_number,
        token_ids=[token.token_id for token in tokens],
        quote=quote,
        box=BoundingBox(
            x0=min(token.box.x0 for token in tokens),
            top=min(token.box.top for token in tokens),
            x1=max(token.box.x1 for token in tokens),
            bottom=max(token.box.bottom for token in tokens),
        ),
    )


def extract_headers(pages: list[PageText]) -> tuple[InvoiceFields, list[ValidationIssue]]:
    patterns = {
        name: re.compile(r"^(?:" + "|".join(map(re.escape, labels)) + r")\s*:\s*(.+)$", re.I)
        for name, (labels, _) in DEFINITIONS.items()
    }
    collected: dict[str, list[tuple[Any, str, SourceEvidence, bool]]] = {
        name: [] for name in DEFINITIONS
    }
    issues: list[ValidationIssue] = []
    for page in pages:
        for tokens in text_lines(page):
            quote = " ".join(token.text for token in tokens)
            for name, pattern in patterns.items():
                match = pattern.fullmatch(quote)
                if not match:
                    continue
                raw = match[1].strip()
                evidence = line_evidence(page, tokens, quote)
                value, valid = None, True
                try:
                    value = DEFINITIONS[name][1](raw)
                except ValueError as exc:
                    valid = False
                    issues.append(
                        ValidationIssue(
                            code=(
                                "ambiguous_date"
                                if isinstance(exc, AmbiguousDateError)
                                else "invalid_field_value"
                            ),
                            severity="warning",
                            message=str(exc),
                            field=name,
                            page_number=page.page_number,
                        )
                    )
                collected[name].append((value, raw, evidence, valid))
                break

    fields: dict[str, Any] = {}
    for name, candidates in collected.items():
        values = {candidate[0] for candidate in candidates if candidate[3]}
        conflict = len(values) > 1
        if conflict:
            issues.append(
                ValidationIssue(
                    code="conflicting_field_values",
                    severity="warning",
                    field=name,
                    message="Multiple different values were found; choose the correct one in review.",
                )
            )
        fields[name] = {
            "value": (
                next(iter(values))
                if len(values) == 1 and all(candidate[3] for candidate in candidates)
                else None
            ),
            "raw_values": list(dict.fromkeys(candidate[1] for candidate in candidates)),
            "evidence": [candidate[2] for candidate in candidates],
        }
        if name in REQUIRED_FIELDS and not candidates:
            issues.append(
                ValidationIssue(
                    code="missing_required_field",
                    severity="warning",
                    field=name,
                    message="No supported labelled value was found for this required field.",
                )
            )
    invoice = InvoiceFields.model_validate(fields)
    if invoice.currency.value is not None and invoice.currency.value != "INR":
        issues.append(
            ValidationIssue(
                code="unsupported_currency",
                severity="warning",
                field="currency",
                message="This milestone supports INR invoices. The printed currency was preserved.",
            )
        )
    if (
        invoice.invoice_date.value is not None
        and invoice.due_date.value is not None
        and invoice.due_date.value < invoice.invoice_date.value
    ):
        issues.append(
            ValidationIssue(
                code="due_date_before_invoice_date",
                severity="warning",
                field="due_date",
                message="The due date precedes the invoice date; review the source.",
            )
        )
    return invoice, issues
