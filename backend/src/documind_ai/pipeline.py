"""Synchronous native-PDF pipeline; no network access or model inference."""

import hashlib
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

import pdfplumber
from pdfminer.pdfdocument import PDFPasswordIncorrect, PDFTextExtractionNotAllowed
from pdfminer.pdfparser import PDFSyntaxError
from pdfminer.psparser import PSEOF
from pdfplumber.utils.exceptions import PdfminerException
from PIL import Image, ImageOps, UnidentifiedImageError

from documind_ai import __version__
from documind_ai.errors import DocumentError
from documind_ai.headers import extract_headers
from documind_ai.schemas import (
    BoundingBox,
    ExtractionResult,
    FileMetadata,
    PageText,
    ValidationIssue,
    WordToken,
)
from documind_ai.tables import extract_items


@dataclass(frozen=True)
class ExtractionLimits:
    max_bytes: int = 20 * 1024 * 1024
    max_pages: int = 20
    max_characters_per_page: int = 100_000

    def __post_init__(self) -> None:
        if min(self.max_bytes, self.max_pages, self.max_characters_per_page) <= 0:
            raise ValueError("All extraction limits must be positive")


def read_pdf(path: Path, limits: ExtractionLimits) -> bytes:
    if path.suffix.lower() != ".pdf":
        raise DocumentError(
            "unsupported_file_type",
            "This milestone accepts PDF files. Image OCR is not available yet.",
        )
    try:
        if not path.is_file():
            raise DocumentError("file_not_found", "The input PDF is not a readable regular file.")
        if path.stat().st_size > limits.max_bytes:
            raise DocumentError("file_too_large", f"The file exceeds {limits.max_bytes} bytes.")
        with path.open("rb") as stream:
            data = stream.read(limits.max_bytes + 1)
    except OSError as exc:
        raise DocumentError("file_read_failed", "The input PDF could not be read.") from exc
    if len(data) > limits.max_bytes:
        raise DocumentError("file_too_large", f"The file exceeds {limits.max_bytes} bytes.")
    if b"%PDF-" not in data[:1024]:
        raise DocumentError("invalid_pdf", "The file does not contain a PDF header.")
    return data


