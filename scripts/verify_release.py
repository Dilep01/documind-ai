"""Exercise the actual local HTTP/worker/model paths with fictional fixtures."""

import json
import re
import time
import uuid
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]


def run():
    config = dict(
        line.split("=", 1)
        for line in (ROOT / ".env").read_text(encoding="utf-8-sig").splitlines()
        if "=" in line and not line.startswith("#")
    )
    client = httpx.Client(base_url="http://127.0.0.1:8765/api/v1", timeout=150, trust_env=False)
    response = client.post(
        "/auth/login", json={"username": "admin", "password": config["DOCUMIND_ADMIN_PASSWORD"]}
    )
    response.raise_for_status()
    client.headers["x-documind-csrf"] = response.json()["csrf_token"]
    manifest = json.loads((ROOT / "data/samples/manifest.json").read_text())
    existing = client.get("/documents?limit=100").json()["items"]
    report = {
        "scope": "controlled synthetic development regression, not held-out real-document accuracy",
        "fixtures": [],
        "checks": {},
        "model_checks": [],
    }
    details = {}
    for sample in manifest["samples"]:
        matching = next(
            (document for document in existing if document["name"] == sample["file"]), None
        )
        if matching:
            document_id = matching["id"]
        else:
            uploaded = client.post(
                "/documents",
                files={
                    "file": (
                        sample["file"],
                        (ROOT / "data/samples" / sample["file"]).read_bytes(),
                        "application/pdf",
                    )
                },
            )
            uploaded.raise_for_status()
            document_id = uploaded.json()["document_id"]
        started = time.monotonic()
        while time.monotonic() - started < 240:
            result = client.get("/documents/" + document_id)
            result.raise_for_status()
            detail = result.json()
            if detail["status"] not in {"queued", "processing"}:
                break
            time.sleep(1)
        else:
            raise RuntimeError(
                "Fixture did not finish processing within the verification deadline."
            )
        details[sample["file"]] = detail
        fields = detail["extraction"]["invoice"] if detail["extraction"] else {}
        expected = sample["ground_truth_headers"]
        matches = {
            field: fields.get(field, {}).get("value") == value for field, value in expected.items()
        }
        report["fixtures"].append(
            {
                "name": sample["file"],
                "document_id": document_id,
                "status": detail["status"],
                "header_matches": sum(matches.values()),
                "header_count": len(matches),
                "field_matches": matches,
                "methods": [page["extraction_method"] for page in detail["extraction"]["pages"]]
                if detail["extraction"]
                else [],
                "duration_ms": detail.get("duration_ms"),
                "index_status": detail["index_status"],
                "issues": [issue["code"] for issue in detail["issues"]],
            }
        )
        print(
            f"fixture={sample['file']} status={detail['status']} headers={sum(matches.values())}/{len(matches)}",
            flush=True,
        )
    # Produce reviewable approved examples through the same API used by the browser.
    approved = []
    for name in ("digital_basic.pdf", "digital_alternate.pdf"):
        detail = details[name]
        document_id = detail["id"]
        if detail["review_status"] != "approved":
            data = detail["data"]
            data["totals_mode"] = "tax_exclusive"
            saved = client.patch(
                "/invoices/" + document_id,
                json={
                    "expected_version": detail["version"],
                    "reason": "Verified synthetic printed values and selected tax-exclusive totals.",
                    "data": data,
                },
            )
            saved.raise_for_status()
            decision = client.post(
                "/invoices/" + document_id + "/approvals",
                json={
                    "expected_version": saved.json()["version"],
                    "decision": "approved",
                    "reason": "Compared every value and line item with the fictional original.",
                    "acknowledge_warnings": True,
                },
            )
            decision.raise_for_status()
        approved.append(document_id)
    for format in ("csv", "json"):
        exported = client.post(
            "/exports",
            json={"document_ids": approved, "format": format, "idempotency_key": str(uuid.uuid4())},
        )
        exported.raise_for_status()
        download = client.get("/exports/" + exported.json()["id"] + "/download")
        download.raise_for_status()
        (ROOT / "docs/demo" / f"approved-batch.{format}").write_bytes(download.content)
        report["checks"][f"approved_{format}_export"] = "passed"
    exact = client.get("/documents", params={"invoice_number": "BSS-000007"})
    exact.raise_for_status()
    report["checks"]["exact_invoice_filter"] = len(exact.json()["items"]) == 1
    # Two explicitly labelled retrieval regressions; not an estimate over arbitrary queries.
    retrieval = []
    for query, name in (
        ("Birch Software Services", "digital_alternate.pdf"),
        ("Cedar Office Supplies", "digital_basic.pdf"),
    ):
        result = client.get("/search", params={"q": query, "mode": "semantic"})
        retrieval.append(
            {
                "query": query,
                "status": result.status_code,
                "expected_document_in_top5": result.is_success
                and details[name]["id"]
                in [source["document_id"] for source in result.json().get("items", [])],
                "supporting_vendor_quote_in_top5": result.is_success
                and any(
                    query.casefold() in source["text"].casefold()
                    for source in result.json().get("items", [])
                ),
                "note": "Duplicate uploads can contain the same evidence; quote relevance is reported separately from a particular upload ID.",
            }
        )
    report["retrieval_regressions"] = retrieval
    document_id = details["digital_basic.pdf"]["id"]
    for question, expectation in (
        ("What is the invoice total?", "2950"),
        ("What bank account number is printed on this invoice?", "abstain"),
    ):
        started = time.monotonic()
        result = client.post("/questions", json={"question": question, "document_id": document_id})
        answer = result.json() if result.is_success else {"error": "model unavailable"}
        correct = (
            answer.get("abstained") is True
            if expectation == "abstain"
            else expectation in re.sub(r"[,\s]", "", answer.get("answer", ""))
        )
        report["model_checks"].append(
            {
                "question": question,
                "status": result.status_code,
                "expectation": expectation,
                "regression_passed": correct,
                "answer": answer,
                "duration_seconds": round(time.monotonic() - started, 2),
            }
        )
        print(f"model_check={expectation} status={result.status_code} passed={correct}", flush=True)
    suggestion = client.post(f"/documents/{document_id}/suggestions")
    report["checks"]["local_suggestions"] = {
        "status": suggestion.status_code,
        "count": len(suggestion.json().get("suggestions", [])) if suggestion.is_success else 0,
    }
    report["dashboard"] = client.get("/dashboard").json()
    report["model_status"] = client.get("/models/status").json()
    (ROOT / "evaluation/reports/local-release.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    client.close()
    return report


if __name__ == "__main__":
    run()
