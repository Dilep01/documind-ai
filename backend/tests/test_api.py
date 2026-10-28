import concurrent.futures

from documind_ai.processing import process
from sqlalchemy import select


def upload_and_process(client, samples, name="digital_basic.pdf"):
    response = client.post(
        "/api/v1/documents",
        files={"file": (name, (samples / name).read_bytes(), "application/pdf")},
    )
    assert response.status_code == 202, response.text
    result = response.json()
    process(result["job_id"])
    detail = client.get("/api/v1/documents/" + result["document_id"])
    assert detail.status_code == 200
    return result["document_id"], result["job_id"], detail.json()


def approve(client, document_id, detail):
    response = client.post(
        f"/api/v1/invoices/{document_id}/approvals",
        json={
            "expected_version": detail["version"],
            "decision": "approved",
            "reason": "Checked the printed source carefully",
            "acknowledge_warnings": True,
        },
    )
    assert response.status_code == 200, response.text


def test_full_revision_approval_export_workflow(client, samples):
    document_id, job_id, detail = upload_and_process(client, samples)
    assert detail["status"] == "succeeded", detail
    assert detail["data"]["invoice_number"] == "INV-000042"
    assert len(detail["data"]["line_items"]) == 2
    assert client.get(f"/api/v1/documents/{document_id}/pages/1").status_code == 200
    blocked = client.post(
        "/api/v1/exports",
        json={
            "document_ids": [document_id],
            "format": "csv",
            "idempotency_key": "unapproved-export",
        },
    )
    assert blocked.status_code == 409
    approve(client, document_id, detail)
    result = client.post(
        "/api/v1/exports",
        json={
            "document_ids": [document_id],
            "format": "csv",
            "idempotency_key": "first-approved-export",
        },
    )
    assert result.status_code == 200, result.text
    export_id = result.json()["id"]
    changed_request = client.post(
        "/api/v1/exports",
        json={
            "document_ids": [document_id],
            "format": "json",
            "idempotency_key": "first-approved-export",
        },
    )
    assert changed_request.status_code == 409
    exported = client.get(f"/api/v1/exports/{export_id}/download").text
    assert "INV-000042" in exported
    assert (
        client.post(
            "/api/v1/exports",
            json={
                "document_ids": [document_id],
                "format": "csv",
                "idempotency_key": "first-approved-export",
            },
        ).json()["id"]
        == export_id
    )
    data = detail["data"]
    data["vendor_name"] = "Corrected Fictional Vendor"
    edit = client.patch(
        f"/api/v1/invoices/{document_id}",
        json={"expected_version": 1, "reason": "Corrected vendor spelling", "data": data},
    )
    assert edit.status_code == 200, edit.text
    assert (
        client.post(
            "/api/v1/exports",
            json={
                "document_ids": [document_id],
                "format": "json",
                "idempotency_key": "edited-export-blocked",
            },
        ).status_code
        == 409
    )
    # The previous immutable export and initial revision remain unchanged.
    assert client.get(f"/api/v1/exports/{export_id}/download").text == exported
    updated = client.get(f"/api/v1/documents/{document_id}").json()
    assert updated["version"] == 2 and len(updated["revisions"]) == 2
    assert (
        client.patch(
            f"/api/v1/invoices/{document_id}",
            json={"expected_version": 1, "reason": "Stale browser form", "data": data},
        ).status_code
        == 409
    )


def test_duplicate_and_idempotent_processing(client, samples, database):
    document_id, job_id, detail = upload_and_process(client, samples)
    process(job_id)
    with database.session_factory()() as db:
        assert len(list(db.scalars(select(database.ExtractionRun)))) == 1
        assert len(list(db.scalars(select(database.Revision)))) == 1
    another, _, duplicate = upload_and_process(client, samples)
    assert another != document_id
    assert duplicate["duplicate_of"] == document_id
    assert any(issue["code"] == "possible_duplicate" for issue in duplicate["issues"])