def extract_pdf(
    path: Path,
    limits: ExtractionLimits | None = None,
    *,
    ocr: bool = False,
    preview_dir: Path | None = None,
) -> ExtractionResult:
    path = Path(path)
    limits = limits or ExtractionLimits()
    data = read_pdf(path, limits)
    pages: list[PageText] = []
    issues: list[ValidationIssue] = []
    try:
        with pdfplumber.open(BytesIO(data)) as document:
            if not document.doc.is_extractable:
                raise DocumentError("restricted_pdf", "Text extraction is restricted in this PDF.")
            if not document.pages:
                raise DocumentError("empty_pdf", "The PDF contains no pages.")
            if len(document.pages) > limits.max_pages:
                raise DocumentError("too_many_pages", f"The PDF exceeds {limits.max_pages} pages.")
            for number, page in enumerate(document.pages, start=1):
                if len(page.chars) > limits.max_characters_per_page:
                    raise DocumentError(
                        "page_too_complex", f"Page {number} has too many characters."
                    )
                words = page.extract_words(x_tolerance=2, y_tolerance=3)
                tokens = [
                    WordToken(
                        token_id=index,
                        text=word["text"],
                        box=BoundingBox(
                            x0=word["x0"], top=word["top"], x1=word["x1"], bottom=word["bottom"]
                        ),
                    )
                    for index, word in enumerate(words, start=1)
                ]
                usable = any(any(char.isalnum() for char in token.text) for token in tokens)
                has_artwork = bool(page.images or page.curves or page.rects or page.lines)
                status = "native_text" if usable else ("needs_ocr" if has_artwork else "empty")
                pages.append(
                    PageText(
                        page_number=number,
                        width=page.width,
                        height=page.height,
                        rotation=page.rotation,
                        status=status,
                        text=page.extract_text(x_tolerance=2, y_tolerance=3) or "",
                        tokens=tokens,
                        image_count=len(page.images),
                    )
                )
                if preview_dir is not None or (ocr and status == "needs_ocr"):
                    if page.width * page.height * 4 > 30_000_000:
                        raise DocumentError(
                            "page_too_complex", "Page exceeds the rendering pixel limit."
                        )
                    image = page.to_image(resolution=144).original
                    if preview_dir is not None:
                        preview_dir.mkdir(parents=True, exist_ok=True)
                        image.save(preview_dir / f"{number}.png")
                    if ocr and status == "needs_ocr":
                        from documind_ai.ocr import recognize

                        try:
                            pages[-1] = recognize(image, number, page.width, page.height)
                            status = pages[-1].status
                        except RuntimeError:
                            status = "ocr_failed"
                            pages[-1].status = status
                            pages[-1].extraction_method = "ocr"
                    image.close()
                if status not in {"native_text", "ocr_text"}:
                    issues.append(
                        ValidationIssue(
                            code=(
                                "ocr_required"
                                if status == "needs_ocr"
                                else "ocr_failed"
                                if status == "ocr_failed"
                                else "empty_page"
                            ),
                            severity="warning",
                            page_number=number,
                            message=(
                                "No usable native text was found. OCR is needed and is not implemented yet."
                                if status in {"needs_ocr", "ocr_failed"}
                                else "No native text or visible page objects were found."
                            ),
                        )
                    )
                elif sum(len(token.text) for token in tokens) < 30:
                    issues.append(
                        ValidationIssue(
                            code="sparse_native_text",
                            severity="warning",
                            page_number=number,
                            message="Little native text was found. Inspect this page manually.",
                        )
                    )
    except PdfminerException as exc:
        cause = exc.args[0] if exc.args else None
        if isinstance(cause, PDFPasswordIncorrect):
            raise DocumentError(
                "encrypted_pdf", "Password-protected PDFs are not supported yet."
            ) from exc
        if isinstance(cause, PDFTextExtractionNotAllowed):
            raise DocumentError(
                "restricted_pdf", "Text extraction is restricted in this PDF."
            ) from exc
        raise DocumentError("invalid_pdf", "The PDF could not be parsed safely.") from exc
    except PDFPasswordIncorrect as exc:
        raise DocumentError(
            "encrypted_pdf", "Password-protected PDFs are not supported yet."
        ) from exc
    except PDFTextExtractionNotAllowed as exc:
        raise DocumentError("restricted_pdf", "Text extraction is restricted in this PDF.") from exc
    except (PDFSyntaxError, PSEOF, ValueError, TypeError, KeyError, IndexError, OSError) as exc:
        raise DocumentError("invalid_pdf", "The PDF could not be parsed safely.") from exc

    invoice, field_issues = extract_headers(pages)
    issues.extend(field_issues)
    statuses = {page.status for page in pages}
    if statuses <= {"native_text", "ocr_text"}:
        result_status = "succeeded"
    elif statuses & {"native_text", "ocr_text"}:
        result_status = "partial"
    elif statuses & {"needs_ocr", "ocr_failed"}:
        result_status = "needs_ocr"
    else:
        result_status = "empty"
    return ExtractionResult(
        pipeline_version=__version__,
        file=FileMetadata(
            name=path.name, size_bytes=len(data), sha256=hashlib.sha256(data).hexdigest()
        ),
        processing_status=result_status,
        pages=pages,
        invoice=invoice,
        issues=issues,
        line_items=extract_items(pages),
        line_items_status="extracted" if extract_items(pages) else "needs_review",
    )


def extract_document(path: Path, *, preview_dir: Path | None = None) -> ExtractionResult:
    if path.suffix.lower() == ".pdf":
        return extract_pdf(path, ocr=True, preview_dir=preview_dir)
    if path.suffix.lower() not in {".png", ".jpg", ".jpeg"}:
        raise DocumentError("unsupported_file_type", "Use PDF, PNG, or JPEG.")
    try:
        if path.stat().st_size > ExtractionLimits().max_bytes:
            raise DocumentError("file_too_large", "Image exceeds 20 MB.")
        with Image.open(path) as source:
            if source.format not in {"PNG", "JPEG"}:
                raise DocumentError(
                    "invalid_image", "The image format does not match supported types."
                )
            if source.width * source.height > 30_000_000:
                raise DocumentError("image_too_large", "Image exceeds 30 million pixels.")
            image = ImageOps.exif_transpose(source).convert("RGB")
        if preview_dir is not None:
            preview_dir.mkdir(parents=True, exist_ok=True)
            image.save(preview_dir / "1.png")
        from documind_ai.ocr import recognize

        page = recognize(image, 1, image.width / 2, image.height / 2)
        image.close()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise DocumentError("invalid_image", "Image cannot be read safely.") from exc
    invoice, issues = extract_headers([page])
    items = extract_items([page])
    return ExtractionResult(
        pipeline_version=__version__,
        file=FileMetadata(
            name=path.name,
            size_bytes=path.stat().st_size,
            sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        ),
        processing_status="succeeded" if page.tokens else "needs_ocr",
        pages=[page],
        invoice=invoice,
        issues=issues,
        line_items=items,
        line_items_status="extracted" if items else "needs_review",
    )
