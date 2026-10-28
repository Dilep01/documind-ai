"""Authenticated, revision-aware local invoice application."""

import hashlib
import json
import logging
import os
import time
from collections import defaultdict, deque
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Literal

import httpx
from fastapi import Depends, FastAPI, File, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import Field
from sqlalchemy import delete, func, or_, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from documind_ai import __version__
from documind_ai.auth import (
    DUMMY_HASH,
    admin,
    create_session,
    current_user,
    hash_password,
    reviewer,
    verify_password,
)
from documind_ai.config import settings
from documind_ai.database import (
    Approval,
    AuditEvent,
    Blob,
    Chunk,
    Document,
    ExportBatch,
    ExtractionRun,
    Invoice,
    Job,
    LoginSession,
    Revision,
    User,
    get_db,
    uid,
)
from documind_ai.intelligence import answer_question, embed
from documind_ai.review import ApprovalRequest, EditRequest, validate_invoice
from documind_ai.schemas import Contract
from documind_ai.services import (
    accessible,
    audit,
    business_duplicate,
    export_content,
    latest_revision,
    make_revision,
    validate_upload,
    visible_documents,
)

app = FastAPI(title="DocuMind AI", version=__version__, docs_url="/api/docs", redoc_url=None)
login_attempts: dict[str, deque] = defaultdict(deque)
logger = logging.getLogger("documind")


@app.middleware("http")
async def request_boundaries(request: Request, call_next):
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        origin = request.headers.get("origin")
        if origin and origin not in settings().origins:
            return JSONResponse({"detail": "This origin is not permitted."}, status_code=403)
        length = request.headers.get("content-length")
        if length and (not length.isdigit() or int(length) > 21 * 1024 * 1024):
            return JSONResponse({"detail": "Request exceeds 21 MB."}, status_code=413)
        if request.url.path == "/api/v1/documents" and not length:
            return JSONResponse(
                {"detail": "Uploads require a Content-Length header."}, status_code=411
            )
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: blob:; connect-src 'self'; frame-ancestors 'none'; object-src 'none'"
    )
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response


class LoginRequest(Contract):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=200)


class UserRequest(Contract):
    username: str = Field(pattern=r"^[a-zA-Z0-9_.-]{3,80}$")
    password: str = Field(min_length=12, max_length=200)
    role: Literal["uploader", "reviewer", "admin"]


class ExportRequest(Contract):
    document_ids: list[str] = Field(min_length=1, max_length=100)
    format: Literal["csv", "json"] = "csv"
    idempotency_key: str = Field(min_length=8, max_length=100)


class QuestionRequest(Contract):
    question: str = Field(min_length=3, max_length=500)
    document_id: str | None = None


def user_json(user: User) -> dict:
    return {"id": user.id, "username": user.username, "role": user.role, "active": user.active}


@app.get("/api/v1/health")
def health():
    return {"status": "ok", "version": __version__, "deployment": "local"}


