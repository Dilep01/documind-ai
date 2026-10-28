import hashlib
from datetime import date
from decimal import Decimal

import pytest
from documind_ai.cli import main
from documind_ai.errors import DocumentError
from documind_ai.normalization import AmbiguousDateError, parse_date, parse_money
from documind_ai.pipeline import ExtractionLimits, extract_document, extract_pdf
from documind_ai.schemas import ExtractionResult
from reportlab.lib.pdfencrypt import StandardEncryption
from reportlab.pdfgen.canvas import Canvas


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("INR 1,234.50", "1234.50"),
        ("Rs. 1,23,456.78", "123456.78"),
        ("0", "0.00"),
        ("-10.20", "-10.20"),
    ],
)
def test_decimal_money(raw, expected):
    assert parse_money(raw) == Decimal(expected)


@pytest.mark.parametrize(
    "raw", ["1,23.00", "1.234", "NaN", "1e3", "", "INR 1 USD", "10000000000000000", "1 234.50"]
)
def test_invalid_money(raw):
    with pytest.raises(ValueError):
        parse_money(raw)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("2026-10-28", date(2026, 10, 28)),
        ("28 Oct 2026", date(2026, 10, 28)),
        ("28/10/2026", date(2026, 10, 28)),
        ("10/28/2026", date(2026, 10, 28)),
        ("10/10/2026", date(2026, 10, 10)),
    ],
)
def test_dates(raw, expected):
    assert parse_date(raw) == expected


def test_ambiguous_date():
    with pytest.raises(AmbiguousDateError):
        parse_date("03/04/2026")


@pytest.mark.parametrize("raw", ["2026-02-30", "30/30/2026", "next week", "2026/10/28"])
def test_invalid_dates(raw):
    with pytest.raises(ValueError):
        parse_date(raw)


def test_digital_evidence_and_json_roundtrip(samples):
    path = samples / "digital_basic.pdf"
    result = extract_pdf(path)
    assert result.processing_status == "succeeded"
    assert result.invoice.invoice_number.value == "INV-000042"
    assert result.invoice.total.value == Decimal("2950.00")
    assert result.file.sha256 == hashlib.sha256(path.read_bytes()).hexdigest()
    assert len(result.line_items) == 2
    assert result.line_items[0].amount == Decimal("1000.00")
    assert result.human_review_required is True
    for name, value in result.invoice:
        if value.value is not None:
            assert value.evidence, name
        for source in value.evidence:
            page = result.pages[source.page_number - 1]
            tokens = {token.token_id: token for token in page.tokens}
            assert " ".join(tokens[token_id].text for token_id in source.token_ids) == source.quote
            assert source.box.x0 >= 0 and source.box.x1 <= page.width
    restored = ExtractionResult.model_validate_json(result.model_dump_json())
    assert restored == result
    assert '"2950.00"' in result.model_dump_json()


def test_alternate_and_missing_fields(samples):
    alternative = extract_pdf(samples / "digital_alternate.pdf")
    assert alternative.invoice.invoice_number.value == "BSS-000007"
    assert alternative.invoice.invoice_date.value == date(2026, 10, 28)
    missing = extract_pdf(samples / "missing_fields.pdf")
    assert missing.invoice.total.value is None
    assert missing.invoice.currency.value is None
    assert missing.invoice.invoice_number.value is None
    assert any(
        issue.field == "total" and issue.code == "missing_required_field"
        for issue in missing.issues
    )


def test_scans_are_not_misrepresented_without_ocr(samples):
    scan = extract_pdf(samples / "scan_needs_ocr.pdf")
    assert scan.processing_status == "needs_ocr"
    assert scan.invoice.total.value is None
    mixed = extract_pdf(samples / "mixed_needs_ocr.pdf")
    assert mixed.processing_status == "partial"
    assert [page.status for page in mixed.pages] == ["native_text", "needs_ocr"]


def test_conflicts_are_unresolved(tmp_path):
    path = tmp_path / "conflict.pdf"
    c = Canvas(str(path))
    for i, line in enumerate(
        ["Total: INR 100.00", "Total: INR 200.00", "Invoice Date: 03/04/2026"]
    ):
        c.drawString(40, 750 - i * 25, line)
    c.save()
    result = extract_pdf(path)
    assert result.invoice.total.value is None
    assert result.invoice.total.raw_values == ["INR 100.00", "INR 200.00"]
    assert result.invoice.invoice_date.value is None
    assert {issue.code for issue in result.issues} >= {"conflicting_field_values", "ambiguous_date"}


def test_bad_input_and_limits(tmp_path, samples):
    path = tmp_path / "bad.pdf"
    path.write_bytes(b"not a pdf")
    with pytest.raises(DocumentError, match="PDF header"):
        extract_pdf(path)
    path.write_bytes(b"%PDF-1.4\ninvalid")
    with pytest.raises(DocumentError):
        extract_pdf(path)
    with pytest.raises(DocumentError, match="exceeds"):
        extract_pdf(samples / "digital_basic.pdf", ExtractionLimits(max_bytes=10))
    with pytest.raises(DocumentError, match="exceeds"):
        extract_pdf(samples / "mixed_needs_ocr.pdf", ExtractionLimits(max_pages=1))
    with pytest.raises(DocumentError):
        extract_pdf(tmp_path / "missing.pdf")


def test_encrypted_and_blank(tmp_path):
    encrypted = tmp_path / "encrypted.pdf"
    c = Canvas(str(encrypted), encrypt=StandardEncryption("private-test-password"))
    c.drawString(40, 750, "Private test fixture")
    c.save()
    with pytest.raises(DocumentError, match="Password"):
        extract_pdf(encrypted)
    blank = tmp_path / "blank.pdf"
    c = Canvas(str(blank))
    c.showPage()
    c.save()
    assert extract_pdf(blank).processing_status == "empty"


def test_cli_protects_source_and_existing_output(samples, tmp_path, capsys):
    source = samples / "digital_basic.pdf"
    before = source.read_bytes()
    assert main(["extract", str(source), "--output", str(source), "--overwrite"]) == 2
    assert source.read_bytes() == before
    output = tmp_path / "result.json"
    assert main(["extract", str(source), "--output", str(output)]) == 0
    output.write_text("preserved", encoding="utf-8")
    assert main(["extract", str(source), "--output", str(output)]) == 2
    assert output.read_text() == "preserved"
    assert main(["extract", str(source), "--output", str(output), "--overwrite"]) == 0
    ExtractionResult.model_validate_json(output.read_text())


def test_real_ocr(samples, tmp_path):
    import shutil

    if not shutil.which("tesseract"):
        pytest.skip("Real OCR runs in the supplied Docker image")
    result = extract_document(samples / "scan_needs_ocr.pdf", preview_dir=tmp_path / "preview")
    assert result.pages[0].extraction_method == "ocr"
    assert result.invoice.invoice_number.value == "INV-000042"
    assert result.invoice.total.value == Decimal("2950.00")
    assert (tmp_path / "preview" / "1.png").is_file()
