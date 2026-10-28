from datetime import timedelta

from documind_ai.database import now
from documind_ai.worker import claim_job


def test_expired_lease_is_reclaimed_and_attempts_are_bounded(client, samples, database):
    uploaded = client.post(
        "/api/v1/documents",
        files={"file": ("lease.pdf", (samples / "digital_basic.pdf").read_bytes())},
    ).json()
    with database.session_factory()() as db:
        job = db.get(database.Job, uploaded["job_id"])
        job.state = "processing"
        job.attempts = 1
        job.lease_until = now() - timedelta(seconds=1)
        db.commit()
    assert claim_job() == uploaded["job_id"]
    with database.session_factory()() as db:
        job = db.get(database.Job, uploaded["job_id"])
        assert job.attempts == 2
        job.lease_until = now() - timedelta(seconds=1)
        job.attempts = 3
        db.commit()
    assert claim_job() is None
    with database.session_factory()() as db:
        assert db.get(database.Job, uploaded["job_id"]).state == "failed"


def test_rotated_image_ocr(samples, tmp_path):
    import shutil

    import pdfplumber
    import pytest
    from documind_ai.pipeline import extract_document

    if not shutil.which("tesseract"):
        pytest.skip("Real OCR is verified in Docker")
    with pdfplumber.open(samples / "digital_basic.pdf") as pdf:
        image = pdf.pages[0].to_image(resolution=144).original.rotate(90, expand=True)
        path = tmp_path / "rotated.png"
        image.save(path)
        image.close()
    result = extract_document(path)
    assert result.processing_status == "succeeded"
    assert result.invoice.total.value is not None
    assert result.invoice.invoice_number.value == "INV-000042"
