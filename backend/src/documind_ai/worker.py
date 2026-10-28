"""One-process queue consumer with leased claims and bounded processing subprocesses."""

import logging
import subprocess
import sys
import time
from datetime import timedelta

from sqlalchemy import or_, select

from documind_ai.database import Document, Job, now, session_factory

log = logging.getLogger("documind.worker")


def claim_job() -> str | None:
    with session_factory()() as db:
        job = db.scalar(
            select(Job)
            .where(
                or_(Job.state == "queued", (Job.state == "processing") & (Job.lease_until < now()))
            )
            .order_by(Job.created_at)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if job is None:
            return None
        if job.attempts >= 3:
            job.state, job.stage, job.error = (
                "failed",
                "failed",
                "Retry limit reached after interrupted processing.",
            )
            db.get(Document, job.document_id).status = "failed"
            db.commit()
            return None
        job.state, job.stage = "processing", "extracting"
        job.attempts += 1
        job.started_at = job.started_at or now()
        job.heartbeat_at, job.lease_until = now(), now() + timedelta(seconds=300)
        db.get(Document, job.document_id).status = "processing"
        db.commit()
        return job.id


def execute_job(job_id: str, timeout: int = 240):
    process = subprocess.Popen(
        [sys.executable, "-m", "documind_ai.manage", "process", job_id],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    start = time.monotonic()
    while process.poll() is None:
        if time.monotonic() - start > timeout:
            process.kill()
            process.wait()
            break
        with session_factory()() as db:
            job = db.get(Job, job_id)
            if job and job.state == "processing":
                job.heartbeat_at, job.lease_until = now(), now() + timedelta(seconds=300)
                db.commit()
        time.sleep(2)
    with session_factory()() as db:
        job = db.get(Job, job_id)
        if job and job.state == "processing":
            # Retry transient failures at most three times; prior completed runs are idempotent.
            job.state = "queued" if job.attempts < 3 else "failed"
            job.stage = job.state
            job.error = "Processing interrupted or exceeded its time limit. Retry is bounded."
            job.lease_until = None
            db.get(Document, job.document_id).status = job.state
            db.commit()
    log.info("job_finished id=%s", job_id)


def run():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    while True:
        try:
            job_id = claim_job()
            if job_id:
                execute_job(job_id)
            else:
                time.sleep(2)
        except KeyboardInterrupt:
            return
        except Exception:
            log.error("worker_retry reason=database_or_job_failure")
            time.sleep(3)


if __name__ == "__main__":
    run()
