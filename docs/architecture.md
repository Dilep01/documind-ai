# Application architecture

DocuMind is a local modular monolith. API, worker, and processing subprocess share domain code. PostgreSQL owns business state; local content-addressed storage owns originals and previews.

## Ingestion and processing

The API authenticates the user, checks upload boundaries/signatures, stages an original, and inserts blob/document/job records. Identical originals share a blob, but every upload gets its own history. Filesystem and database commits are separate: an interrupted upload can leave an unreferenced original. Retention is safer than deleting a shared original; reconciliation is an operator task in this release.

One worker claims jobs using `FOR UPDATE SKIP LOCKED`, grants a lease, and increments attempts. OCR runs in a subprocess with a deadline. The parent refreshes the lease and retries interruption up to three times. Recovery is at-least-once, not exactly-once. A completed extraction is published transactionally with a unique job/run relationship.

Native text comes first. Scanned/vector-only pages are rendered for Tesseract. OCR line IDs preserve reading order while word coordinates map back to the original preview. Orientation detection is best effort. A misleading native text layer may evade this heuristic.

The baseline recognizes explicit colon-labelled headers and simple Description/Qty/Unit price/Amount rows. Candidates retain raw values, nulls, conflicts, source quotes, token IDs, and boxes. Complex layouts require review.

## Revisions and approval

An invoice has a current integer version. Saving inserts an immutable revision with normalized header columns and a versioned JSON line-item snapshot. Row locks and expected-version checks prevent silent overwrite. Reprocessing preserves human revisions.

Approval references one revision. Edits reset review state. Missing values/arithmetic errors block approval; warnings need acknowledgement and a reason. Default personal-workspace policy permits self-approval. Set `DOCUMIND_ALLOW_SELF_APPROVAL=false` to require another reviewer.

Only current approved revisions can be exported. Export content/hashes remain immutable after later edits. CSV user text is neutralized against spreadsheet formula execution. This is export automation, not payment or tax filing.

## Search and local models

Metadata lookup queries invoice fields. Keyword/semantic retrieval scopes documents by user access before fetching chunks. pgvector stores exact 768-dimensional embeddings. An unavailable local model leaves keyword search usable and prevents partial indexes from being marked complete.

Implementation change: reuse the already-installed `nomic-embed-text:latest` in local Ollama instead of downloading MiniLM/PyTorch on a memory-constrained computer. A different model/dimension requires reindexing. Record exact model digests with evaluation evidence; tags alone are mutable.

Experimental Q&A sends retrieved chunks as untrusted evidence to a local Qwen model with no tools. JSON schema and source-index validation check output structure/citation indices, not factual correctness. Verify the original. Collection totals use approved SQL records, not approximate retrieval.

## Security and operations

Passwords use Argon2; server-side sessions store hashed tokens and expire after eight hours. HttpOnly SameSite cookies, session-specific CSRF tokens, and Origin checks protect mutations. Uploaders see their records; reviewers/admins see the single organization workspace. No multi-tenant SaaS isolation is claimed.

Compose exposes only the web port on loopback. PostgreSQL has no host port. Local HTTP cookies are not Secure; any remote deployment requires HTTPS, secure cookies, and a separate review. Previews are images, originals download as attachments, and logs contain IDs/errors rather than document text.

Alembic's initial migration uses frozen SQL. Future changes need new migrations. Backups quiesce writes and include both DB and originals; restore verification uses a separately named temporary database.
