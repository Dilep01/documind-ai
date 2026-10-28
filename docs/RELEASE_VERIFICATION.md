# DocuMind AI v0.1.0 local release candidate

Local release candidate verified on 28 October 2026. Source repository: [Dilep01/documind-ai](https://github.com/Dilep01/documind-ai). This application runs locally. No hosted production service or real customer usage is claimed.

## Implemented scope

The release covers bounded PDF/PNG/JPEG ingestion; native extraction and Tesseract OCR; evidence-linked header and limited table parsing; PostgreSQL records and migrations; leased processing jobs; immutable review revisions; manual approval and approved CSV/JSON snapshots; local accounts/roles/CSRF; keyword/semantic retrieval; optional grounded field suggestions and experimental Q&A; synthetic classification; local packaging; recovery scripts; and learning/presentation documentation.

The learning plan's broad capabilities are implemented within the documented limits. This is a local portfolio release candidate, not a universal document processor.

## Verification outcomes

| Check | Observed result |
| --- | --- |
| Full backend suite in Linux container | 57 passed; no skips |
| Frontend unit/contract checks | 4 passed |
| Desktop and mobile browser acceptance | 2 passed |
| Frontend production build | Passed |
| Ruff lint and formatting | Passed |
| Python dependency consistency | No broken requirements |
| Clean database installation | Both migrations applied; 14 tables; no metadata differences; repeat upgrade passed |
| Frontend dependency audit after test-runner update | 0 known reported vulnerabilities |
| Actual OCR with external networking disabled | Scanned sample processed; total 2950.00 extracted |
| Backup restored in separate PostgreSQL container | Passed counts and all 5 original-file hashes |
| Local semantic retrieval | Both controlled vendor queries returned supporting evidence in top five |
| Local invoice-total question | Expected printed amount returned with citation |
| Missing bank-account question | Abstained |
| Local field suggestions | HTTP 200; 12 source-checked suggestions on the digital sample |

Browser acceptance exercises upload, processing through the real worker, source highlighting, correction, versioned save, approval, CSV download, approval invalidation after another edit, and keyword search. The mobile test checks usability and absence of page-level horizontal overflow. The suite does not constitute comprehensive accessibility testing.

The backend suite includes actual PostgreSQL transactions and OCR, permission and CSRF boundaries, stale/concurrent review conflicts, duplicate processing, immutable export history, export idempotency, lease reclamation/retry limits, and rotated image recognition. Tests use isolated database schemas rather than workspace records. There is one upstream Starlette/HTTPX TestClient deprecation warning; tests pass, but this adapter needs attention during future dependency upgrades.

## Controlled document results

These are five related DEVELOPMENT fixtures, not held-out real-invoice accuracy. Each has 12 ground-truth header slots. Intentionally missing values count as correct when left null.

| Fixture | Correct header slots | Interpretation |
| --- | --- | --- |
| Digital basic | 12/12 | Explicit labelled layout |
| Digital alternate | 12/12 | Related layout/label aliases |
| Missing fields | 12/12 | Includes four intentionally absent values preserved as null |
| Raster scan | 9/12 | OCR misread customer/date labels and the invoice-number value |
| Mixed document | 11/12 | Native/OCR evidence exposed a conflicting invoice number |

The scan remains imperfect. Local comparisons with a different segmentation mode improved row grouping but did not reliably repair the header recognition. We retained the baseline and manual review rather than silently rewriting printed identifiers. The scan and mixed examples need human header/table correction; they are not automatically approved. The mixed fixture repeats content across pages and can produce duplicate line rows that validation exposes.

`evaluation/reports/local-release.json` records field-by-field matches, page methods, run duration, model responses, retrieval observations, and dashboard state. Durations include processing and optional indexing; they are not isolated OCR latency estimates. No general p95, business time-saving, or real-document accuracy claim is made.

## Classification experiment

The TF-IDF/Logistic Regression experiment uses 300 short synthetic TEXT records: 180 training, 60 validation, 60 testing, with template families separated. Its recorded test macro-F1 is 1.0 on this deliberately simple corpus. Lexical cues make it easy; this is neither OCR nor invoice-field extraction accuracy and does not establish real-document generalization. The 0.55 abstention threshold is an initial heuristic, not a calibrated real-world confidence probability. See the full classification report and data card.

## Actual model failure and mitigation

An unguarded Qwen probe repeated a false amount embedded as an instruction in synthetic document text. That failure is preserved in `evaluation/reports/model-probe-unguarded.json`.

The application now detects a limited set of instruction-like patterns, blocks model assistance for flagged context, and warns reviewers. The same probe then abstained without passing the flagged context to the model; see `model-probe.json`. The guard can miss obfuscated/indirect instructions. Valid JSON, source quotes, and citation indices also do not establish factual correctness. Q&A remains experimental, and the model has no application tools or approval authority.

## Environment and recovery

The Windows host was observed with about 15.3 GiB RAM and 12 logical CPUs. The checked image runs PostgreSQL 17/pgvector alongside Python 3.13.18, Tesseract 5.3.0, and the bundled React app. Processing uses one worker. The local models are `nomic-embed-text:latest` and `qwen3:1.7b`; installed upstream license notices are retained under `docs/model-licenses/`.

Observed model digests:

- nomic embedding: `0a109f422b47e3a30ba2b10eca18548e944e8a23073ee3f3e947efcf3c45e59f`
- Qwen 1.7B: `8f68893c685c3ddff2aa3fffce2aa60a30bb2da65ca488b61fff134a4d1730e7`

The recovery snapshot restored 7 documents, 11 revisions, 3 decisions, 3 exports, and 5 shared original blobs in a separate temporary database. Later acceptance runs add more fictional records; those counts describe the snapshot, not a permanent dashboard value. Only the safe restoration result is included in the repository. The private backup/configuration is ignored.

Dependencies are pinned in lockfiles. Container base tags still receive upstream updates; this is not a byte-for-byte reproducible operating-system claim. [GitHub Actions](https://github.com/Dilep01/documind-ai/actions/workflows/checks.yml) repeats backend and frontend checks on repository pushes; the workflow page records its current status. The local results above describe the original release verification.

## Review and publication

Open `REVIEW_GUIDE.md`, the local application, screenshots, and the short browser recording. Read `limitations.md` before using private documents or making portfolio claims. Source, synthetic fixtures, tests, reports, setup/recovery scripts, and presentation material are available in the public repository. Portfolio-site publication is a separate step.
