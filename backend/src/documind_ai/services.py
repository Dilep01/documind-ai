import csv
import io
import json
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from documind_ai.database import AuditEvent, Document, Invoice, Revision, User
from documind_ai.review import InvoiceData


def audit(db: Session, actor: str | None, action: str, document_id=None, **details):
    db.add(AuditEvent(actor_id=actor, action=action, document_id=document_id, details=details))


def visible_documents(user: User):
    query = select(Document).where(Document.deleted.is_(False))
    return query.where(Document.created_by == user.id) if user.role == "uploader" else query


def accessible(db: Session, user: User, document_id: str) -> Document:
    document = db.scalar(visible_documents(user).where(Document.id == document_id))
    if document is None:
        raise HTTPException(404, "Document not found.")
    return document


def latest_revision(db: Session, invoice: Invoice) -> Revision:
    revision = db.scalar(
        select(Revision).where(
            Revision.invoice_id == invoice.id, Revision.version == invoice.version
        )
    )
    if revision is None:
        raise HTTPException(409, "This document has no reviewable extraction yet.")
    return revision


def make_revision(
    db: Session, invoice: Invoice, data: InvoiceData, issues: list, actor: str, reason: str
) -> Revision:
    revision = Revision(
        invoice_id=invoice.id,
        version=invoice.version,
        vendor_name=data.vendor_name,
        invoice_number=data.invoice_number,
        invoice_date=data.invoice_date,
        currency=data.currency,
        total=data.total,
        payload=data.model_dump(mode="json"),
        issues=issues,
        created_by=actor,
        reason=reason,
    )
    db.add(revision)
    db.flush()
    return revision


def business_duplicate(db: Session, document: Document, data: InvoiceData) -> bool:
    if document.duplicate_of:
        return True
    if not all((data.vendor_name, data.invoice_number, data.currency, data.total is not None)):
        return False
    query = (
        select(Revision.id)
        .join(Invoice, Revision.invoice_id == Invoice.id)
        .join(Document, Invoice.document_id == Document.id)
        .where(
            Invoice.document_id != document.id,
            Document.deleted.is_(False),
            Revision.version == Invoice.version,
            Revision.vendor_name.ilike(
                data.vendor_name.strip().replace("%", "\\%").replace("_", "\\_")
            ),
            Revision.invoice_number == data.invoice_number,
            Revision.currency == data.currency,
            Revision.total == data.total,
        )
    )
    return db.scalar(query.limit(1)) is not None


def safe_csv(value) -> str:
    text = "" if value is None else str(value)
    dangerous = text.startswith(("\t", "\r", "\n")) or text.lstrip().startswith(
        ("=", "+", "-", "@")
    )
    return "'" + text if dangerous else text


def export_content(rows: list[dict], format: str) -> str:
    if format == "json":
        return json.dumps({"schema_version": "1.0", "invoices": rows}, indent=2) + "\n"
    stream = io.StringIO(newline="")
    columns = [
        "revision_id",
        "document_id",
        "vendor_name",
        "invoice_number",
        "invoice_date",
        "currency",
        "total",
    ]
    writer = csv.DictWriter(stream, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({key: safe_csv(row.get(key)) for key in columns})
    return stream.getvalue()


def validate_upload(name: str, data: bytes) -> tuple[str, str]:
    suffix = Path(name).suffix.lower()
    if suffix not in {".pdf", ".png", ".jpg", ".jpeg"}:
        raise HTTPException(415, "Use PDF, PNG, or JPEG files.")
    if suffix == ".pdf":
        if b"%PDF-" not in data[:1024]:
            raise HTTPException(415, "The file content does not match a PDF.")
        return ".pdf", "application/pdf"
    from PIL import Image, UnidentifiedImageError

    try:
        with Image.open(io.BytesIO(data)) as image:
            expected = "PNG" if suffix == ".png" else "JPEG"
            if image.format != expected or image.width * image.height > 30_000_000:
                raise HTTPException(415, "Unsupported image content or image dimensions.")
            image.verify()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise HTTPException(415, "The image is not readable.") from exc
    return suffix, "image/png" if suffix == ".png" else "image/jpeg"