@app.get("/api/v1/ready")
def ready(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ready"}
    except Exception as exc:
        raise HTTPException(503, "Database is unavailable.") from exc


@app.post("/api/v1/auth/login")
def login(body: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    key = request.client.host if request.client else "local"
    attempts = login_attempts[key]
    while attempts and attempts[0] < time.monotonic() - 60:
        attempts.popleft()
    if len(attempts) >= 8:
        raise HTTPException(429, "Too many sign-in attempts. Try again in a minute.")
    attempts.append(time.monotonic())
    user = db.scalar(select(User).where(User.username == body.username))
    valid = verify_password(user.password_hash if user else DUMMY_HASH, body.password)
    if not user or not valid or not user.active:
        raise HTTPException(401, "Incorrect username or password.")
    old_token = request.cookies.get("documind_session")
    if old_token:
        from documind_ai.auth import token_hash

        db.execute(delete(LoginSession).where(LoginSession.token_hash == token_hash(old_token)))
    token, session = create_session(db, user)
    audit(db, user.id, "auth.login")
    db.commit()
    response.set_cookie(
        "documind_session",
        token,
        httponly=True,
        samesite="strict",
        secure=settings().cookie_secure,
        max_age=8 * 3600,
        path="/",
    )
    return {"user": user_json(user), "csrf_token": session.csrf_token}


@app.get("/api/v1/auth/me")
def me(request: Request, user: User = Depends(current_user)):
    return {
        "user": user_json(user),
        "csrf_token": request.state.login_session.csrf_token,
        "allow_self_approval": settings().allow_self_approval,
    }


@app.post("/api/v1/auth/logout")
def logout(
    request: Request,
    response: Response,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    db.delete(request.state.login_session)
    audit(db, user.id, "auth.logout")
    db.commit()
    response.delete_cookie("documind_session", path="/")
    return {"ok": True}


@app.get("/api/v1/users")
def users(user: User = Depends(admin), db: Session = Depends(get_db)):
    return [user_json(account) for account in db.scalars(select(User).order_by(User.created_at))]


@app.post("/api/v1/users", status_code=201)
def add_user(body: UserRequest, user: User = Depends(admin), db: Session = Depends(get_db)):
    if db.scalar(select(User).where(User.username == body.username)):
        raise HTTPException(409, "Username already exists.")
    account = User(
        username=body.username, password_hash=hash_password(body.password), role=body.role
    )
    db.add(account)
    db.flush()
    audit(db, user.id, "user.created", account_id=account.id, role=account.role)
    db.commit()
    return user_json(account)


@app.post("/api/v1/documents", status_code=202)
async def upload(
    file: UploadFile = File(...), user: User = Depends(current_user), db: Session = Depends(get_db)
):
    data = await file.read(20 * 1024 * 1024 + 1)
    await file.close()
    if not data or len(data) > 20 * 1024 * 1024:
        raise HTTPException(413, "Upload must be between 1 byte and 20 MB.")
    name = (file.filename or "document").replace("\\", "/").split("/")[-1][:255]
    suffix, media_type = validate_upload(name, data)
    digest = hashlib.sha256(data).hexdigest()
    config = settings()
    directory = config.storage / "originals"
    directory.mkdir(parents=True, exist_ok=True)
    storage_key = digest + suffix
    path = directory / storage_key
    # Originals are content-addressed. Exclusive creation prevents partial replacement of a shared blob.
    if not path.exists():
        staged = directory / (uid() + ".staging")
        staged.write_bytes(data)
        try:
            import os

            os.link(staged, path)
        except FileExistsError:
            pass
        finally:
            staged.unlink(missing_ok=True)
    db.execute(
        insert(Blob)
        .values(sha256=digest, storage_key=storage_key, size_bytes=len(data), media_type=media_type)
        .on_conflict_do_nothing()
    )
    # Never disclose another uploader's record ID through the duplicate relationship.
    duplicate = db.scalar(
        visible_documents(user)
        .where(Document.blob_hash == digest)
        .order_by(Document.created_at)
        .limit(1)
    )
    document = Document(
        name=name,
        blob_hash=digest,
        created_by=user.id,
        duplicate_of=duplicate.id if duplicate else None,
    )
    db.add(document)
    db.flush()
    job = Job(document_id=document.id)
    db.add(job)
    db.flush()
    audit(db, user.id, "document.uploaded", document.id, job_id=job.id, duplicate=bool(duplicate))
    db.commit()
    return {"document_id": document.id, "job_id": job.id, "duplicate_of": document.duplicate_of}


def summary(db: Session, document: Document) -> dict:
    invoice = db.scalar(select(Invoice).where(Invoice.document_id == document.id))
    revision = latest_revision(db, invoice) if invoice else None
    job = db.scalar(
        select(Job).where(Job.document_id == document.id).order_by(Job.created_at.desc()).limit(1)
    )
    return {
        "id": document.id,
        "name": document.name,
        "created_at": document.created_at,
        "status": document.status,
        "kind": document.kind,
        "classification": document.classification,
        "duplicate_of": document.duplicate_of,
        "index_status": document.index_status,
        "review_status": invoice.review_status if invoice else "pending",
        "version": invoice.version if invoice else 0,
        "vendor_name": revision.vendor_name if revision else None,
        "invoice_number": revision.invoice_number if revision else None,
        "currency": revision.currency if revision else None,
        "total": str(revision.total) if revision and revision.total is not None else None,
        "issue_count": len(revision.issues) if revision else 0,
        "job": {
            "id": job.id,
            "state": job.state,
            "stage": job.stage,
            "error": job.error,
            "attempts": job.attempts,
        }
        if job
        else None,
    }


@app.get("/api/v1/documents")
def documents(
    q: str = "",
    status: str = "",
    limit: int = 50,
    offset: int = 0,
    date_from: date | None = None,
    date_to: date | None = None,
    min_total: Decimal | None = None,
    invoice_number: str | None = None,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    limit, offset = min(max(limit, 1), 100), max(offset, 0)
    query = visible_documents(user)
    if len(q) > 200:
        raise HTTPException(422, "Search text is too long.")
    if q:
        pattern = "%" + q.replace("%", "\\%").replace("_", "\\_") + "%"
        ids = (
            select(Invoice.document_id)
            .join(Revision, Revision.invoice_id == Invoice.id)
            .where(
                Revision.version == Invoice.version,
                or_(Revision.vendor_name.ilike(pattern), Revision.invoice_number.ilike(pattern)),
            )
        )
        query = query.where(or_(Document.name.ilike(pattern), Document.id.in_(ids)))
    if status in {"approved", "needs_review", "rejected"}:
        query = query.where(
            Document.id.in_(select(Invoice.document_id).where(Invoice.review_status == status))
        )
    elif status:
        query = query.where(Document.status == status)
    if any(value is not None for value in (date_from, date_to, min_total, invoice_number)):
        metadata = (
            select(Invoice.document_id)
            .join(Revision, Revision.invoice_id == Invoice.id)
            .where(Revision.version == Invoice.version)
        )
        if date_from is not None:
            metadata = metadata.where(Revision.invoice_date >= date_from)
        if date_to is not None:
            metadata = metadata.where(Revision.invoice_date <= date_to)
        if min_total is not None:
            if not min_total.is_finite() or min_total < 0:
                raise HTTPException(422, "Minimum total must be a finite nonnegative amount.")
            metadata = metadata.where(Revision.total >= min_total, Revision.currency == "INR")
        if invoice_number is not None:
            metadata = metadata.where(Revision.invoice_number == invoice_number)
        query = query.where(Document.id.in_(metadata))
    rows = [
        summary(db, doc)
        for doc in db.scalars(
            query.order_by(Document.created_at.desc()).limit(limit).offset(offset)
        )
    ]
    return {"items": rows, "limit": limit, "offset": offset}


@app.get("/api/v1/documents/{document_id}")
def detail(document_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    document = accessible(db, user, document_id)
    result = summary(db, document)
    invoice = db.scalar(select(Invoice).where(Invoice.document_id == document.id))
    revision = latest_revision(db, invoice) if invoice else None
    run = db.scalar(
        select(ExtractionRun)
        .where(ExtractionRun.document_id == document.id)
        .order_by(ExtractionRun.created_at.desc())
        .limit(1)
    )
    result.update(
        data=revision.payload if revision else None,
        issues=revision.issues if revision else [],
        revision_id=revision.id if revision else None,
        extraction=run.result if run else None,
        duration_ms=run.duration_ms if run else None,
        revisions=[
            {
                "id": rev.id,
                "version": rev.version,
                "reason": rev.reason,
                "created_at": rev.created_at,
            }
            for rev in db.scalars(
                select(Revision)
                .where(Revision.invoice_id == invoice.id)
                .order_by(Revision.version.desc())
            )
        ]
        if invoice
        else [],
    )
    return result


@app.get("/api/v1/documents/{document_id}/pages/{number}")
def preview(
    document_id: str, number: int, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    accessible(db, user, document_id)
    if number < 1 or number > 20:
        raise HTTPException(404, "Page not found.")
    path = settings().storage / "previews" / document_id / f"{number}.png"
    if not path.is_file():
        raise HTTPException(404, "Page preview is not ready.")
    return FileResponse(path, media_type="image/png")


@app.get("/api/v1/documents/{document_id}/original")
def original(document_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    document = accessible(db, user, document_id)
    blob = db.get(Blob, document.blob_hash)
    return FileResponse(
        settings().storage / "originals" / blob.storage_key,
        media_type="application/octet-stream",
        filename=document.name,
    )


@app.post("/api/v1/documents/{document_id}/reprocess", status_code=202)
def reprocess(document_id: str, user: User = Depends(reviewer), db: Session = Depends(get_db)):
    document = accessible(db, user, document_id)
    db.execute(select(Document).where(Document.id == document_id).with_for_update())
    if db.scalar(
        select(Job).where(Job.document_id == document_id, Job.state.in_(["queued", "processing"]))
    ):
        raise HTTPException(409, "A processing job is already active.")
    job = Job(document_id=document_id)
    db.add(job)
    document.status = "queued"
    db.flush()
    audit(db, user.id, "document.reprocess_requested", document_id, job_id=job.id)
    db.commit()
    return {"job_id": job.id}


@app.get("/api/v1/jobs/{job_id}")
def job_detail(job_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(404, "Job not found.")
    accessible(db, user, job.document_id)
    return {
        "id": job.id,
        "state": job.state,
        "stage": job.stage,
        "attempts": job.attempts,
        "error": job.error,
        "heartbeat_at": job.heartbeat_at,
    }


@app.patch("/api/v1/invoices/{document_id}")
def edit(
    document_id: str,
    body: EditRequest,
    user: User = Depends(reviewer),
    db: Session = Depends(get_db),
):
    document = accessible(db, user, document_id)
    invoice = db.scalar(select(Invoice).where(Invoice.document_id == document_id).with_for_update())
    if invoice is None:
        raise HTTPException(409, "Wait for document processing.")
    if invoice.version != body.expected_version:
        raise HTTPException(409, "A newer revision exists. Reload before editing.")
    invoice.version += 1
    invoice.review_status = "needs_review"
    issues = validate_invoice(body.data, duplicate=business_duplicate(db, document, body.data))
    revision = make_revision(db, invoice, body.data, issues, user.id, body.reason)
    audit(
        db,
        user.id,
        "invoice.revised",
        document_id,
        revision_id=revision.id,
        version=invoice.version,
    )
    db.commit()
    return {"version": invoice.version, "revision_id": revision.id, "issues": issues}


@app.post("/api/v1/invoices/{document_id}/approvals")
def approve(
    document_id: str,
    body: ApprovalRequest,
    user: User = Depends(reviewer),
    db: Session = Depends(get_db),
):
    document = accessible(db, user, document_id)
    invoice = db.scalar(select(Invoice).where(Invoice.document_id == document_id).with_for_update())
    if not invoice or invoice.version != body.expected_version:
        raise HTTPException(409, "The record changed. Reload before making a decision.")
    revision = latest_revision(db, invoice)
    if db.scalar(select(Approval).where(Approval.revision_id == revision.id)):
        raise HTTPException(
            409, "This revision already has a decision. Save a new revision to reconsider."
        )
    if body.decision == "approved":
        if document.status != "succeeded":
            raise HTTPException(409, "All pages must finish processing before approval.")
        if not settings().allow_self_approval and document.created_by == user.id:
            raise HTTPException(403, "A different reviewer must approve this upload.")
        if any(issue["severity"] == "error" for issue in revision.issues):
            raise HTTPException(422, "Resolve blocking validation issues before approving.")
        if revision.issues and not body.acknowledge_warnings:
            raise HTTPException(422, "Acknowledge warnings and record your review reason.")
    invoice.review_status = body.decision
    db.add(
        Approval(
            revision_id=revision.id, user_id=user.id, decision=body.decision, reason=body.reason
        )
    )
    audit(
        db,
        user.id,
        f"invoice.{body.decision}",
        document_id,
        revision_id=revision.id,
        warnings_acknowledged=body.acknowledge_warnings,
    )
    db.commit()
    return {"review_status": invoice.review_status}


@app.post("/api/v1/exports")
def export(body: ExportRequest, user: User = Depends(reviewer), db: Session = Depends(get_db)):
    request_hash = hashlib.sha256(
        json.dumps(
            {"format": body.format, "documents": sorted(set(body.document_ids))}, sort_keys=True
        ).encode()
    ).hexdigest()
    lock_key = int.from_bytes(
        hashlib.sha256(body.idempotency_key.encode()).digest()[:8], "big", signed=True
    )
    db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": lock_key})
    existing = db.scalar(
        select(ExportBatch).where(ExportBatch.idempotency_key == body.idempotency_key)
    )
    if existing:
        if existing.created_by != user.id:
            raise HTTPException(409, "Export key is already in use.")
        if existing.request_hash != request_hash:
            raise HTTPException(409, "This export key refers to a different selection or format.")
        return {"id": existing.id, "format": existing.format, "sha256": existing.content_hash}
    rows, revision_ids = [], []
    for document_id in sorted(set(body.document_ids)):
        accessible(db, user, document_id)
        invoice = db.scalar(
            select(Invoice).where(Invoice.document_id == document_id).with_for_update()
        )
        if not invoice or invoice.review_status != "approved":
            raise HTTPException(409, "Only current approved revisions can be exported.")
        revision = latest_revision(db, invoice)
        approval = db.scalar(
            select(Approval).where(
                Approval.revision_id == revision.id, Approval.decision == "approved"
            )
        )
        if not approval:
            raise HTTPException(409, "The current revision has no approval.")
        revision_ids.append(revision.id)
        rows.append({"revision_id": revision.id, "document_id": document_id, **revision.payload})
    content = export_content(rows, body.format)
    batch = ExportBatch(
        created_by=user.id,
        format=body.format,
        content_hash=hashlib.sha256(content.encode()).hexdigest(),
        revision_ids=revision_ids,
        content=content,
        idempotency_key=body.idempotency_key,
        request_hash=request_hash,
    )
    db.add(batch)
    db.flush()
    for document_id in set(body.document_ids):
        audit(db, user.id, "invoice.exported", document_id, export_id=batch.id)
    db.commit()
    return {"id": batch.id, "format": batch.format, "sha256": batch.content_hash}


@app.get("/api/v1/exports")
def export_history(user: User = Depends(reviewer), db: Session = Depends(get_db)):
    return [
        {
            "id": batch.id,
            "created_at": batch.created_at,
            "format": batch.format,
            "sha256": batch.content_hash,
            "count": len(batch.revision_ids),
        }
        for batch in db.scalars(
            select(ExportBatch).order_by(ExportBatch.created_at.desc()).limit(100)
        )
    ]


@app.get("/api/v1/exports/{export_id}/download")
def download_export(export_id: str, user: User = Depends(reviewer), db: Session = Depends(get_db)):
    batch = db.get(ExportBatch, export_id)
    if not batch:
        raise HTTPException(404, "Export not found.")
    return Response(
        batch.content,
        media_type="text/csv" if batch.format == "csv" else "application/json",
        headers={
            "Content-Disposition": f'attachment; filename="documind-{batch.id}.{batch.format}"'
        },
    )


@app.get("/api/v1/audit")
def audit_history(
    document_id: str | None = None,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    query = select(AuditEvent)
    if document_id:
        accessible(db, user, document_id)
        query = query.where(AuditEvent.document_id == document_id)
    elif user.role == "uploader":
        query = query.where(AuditEvent.actor_id == user.id)
    return [
        {
            "id": event.id,
            "action": event.action,
            "document_id": event.document_id,
            "details": event.details,
            "created_at": event.created_at,
        }
        for event in db.scalars(query.order_by(AuditEvent.created_at.desc()).limit(100))
    ]


@app.get("/api/v1/dashboard")
def dashboard(user: User = Depends(current_user), db: Session = Depends(get_db)):
    ids = visible_documents(user).with_only_columns(Document.id)
    count = db.scalar(select(func.count()).select_from(Document).where(Document.id.in_(ids))) or 0
    approved = (
        db.scalar(
            select(func.count())
            .select_from(Invoice)
            .where(Invoice.document_id.in_(ids), Invoice.review_status == "approved")
        )
        or 0
    )
    pending = (
        db.scalar(
            select(func.count())
            .select_from(Invoice)
            .where(Invoice.document_id.in_(ids), Invoice.review_status == "needs_review")
        )
        or 0
    )
    amount = db.scalar(
        select(func.sum(Revision.total))
        .join(Invoice, Revision.invoice_id == Invoice.id)
        .where(
            Invoice.document_id.in_(ids),
            Invoice.review_status == "approved",
            Revision.version == Invoice.version,
            Revision.currency == "INR",
        )
    )
    return {
        "documents": count,
        "approved": approved,
        "needs_review": pending,
        "approved_total_inr": str(amount or "0.00"),
    }


def search_sources(
    db: Session, user: User, q: str, mode: str, document_id: str | None = None
) -> list[dict]:
    ids = visible_documents(user).with_only_columns(Document.id)
    query = (
        select(Chunk, Document.name)
        .join(Document, Chunk.document_id == Document.id)
        .where(Chunk.document_id.in_(ids))
    )
    if document_id:
        accessible(db, user, document_id)
        query = query.where(Chunk.document_id == document_id)
    if mode == "semantic":
        try:
            vector = embed([q], query=True)[0]
        except (httpx.HTTPError, ValueError, KeyError) as exc:
            raise HTTPException(
                503, "Local semantic model is unavailable. Use keyword search."
            ) from exc
        query = query.where(
            Chunk.embedding.is_not(None), Chunk.model == settings().embedding_model
        ).order_by(Chunk.embedding.cosine_distance(vector))
    else:
        words = [word for word in q.split() if len(word) > 2][:8]
        if not words:
            return []
        query = query.where(
            or_(
                *(
                    Chunk.text.ilike("%" + word.replace("%", "\\%").replace("_", "\\_") + "%")
                    for word in words
                )
            )
        ).order_by(Chunk.document_id, Chunk.page_number)
    results, seen = [], set()
    for chunk, name in db.execute(query.limit(5 if document_id else 30)):
        # A long invoice must not monopolize every collection-search result.
        if not document_id and chunk.document_id in seen:
            continue
        seen.add(chunk.document_id)
        results.append(
            {
                "id": chunk.id,
                "document_id": chunk.document_id,
                "name": name,
                "page_number": chunk.page_number,
                "text": chunk.text,
            }
        )
        if len(results) == 5:
            break
    return results


@app.get("/api/v1/search")
def search(
    q: str,
    mode: Literal["keyword", "semantic"] = "keyword",
    document_id: str | None = None,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    if not 2 <= len(q) <= 500:
        raise HTTPException(422, "Use between 2 and 500 characters.")
    return {"mode": mode, "items": search_sources(db, user, q, mode, document_id)}


@app.post("/api/v1/questions")
def question(
    body: QuestionRequest, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    if any(
        term in body.question.lower()
        for term in ("sum of all", "total value of", "across all", "total of all")
    ):
        return {
            "answer": "Use the approved invoice dashboard or export for collection totals.",
            "citations": [],
            "abstained": True,
        }
    try:
        sources = search_sources(db, user, body.question, "semantic", body.document_id)
        return answer_question(body.question, sources)
    except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
        raise HTTPException(
            503, "The local answer model is unavailable. You can still search and review documents."
        ) from exc


@app.get("/api/v1/models/status")
def model_status(user: User = Depends(current_user)):
    try:
        with httpx.Client(timeout=3, trust_env=False) as client:
            response = client.get(settings().ollama_url + "/api/tags")
            response.raise_for_status()
            names = [model["name"] for model in response.json().get("models", [])]
        return {
            "available": True,
            "embedding_model": settings().embedding_model,
            "chat_model": settings().chat_model,
            "installed": names,
        }
    except (httpx.HTTPError, ValueError, KeyError):
        return {
            "available": False,
            "notice": "Core processing remains available without local models.",
        }


@app.post("/api/v1/documents/{document_id}/suggestions")
def suggestions(document_id: str, user: User = Depends(reviewer), db: Session = Depends(get_db)):
    from documind_ai.suggestions import suggest_fields

    accessible(db, user, document_id)
    run = db.scalar(
        select(ExtractionRun)
        .where(ExtractionRun.document_id == document_id)
        .order_by(ExtractionRun.created_at.desc())
        .limit(1)
    )
    if not run:
        raise HTTPException(409, "Wait for extraction before requesting suggestions.")
    try:
        return {
            "suggestions": suggest_fields(run.result.get("pages", [])),
            "notice": "Suggestions never change or approve records. Check the original before applying.",
        }
    except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
        raise HTTPException(
            503, "The optional local model is unavailable. Manual review remains available."
        ) from exc


frontend = Path(
    os.environ.get(
        "DOCUMIND_FRONTEND", str(Path(__file__).resolve().parents[3] / "frontend" / "dist")
    )
)
if frontend.is_dir():
    app.mount("/", StaticFiles(directory=frontend, html=True), name="frontend")
