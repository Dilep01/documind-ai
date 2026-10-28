"""Small deterministic development fixtures. No private or real invoice data."""

import hashlib
import json
from pathlib import Path

import pdfplumber
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen.canvas import Canvas

from documind_ai.errors import DocumentError

SAMPLE_NAMES = (
    "digital_basic.pdf",
    "digital_alternate.pdf",
    "missing_fields.pdf",
    "scan_needs_ocr.pdf",
    "mixed_needs_ocr.pdf",
)
BASIC_TRUTH = {
    "vendor_name": "Cedar Office Supplies",
    "customer_name": "Demo Learning Studio",
    "invoice_number": "INV-000042",
    "invoice_date": "2026-10-28",
    "due_date": "2026-11-11",
    "currency": "INR",
    "subtotal": "2500.00",
    "discount": "0.00",
    "tax": "450.00",
    "shipping": "0.00",
    "total": "2950.00",
    "amount_due": "2950.00",
}


def draw_invoice(canvas: Canvas, *, alternate: bool = False, missing: bool = False) -> None:
    width, height = A4
    canvas.setTitle("DocuMind synthetic development invoice")
    canvas.setAuthor("DocuMind AI synthetic fixture generator")
    canvas.setFillColor(colors.HexColor("#16384A"))
    canvas.rect(0, height - 105, width, 105, fill=1, stroke=0)
    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica-Bold", 22)
    canvas.drawString(42, height - 48, "DOCUMIND AI")
    canvas.setFont("Helvetica", 11)
    canvas.drawString(42, height - 73, "Synthetic invoice | Development fixture")
    canvas.setFillColor(colors.HexColor("#172C38"))
    canvas.setFont("Helvetica", 11)
    fields = [
        (
            "Supplier" if alternate else "Vendor",
            "Birch Software Services" if alternate else BASIC_TRUTH["vendor_name"],
        ),
        ("Bill To" if alternate else "Customer", BASIC_TRUTH["customer_name"]),
        (
            "Invoice No." if alternate else "Invoice Number",
            "BSS-000007" if alternate else BASIC_TRUTH["invoice_number"],
        ),
        (
            "Date Issued" if alternate else "Invoice Date",
            "28 Oct 2026" if alternate else BASIC_TRUTH["invoice_date"],
        ),
        ("Pay By" if alternate else "Due Date", BASIC_TRUTH["due_date"]),
        ("Currency", "INR"),
    ]
    y = height - 140
    for label, value in fields:
        if missing and label in {"Due Date", "Invoice Number", "Currency"}:
            continue
        canvas.drawString(42, y, f"{label}: {value}")
        y -= 24

    y = height - 325
    canvas.setFillColor(colors.HexColor("#E8EFF3"))
    canvas.rect(42, y - 8, width - 84, 25, fill=1, stroke=0)
    canvas.setFillColor(colors.HexColor("#172C38"))
    canvas.setFont("Helvetica-Bold", 10)
    for x, label in ((48, "Description"), (310, "Qty"), (360, "Unit price"), (472, "Amount")):
        canvas.drawString(x, y, label)
    canvas.setFont("Helvetica", 10)
    for offset, description, quantity, unit, total in (
        (30, "Notebook packs", "5", "200.00", "1000.00"),
        (54, "Desk organizer sets", "3", "500.00", "1500.00"),
    ):
        for x, value in ((48, description), (310, quantity), (360, unit), (472, total)):
            canvas.drawString(x, y - offset, value)
    canvas.setFont("Helvetica", 11)
    totals = [
        ("Net Amount" if alternate else "Subtotal", "2500.00"),
        ("Discount", "0.00"),
        ("Tax Amount" if alternate else "Tax", "450.00"),
        ("Shipping", "0.00"),
        ("Grand Total" if alternate else "Total", "2950.00"),
        ("Balance Due" if alternate else "Amount Due", "2950.00"),
    ]
    y -= 115
    for label, value in totals:
        if missing and label == "Total":
            continue
        canvas.drawString(305, y, f"{label}: INR {value}")
        y -= 24
    canvas.setFont("Helvetica", 9)
    canvas.setFillColor(colors.HexColor("#5E6A72"))
    canvas.drawString(42, 55, "Fictional parties. No real transaction. Not a tax invoice.")
    canvas.drawString(42, 40, "Review every extracted field and line item against this original.")


def generate_samples(directory: Path, *, overwrite: bool = False) -> list[Path]:
    directory = Path(directory)
    outputs = [directory / name for name in (*SAMPLE_NAMES, "manifest.json")]
    if not overwrite and any(path.exists() for path in outputs):
        raise DocumentError(
            "output_exists", "Sample files already exist. Use --overwrite to replace them."
        )
    directory.mkdir(parents=True, exist_ok=True)
    for name, alternate, missing in (
        ("digital_basic.pdf", False, False),
        ("digital_alternate.pdf", True, False),
        ("missing_fields.pdf", False, True),
    ):
        canvas = Canvas(str(directory / name), pagesize=A4, invariant=1)
        draw_invoice(canvas, alternate=alternate, missing=missing)
        canvas.save()

    with pdfplumber.open(directory / "digital_basic.pdf") as document:
        image = document.pages[0].to_image(resolution=100).original.copy()
    for name, mixed in (("scan_needs_ocr.pdf", False), ("mixed_needs_ocr.pdf", True)):
        canvas = Canvas(str(directory / name), pagesize=A4, invariant=1)
        if mixed:
            draw_invoice(canvas)
            canvas.showPage()
        canvas.drawImage(ImageReader(image), 0, 0, width=A4[0], height=A4[1])
        canvas.save()
    image.close()

    manifest = {
        "schema_version": "1.0",
        "purpose": "synthetic development fixtures, not a held-out evaluation set",
        "split": "development",
        "provenance": "Generated locally with ReportLab; all identities and transactions are fictional.",
        "limitations": "Two closely related labelled layouts; no accuracy/generalization claim.",
        "samples": [],
    }
    for name in SAMPLE_NAMES:
        truth = BASIC_TRUTH.copy()
        if name == "digital_alternate.pdf":
            truth.update(vendor_name="Birch Software Services", invoice_number="BSS-000007")
        if name == "missing_fields.pdf":
            truth.update(invoice_number=None, due_date=None, currency=None, total=None)
        manifest["samples"].append(
            {
                "file": name,
                "sha256": hashlib.sha256((directory / name).read_bytes()).hexdigest(),
                "family": "labelled_development_v1",
                "requires_ocr": name in {"scan_needs_ocr.pdf", "mixed_needs_ocr.pdf"},
                "ground_truth_headers": truth,
            }
        )
    (directory / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    return outputs
