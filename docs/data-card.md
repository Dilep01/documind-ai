# Data and model card

## Invoice fixtures

Five fictional PDFs in `data/samples/`: two related digital labelled layouts, missing fields, raster-only scan, and mixed two-page document. `manifest.json` records hashes/ground truth. All are development fixtures in one related family. A scan and its original are variants, not independent test evidence. These regressions do not measure generalization.

ReportLab/PDFium generate them locally; no real parties, accounts, or transactions are used. PDF generation is deterministic under pinned versions; rendered image bytes may vary across platforms.

## Classification

The generated JSONL has 300 English TEXT records: invoice/receipt/other, five template families/class, 20 variations/family. Three families/class train, one validates, one tests: 180/60/60. Splits are family-disjoint; no OCR is involved.

The model is TF-IDF bigrams with Logistic Regression and a fixed seed. The report contains class metrics, confusion matrices, abstention coverage, split counts, and artifact hash. Templates are simple and lexical cues make classification easy. Do not describe its score as invoice extraction accuracy.

Model weights stay in ignored local storage. Only load the operator-generated Joblib artifact; untrusted serialized models are unsafe. Uploads cannot select model files. Retraining creates a new artifact hash.

## Local models

This implementation reuses installed `nomic-embed-text:latest` (768 dimensions) and `qwen3:1.7b` through local Ollama instead of downloading MiniLM/PyTorch. The release report records observed digests/runtime. No pretrained-model fine-tuning is claimed.

Embeddings use query/document prefixes, truncation disabled, and page-linked chunks. Q&A uses schema-constrained output and validates citation indices. Neither proves factual correctness. Software and model licenses remain separate from our source license; weights are not redistributed.
