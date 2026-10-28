"""Reproducible, template-grouped synthetic TEXT classification experiment."""

import hashlib
import json
import random
from pathlib import Path

import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.pipeline import make_pipeline

TEMPLATES = {
    "invoice": [
        "INVOICE {id}\nVendor: {vendor}\nBill To: Demo Studio\nSubtotal: {amount}\nTax: 450\nTotal: {amount}\nPayment due in 14 days.",
        "Supplier {vendor}\nInvoice Number: {id}\nDescription Qty Unit price Amount\nServices 2 500 1000\nAmount Due: INR {amount}",
        "Invoice issued by {vendor}\nReference {id}\nCustomer account Demo\nInvoice date 2026-10-28\nBalance payable INR {amount}",
        "TAX INVOICE\n{vendor}\nDocument {id}\nNet Amount INR {amount}\nTerms: net thirty\nPlease remit payment by the due date.",
        "Commercial invoice {id}\nSeller {vendor}\nBuyer Demo Learning Studio\nGoods and services supplied\nGrand Total INR {amount}\nUnpaid amount {amount}",
    ],
    "receipt": [
        "RECEIPT {id}\n{vendor}\nPayment received INR {amount}\nPaid in full. Thank you for your purchase.",
        "Cash receipt\nTransaction {id}\nStore {vendor}\nAmount paid {amount}\nChange returned 0.00\nPayment method cash.",
        "Order receipt {id}\nMerchant {vendor}\nSuccessful payment INR {amount}\nCard ending DEMO\nKeep this receipt for your records.",
        "PAYMENT CONFIRMATION\nReceipt reference {id}\nReceived from customer INR {amount}\n{vendor}\nStatus PAID\nNo outstanding balance.",
        "Sales receipt\n{vendor}\nPurchase {id}\nTendered {amount}\nTransaction completed\nThank you for shopping with us.",
    ],
    "other": [
        "MEETING NOTES {id}\nTeam {vendor}\nDiscussed plans for next quarter. Action items: update documentation and schedule a review.",
        "Project report {id}\nPrepared by {vendor}\nResearch findings and technical observations. The team will review the proposed architecture.",
        "Employee handbook section {id}\nOrganization {vendor}\nWorkplace guidelines, leave policy, and onboarding instructions. Please contact your team lead.",
        "DELIVERY CHECKLIST {id}\n{vendor}\nInspect packaging and verify the recipient address. Record damaged items and obtain a signature.",
        "Technical specification {id}\nAuthor {vendor}\nSystem components, deployment requirements, interfaces, and test procedures. Version draft.",
    ],
}


def train(directory: Path = Path("models"), report_dir: Path = Path("evaluation/reports")):
    rng = random.Random(42)
    records = []
    for label, templates in TEMPLATES.items():
        for family, template in enumerate(templates):
            split = "train" if family < 3 else "validation" if family == 3 else "test"
            for index in range(20):
                records.append(
                    {
                        "id": f"{label}-{family}-{index}",
                        "label": label,
                        "family": f"{label}-template-{family}",
                        "split": split,
                        "text": template.format(
                            id=f"D-{rng.randrange(10000, 99999)}",
                            vendor=f"Fictional Organization {rng.randrange(1, 99)}",
                            amount=f"{rng.randrange(100, 9000)}.00",
                        ),
                    }
                )
    train_rows = [row for row in records if row["split"] == "train"]
    model = make_pipeline(
        TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True),
        LogisticRegression(max_iter=500, class_weight="balanced", random_state=42, C=4),
    )
    model.fit([row["text"] for row in train_rows], [row["label"] for row in train_rows])
    report = {
        "seed": 42,
        "scope": "synthetic English TEXT classification only; no OCR or real-document accuracy claim",
        "split_policy": "disjoint template families; all variants stay in one split",
        "abstention_threshold": 0.55,
        "threshold_note": "Fixed conservative starting threshold; not calibrated for real documents.",
        "counts": {
            split: sum(row["split"] == split for row in records)
            for split in ("train", "validation", "test")
        },
    }
    for split in ("validation", "test"):
        rows = [row for row in records if row["split"] == split]
        texts, labels = [row["text"] for row in rows], [row["label"] for row in rows]
        predictions = model.predict(texts)
        probabilities = model.predict_proba(texts)
        accepted = [max(scores) >= 0.55 for scores in probabilities]
        report[split] = {
            "classification": classification_report(
                labels, predictions, output_dict=True, zero_division=0
            ),
            "confusion_matrix": confusion_matrix(
                labels, predictions, labels=model.classes_
            ).tolist(),
            "labels": model.classes_.tolist(),
            "accepted": int(sum(accepted)),
            "total": len(rows),
        }
    directory.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, directory / "classifier.joblib")
    report["artifact_sha256"] = hashlib.sha256(
        (directory / "classifier.joblib").read_bytes()
    ).hexdigest()
    (report_dir / "classification.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    data_dir = report_dir.parent / "datasets"
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "classification.jsonl").write_text(
        "\n".join(json.dumps(row) for row in records) + "\n", encoding="utf-8"
    )
    return report
