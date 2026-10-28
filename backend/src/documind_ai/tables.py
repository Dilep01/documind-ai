"""Limited row parser; unresolved layouts remain visible for manual review."""

import re
from decimal import Decimal

from documind_ai.headers import line_evidence, text_lines
from documind_ai.normalization import parse_money
from documind_ai.schemas import InvoiceLineItem, PageText


def extract_items(pages: list[PageText]) -> list[InvoiceLineItem]:
    items = []
    row = re.compile(r"^(.+?)\s+(\d+(?:\.\d{1,3})?)\s+([\d,.]+)\s+([\d,.]+)$")
    for page in pages:
        inside = False
        for tokens in text_lines(page):
            text = " ".join(token.text for token in tokens)
            lower = text.lower()
            if "description" in lower and "qty" in lower and "amount" in lower:
                inside = True
                continue
            if inside and re.match(
                r"^(subtotal|net amount|discount|tax|total|grand total)\s*:", lower
            ):
                inside = False
            match = row.fullmatch(text) if inside else None
            if match:
                try:
                    items.append(
                        InvoiceLineItem(
                            description=match[1],
                            quantity=Decimal(match[2]),
                            unit_price=parse_money(match[3]),
                            amount=parse_money(match[4]),
                            evidence=[line_evidence(page, tokens, text)],
                        )
                    )
                except ValueError:
                    continue
    return items
