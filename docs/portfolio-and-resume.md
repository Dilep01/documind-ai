# Portfolio and resume presentation

## Portfolio description

DocuMind AI is a local invoice-processing and review application built with Python, FastAPI, PostgreSQL, React, and Tesseract. It extracts digital/scanned documents, connects fields to their source pages, records corrections as revisions, and exports approved snapshots. It also includes role-based access, recoverable processing jobs, keyword/vector search, and optional local-model assistance without paid API keys.

Validation uses fictional invoice fixtures and synthetic text classification data. The controlled scan benchmark exposes OCR errors; local AI remains experimental. There is no production deployment or real customer usage claim.

When publishing the project card, link [the source repository](https://github.com/Dilep01/documind-ai), the demo recording/screenshots, architecture, setup instructions, and release verification. Avoid an unsupported “99% accurate” or time-savings headline.

## Resume bullets for the completed local project

- Built a local invoice-review application using Python, FastAPI, PostgreSQL, React, and Tesseract, with source-linked extraction, versioned corrections, approval checks, and CSV/JSON exports.
- Implemented session authentication, uploader/reviewer/admin permissions, CSRF protection, bounded processing retries, and local pgvector search; verified revision and export behavior through backend and browser tests using synthetic documents.
- Added an evaluated TF-IDF classifier and optional local-model assistance; documented synthetic-data limits, observed OCR errors, and an adversarial-model failure with a guarded abstention path.

Use a heading such as **Local portfolio project · Synthetic validation**. Do not describe this as employment, production operations, tax compliance, fraud prevention, or measured business savings.

## Interview topics

Be ready to explain native extraction versus OCR, source coordinates, Decimal amounts, database transactions, worker leases, at-least-once execution, revision-specific approval, export idempotency, template leakage, retrieval versus SQL totals, the observed prompt-injection failure, and why the mitigation does not prove general resistance.
