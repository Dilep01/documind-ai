import time

import httpx
from sqlalchemy import delete, select

from documind_ai.config import settings
from documind_ai.database import (
    Blob,
    Chunk,
    Document,
    ExtractionRun,
    Invoice,
    Job,
    Page,
    now,
    session_factory,
)
from documind_ai.errors import DocumentError
from documind_ai.intelligence import classify, embed, instruction_like, split_chunks
from documind_ai.pipeline import extract_document
from documind_ai.review import InvoiceData, validate_invoice
from documind_ai.services import audit, business_duplicate, make_revision


def process(job_id: str):
    started = time.monotonic()
    with session_factory()() as db:
        job = db.get(Job, job_id)
        if not job:
            return
        if db.scalar(select(ExtractionRun).where(ExtractionRun.job_id == job_id)):
            job.state, job.stage = "succeeded", "complete"
            db.get(Document, job.document_id).status = "succeeded"
            db.commit()
            return
        document = db.get(Document, job.document_id)
        blob = db.get(Blob, document.blob_hash)
        path = settings().storage / "originals" / blob.storage_key
        document_id, actor_id = document.id, document.created_by
    try:
        result = extract_document(path, preview_dir=settings().storage / "previews" / document_id)
    except (DocumentError, RuntimeError) as exc:
        with session_factory()() as db:
            job = db.get(Job, job_id)
            job.state, job.stage = "failed", "failed"
            job.error = f"{getattr(exc, 'code', 'processing_failed')}: {exc}"[:500]
            job.finished_at = now()
            db.get(Document, document_id).status = "failed"
            audit(
                db,
                actor_id,
                "document.processing_failed",
                document_id,
                code=getattr(exc, "code", "processing_failed"),
            )
            db.commit()
        return
    combined = "\n".join(page.text for page in result.pages)
    classification = classify(combined)
    chunks = []
    for page in result.pages:
        for position, content in enumerate(split_chunks(page.text)):
            chunks.append(
                Chunk(
                    document_id=document_id,
                    page_number=page.page_number,
                    position=position,
                    text=content,
                )
            )
    index_status = "keyword_only"
    if chunks:
        try:
            for offset in range(0, len(chunks), 8):
                group = chunks[offset : offset + 8]
                vectors = embed([chunk.text for chunk in group])
                for chunk, vector in zip(group, vectors, strict=True):
                    chunk.embedding, chunk.model = vector, settings().embedding_model
            index_status = "semantic_ready"
        except (httpx.HTTPError, ValueError, KeyError):
            # A partial index must not masquerade as complete coverage.
            for chunk in chunks:
                chunk.embedding, chunk.model = None, None
    with session_factory()() as db:
        job = db.scalar(select(Job).where(Job.id == job_id).with_for_update())
        if db.scalar(select(ExtractionRun).where(ExtractionRun.job_id == job_id)):
            return
        document = db.get(Document, document_id)
        document.status = result.processing_status
        document.kind, document.classification = classification["label"], classification
        document.index_status = index_status
        run = ExtractionRun(
            job_id=job_id,
            document_id=document_id,
            result=result.model_dump(mode="json"),
            duration_ms=round((time.monotonic() - started) * 1000),
        )
        db.add(run)
        db.flush()
        for page in result.pages:
            db.add(
                Page(
                    run_id=run.id,
                    document_id=document_id,
                    number=page.page_number,
                    text=page.text,
                    data=page.model_dump(mode="json"),
                )
            )
        db.execute(delete(Chunk).where(Chunk.document_id == document_id))
        db.add_all(chunks)
        invoice = db.scalar(
            select(Invoice).where(Invoice.document_id == document_id).with_for_update()
        )
        if invoice is None:
            invoice = Invoice(document_id=document_id)
            db.add(invoice)
            db.flush()
            values = {name: value.value for name, value in result.invoice}
            # Tax mode must be explicitly reviewed; never infer it from arithmetic alone.
            values["totals_mode"] = "unknown"
            values["line_items"] = [
                item.model_dump(exclude={"evidence"}) for item in result.line_items
            ]
            data = InvoiceData.model_validate(values)
            issues = validate_invoice(data, duplicate=business_duplicate(db, document, data))
            if instruction_like(combined):
                issues.append(
                    {
                        "code": "instruction_like_content",
                        "severity": "warning",
                        "field": None,
                        "message": "Instruction-like document text was detected. Inspect the original manually; model assistance is restricted.",
                    }
                )
            if result.processing_status != "succeeded":
                issues.append(
                    {
                        "code": "incomplete_processing",
                        "severity": "error",
                        "field": None,
                        "message": "One or more pages could not be fully read.",
                    }
                )
            make_revision(
                db, invoice, data, issues, actor_id, "Initial extraction; human review required"
            )
        # Reprocessing deliberately keeps all existing human revisions and approvals.
        job.state, job.stage, job.error, job.finished_at = "succeeded", "complete", None, now()
        audit(
            db,
            actor_id,
            "document.processed",
            document_id,
            run_id=run.id,
            page_count=len(result.pages),
            method_counts={
                method: sum(p.extraction_method == method for p in result.pages)
                for method in ("native", "ocr")
            },
        )
        db.commit()
