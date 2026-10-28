# Learn by tracing one invoice

1. **Python/contracts:** read `schemas.py` and `normalization.py`. Explain nulls, Decimal amounts, ambiguous dates, and JSON. Change one case and test it.
2. **Extraction:** follow `pipeline.py`, `headers.py`, and `tables.py`. Compare digital/scanned samples. Add a label alias and reproduce a conflicting label.
3. **OCR:** inspect `ocr.py`. Trace pixel-to-page boxes and reading order. Explain why OCR confidence is not an accuracy probability.
4. **SQL:** read `database.py` and the frozen migration. Trace document → job → run → invoice → revision → approval → export. Explain historical snapshots.
5. **HTTP/security:** follow `api.py` and `auth.py`. Trace session, CSRF, role checks, transactions, and response. Test an uploader requesting another user's preview.
6. **Workers:** read `worker.py` and `processing.py`. Interrupt a job, inspect leases/attempts, and explain idempotent publication.
7. **Frontend:** trace inbox/review state in `frontend/src/main.tsx`, `api.ts`, and CSS. Explain unsaved changes, source highlights, and stale-version conflicts.
8. **ML:** inspect family splits before reading `training.py` metrics. Add a less formulaic held-out family and compare results.
9. **Search/Q&A:** compare exact lookup, keywords, and embeddings. Ask an unanswerable question and verify its answer/citations.
10. **Release/recovery:** inspect Docker/Compose and `scripts/recovery.py`. Run full tests and restore a snapshot into a separate database.

Keep notes about what changed, what failed, how you checked it, and what remains uncertain. Being able to explain and modify the code is the learning objective.
