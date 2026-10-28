# Review DocuMind locally

Open http://localhost:8765. Sign in as `admin` using `DOCUMIND_ADMIN_PASSWORD` from the private `.env` file. The app is already running after the build. If stopped, start Docker Desktop and run `./scripts/start.ps1`.

## Try the full workflow

1. Open **Documents**. The workspace contains fictional examples from the acceptance tests. Two sample invoices have been checked and approved; the others demonstrate review and duplicate warnings.
2. Open `digital_basic.pdf`. Use **Source** beside a field to highlight its printed evidence. Review line items and the chosen totals calculation.
3. Change a field, enter a review note, and **Save revision**. Approval resets. Enter a new note and approve only after checking the original. Warnings require acknowledgement; errors must be resolved.
4. Export an approved revision to CSV. The historical export remains unchanged if the invoice is edited afterward.
5. Open `missing_fields.pdf`. Missing values stay empty and block approval rather than being guessed.
6. Open `scan_needs_ocr.pdf` or the mixed example. Compare OCR with the image. The controlled scan benchmark still has real recognition errors and may need row/header correction.
7. Use **Search & ask**. Keyword search works without models. Semantic search and local questions use installed Ollama models. Try “What is the invoice total?” and an unanswerable bank-account question. Verify cited pages.
8. **Suggest details** proposes only values supported by printed quotes. Applying a suggestion edits the form; it does not save or approve anything.
9. Check **Activity**, **Exports**, and **Team access**. Uploaders see their own documents; reviewers/admins review the workspace. Self-approval is enabled for this personal demo; the configuration can require a separate reviewer.

See `docs/demo/overview.png`, `review.png`, `mobile.png`, and the short actual browser recording `walkthrough.webm`. The recording is an automated acceptance journey, not a production customer demonstration.

Read `RELEASE_VERIFICATION.md` for measured results and `limitations.md` for scope. Source, tests, setup scripts, and evidence are published at [Dilep01/documind-ai](https://github.com/Dilep01/documind-ai). The application runs locally; no hosted production deployment is claimed.
