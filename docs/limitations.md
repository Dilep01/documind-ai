# Supported scope and limitations

- One local organization, English printed documents, INR invoices, PDF/PNG/JPEG, 20 MB and 20 pages. Rendering, image dimensions, OCR, and job runtime are bounded.
- Best with explicit colon-labelled fields and simple row tables. Wrapped rows, merged cells, handwriting, multiple invoices/file, and unknown labels need manual correction. A parser may miss a row without knowing it; always compare the original.
- Native-text quality routing and OCR orientation are heuristic. Misleading text layers, rotation, low resolution, and noise can fail. A completed processing run is not approval or an accuracy guarantee.
- Reviewers choose tax-inclusive/exclusive/unknown calculations. Unknown or missing components produce warnings rather than invented values. This is not tax-compliance software.
- Duplicate detection combines exact hashes and basic business keys. It is not universal duplicate/fraud detection or bank integration.
- The classifier uses 300 short synthetic TEXT records, not representative real invoices. Its score is not OCR/extraction accuracy. Abstention does not guarantee unfamiliar-document detection.
- Semantic search needs the configured local model and correct index version. Model tags can change; keep digests with evidence. Keyword search remains available without models.
- Q&A is experimental. Valid JSON and source indices can still produce an incorrect answer. An actual adversarial probe caused the unguarded model to repeat an injected false amount. The app now refuses model assistance for detected instruction-like context. This pattern guard can miss indirect or obfuscated instructions; it is not comprehensive prompt-injection resistance. The before/after reports are retained. The model has no application tools.
- Local field suggestions inspect at most the first three pages and 6,000 text characters per page. Printed-quote/value checks do not prove the correct semantic field was chosen; applying suggestions still requires a saved human revision.
- Default self-approval is enabled for personal use. Disable it to require another reviewer. This is single-organization access control, not multi-tenant isolation or an externally audited security product.
- Audit is append-only through the app, not tamper-proof against a database administrator. Login throttling is in-process for this single API instance. Advanced account-disable/reset lifecycle tools are outside this release.
- File and DB transactions are separate; crashes can leave unreferenced originals. There is no automatic purge that could break shared-blob references.
- Worker delivery is at-least-once with bounded retries. Recovery after a killed worker can wait for lease expiry. A deadline is not a fully hardened parser sandbox.
- Restore verification covers a separate DB, record counts, and original hashes, not every possible disaster scenario.
- Local learning/demo release only. No production reliability, business savings, universal accuracy, tax compliance, live hosted service, or customer usage is claimed.
