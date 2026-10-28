"""Versioned contracts shared by extraction, JSON output, and later API work."""

from datetime import date
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Money = Annotated[Decimal, Field(allow_inf_nan=False, max_digits=18, decimal_places=2)]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class BoundingBox(Contract):
    """PDF points, using pdfplumber's top-left origin for each page."""

    x0: float = Field(allow_inf_nan=False)
    top: float = Field(allow_inf_nan=False)
    x1: float = Field(allow_inf_nan=False)
    bottom: float = Field(allow_inf_nan=False)

    @model_validator(mode="after")
    def ordered(self) -> "BoundingBox":
        if self.x1 < self.x0 or self.bottom < self.top:
            raise ValueError("Bounding box coordinates must be ordered")
        return self


class WordToken(Contract):
    token_id: int = Field(ge=1)
    text: str
    box: BoundingBox
    line_id: str | None = None


class PageText(Contract):
    page_number: int = Field(ge=1)
    width: float = Field(gt=0, allow_inf_nan=False)
    height: float = Field(gt=0, allow_inf_nan=False)
    rotation: int
    status: Literal["native_text", "needs_ocr", "empty", "ocr_text", "ocr_failed"]
    extraction_method: Literal["native", "ocr", "none"] = "native"
    text: str
    tokens: list[WordToken]
    image_count: int = Field(ge=0)


class SourceEvidence(Contract):
    page_number: int = Field(ge=1)
    token_ids: list[int] = Field(min_length=1)
    quote: str
    box: BoundingBox
    method: Literal["label_rule"] = "label_rule"


class FieldValue[T](Contract):
    value: T | None = None
    raw_values: list[str] = Field(default_factory=list)
    evidence: list[SourceEvidence] = Field(default_factory=list)


class InvoiceFields(Contract):
    vendor_name: FieldValue[str] = Field(default_factory=FieldValue[str])
    customer_name: FieldValue[str] = Field(default_factory=FieldValue[str])
    invoice_number: FieldValue[str] = Field(default_factory=FieldValue[str])
    invoice_date: FieldValue[date] = Field(default_factory=FieldValue[date])
    due_date: FieldValue[date] = Field(default_factory=FieldValue[date])
    currency: FieldValue[str] = Field(default_factory=FieldValue[str])
    subtotal: FieldValue[Money] = Field(default_factory=FieldValue[Money])
    discount: FieldValue[Money] = Field(default_factory=FieldValue[Money])
    tax: FieldValue[Money] = Field(default_factory=FieldValue[Money])
    shipping: FieldValue[Money] = Field(default_factory=FieldValue[Money])
    total: FieldValue[Money] = Field(default_factory=FieldValue[Money])
    amount_due: FieldValue[Money] = Field(default_factory=FieldValue[Money])


class ValidationIssue(Contract):
    code: str
    severity: Literal["warning", "error"]
    message: str
    field: str | None = None
    page_number: int | None = Field(default=None, ge=1)


class FileMetadata(Contract):
    name: str
    size_bytes: int = Field(gt=0)
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    media_type: Literal["application/pdf"] = "application/pdf"


class InvoiceLineItem(Contract):
    description: str = Field(min_length=1, max_length=500)
    quantity: Decimal = Field(gt=0, le=1_000_000, decimal_places=3)
    unit_price: Money
    amount: Money
    evidence: list[SourceEvidence] = Field(default_factory=list)


class ExtractionResult(Contract):
    schema_version: Literal["1.0"] = "1.0"
    pipeline_version: str
    file: FileMetadata
    processing_status: Literal["succeeded", "partial", "needs_ocr", "empty"]
    review_status: Literal["needs_review"] = "needs_review"
    human_review_required: Literal[True] = True
    capabilities: list[str] = Field(
        default_factory=lambda: ["native_pdf_text", "labelled_header_fields", "source_evidence"]
    )
    line_items_status: Literal["extracted", "needs_review"] = "needs_review"
    line_items: list[InvoiceLineItem] = Field(default_factory=list)
    pages: list[PageText] = Field(min_length=1)
    invoice: InvoiceFields
    issues: list[ValidationIssue]