def test_auth_csrf_and_origin(client):
    token = client.headers.pop("x-documind-csrf")
    assert (
        client.post("/api/v1/documents", files={"file": ("test.pdf", b"%PDF-x")}).status_code == 403
    )
    client.headers["x-documind-csrf"] = token
    assert (
        client.post(
            "/api/v1/auth/logout", headers={"Origin": "https://untrusted.invalid"}
        ).status_code
        == 403
    )
    assert client.post("/api/v1/auth/logout").status_code == 200
    assert client.get("/api/v1/documents").status_code == 401


def test_bad_uploads_and_missing_fields_cannot_approve(client, samples):
    assert (
        client.post("/api/v1/documents", files={"file": ("fake.pdf", b"not a pdf")}).status_code
        == 415
    )
    assert (
        client.post("/api/v1/documents", files={"file": ("bad.exe", b"not a pdf")}).status_code
        == 415
    )
    document_id, _, detail = upload_and_process(client, samples, "missing_fields.pdf")
    decision = client.post(
        f"/api/v1/invoices/{document_id}/approvals",
        json={
            "expected_version": 1,
            "decision": "approved",
            "reason": "Should be rejected for missing fields",
            "acknowledge_warnings": True,
        },
    )
    assert decision.status_code == 422


def test_role_and_document_access(client, samples):
    document_id, _, _ = upload_and_process(client, samples)
    response = client.post(
        "/api/v1/users",
        json={"username": "uploader", "password": "uploader-test-password", "role": "uploader"},
    )
    assert response.status_code == 201
    login = client.post(
        "/api/v1/auth/login", json={"username": "uploader", "password": "uploader-test-password"}
    )
    client.headers["x-documind-csrf"] = login.json()["csrf_token"]
    assert client.get("/api/v1/documents").json()["items"] == []
    assert client.get(f"/api/v1/documents/{document_id}").status_code == 404
    assert client.get(f"/api/v1/documents/{document_id}/original").status_code == 404
    assert client.get(f"/api/v1/documents/{document_id}/pages/1").status_code == 404
    assert client.get("/api/v1/search?q=Cedar").json()["items"] == []
    assert client.get("/api/v1/exports").status_code == 403
    assert (
        client.post(
            "/api/v1/users",
            json={"username": "evil", "password": "evil-test-password", "role": "admin"},
        ).status_code
        == 403
    )


def test_reprocess_keeps_review_revision(client, samples):
    document_id, _, detail = upload_and_process(client, samples)
    data = detail["data"]
    data["vendor_name"] = "Human corrected vendor"
    assert (
        client.patch(
            f"/api/v1/invoices/{document_id}",
            json={"expected_version": 1, "reason": "Manual correction", "data": data},
        ).status_code
        == 200
    )
    new_job = client.post(f"/api/v1/documents/{document_id}/reprocess")
    assert new_job.status_code == 202
    assert client.post(f"/api/v1/documents/{document_id}/reprocess").status_code == 409
    process(new_job.json()["job_id"])
    updated = client.get(f"/api/v1/documents/{document_id}").json()
    assert updated["data"]["vendor_name"] == "Human corrected vendor"
    assert updated["version"] == 2


def test_concurrent_edit_is_not_silently_overwritten(client, samples):
    document_id, _, detail = upload_and_process(client, samples)
    body = {"expected_version": 1, "reason": "Concurrent review", "data": detail["data"]}
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(
                lambda _: client.patch(f"/api/v1/invoices/{document_id}", json=body).status_code,
                range(2),
            )
        )
    assert sorted(results) == [200, 409]


def test_self_approval_policy(client, samples, monkeypatch):
    document_id, _, detail = upload_and_process(client, samples)
    monkeypatch.setenv("DOCUMIND_ALLOW_SELF_APPROVAL", "false")
    decision = client.post(
        f"/api/v1/invoices/{document_id}/approvals",
        json={
            "expected_version": 1,
            "decision": "approved",
            "reason": "Self approval should be blocked",
            "acknowledge_warnings": True,
        },
    )
    assert decision.status_code == 403
