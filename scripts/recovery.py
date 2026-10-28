"""Back up a quiesced local workspace; verify restoration in a separate disposable DB."""

import argparse
import hashlib
import json
import secrets
import subprocess
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COUNTS = "SELECT json_build_object('documents',(SELECT count(*) FROM documents),'revisions',(SELECT count(*) FROM invoice_revisions),'approvals',(SELECT count(*) FROM approvals),'exports',(SELECT count(*) FROM export_batches))"


def command(*args, check=True):
    return subprocess.run(list(args), cwd=ROOT, capture_output=True, check=check)


def backup(target: Path):
    if target.exists():
        raise SystemExit("Choose a new backup directory; existing backups are never replaced.")
    target.mkdir(parents=True)
    try:
        command("docker", "compose", "stop", "app", "worker")
        dump = command(
            "docker",
            "compose",
            "exec",
            "-T",
            "db",
            "pg_dump",
            "-U",
            "documind",
            "-d",
            "documind",
            "-Fc",
        )
        (target / "database.dump").write_bytes(dump.stdout)
        command("docker", "compose", "cp", "app:/app/storage", str(target / "storage"))
        counts = json.loads(
            command(
                "docker",
                "compose",
                "exec",
                "-T",
                "db",
                "psql",
                "-U",
                "documind",
                "-d",
                "documind",
                "-tAc",
                COUNTS,
            ).stdout
        )
        blobs = (
            command(
                "docker",
                "compose",
                "exec",
                "-T",
                "db",
                "psql",
                "-U",
                "documind",
                "-d",
                "documind",
                "-tAc",
                "SELECT sha256 || '|' || storage_key FROM blobs ORDER BY sha256",
            )
            .stdout.decode()
            .splitlines()
        )
        for row in blobs:
            digest, name = row.split("|", 1)
            file = target / "storage" / "originals" / name
            if hashlib.sha256(file.read_bytes()).hexdigest() != digest:
                raise RuntimeError("Original-file hash verification failed.")
        (target / "private.env").write_bytes((ROOT / ".env").read_bytes())
        manifest = {
            "created_at": datetime.now(UTC).isoformat(),
            "counts": counts,
            "originals": len(blobs),
            "database_sha256": hashlib.sha256(dump.stdout).hexdigest(),
            "notice": "Private local backup. Contains document data and credentials. Do not publish.",
        }
        (target / "manifest.json").write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
        )
        print(
            json.dumps({"backup": str(target), "counts": counts, "originals_verified": len(blobs)})
        )
    finally:
        command("docker", "compose", "start", "app", "worker", check=False)


def verify(target: Path):
    manifest = json.loads((target / "manifest.json").read_text(encoding="utf-8"))
    if (
        hashlib.sha256((target / "database.dump").read_bytes()).hexdigest()
        != manifest["database_sha256"]
    ):
        raise RuntimeError("Backup checksum mismatch.")
    container = "documind-restore-check-" + uuid.uuid4().hex[:12]
    try:
        command(
            "docker",
            "run",
            "-d",
            "--name",
            container,
            "--network",
            "none",
            "-e",
            "POSTGRES_DB=documind",
            "-e",
            "POSTGRES_USER=documind",
            "-e",
            "POSTGRES_PASSWORD=" + secrets.token_hex(20),
            "pgvector/pgvector:pg17",
        )
        for _ in range(60):
            if (
                command(
                    "docker",
                    "exec",
                    container,
                    "pg_isready",
                    "-U",
                    "documind",
                    "-d",
                    "documind",
                    check=False,
                ).returncode
                == 0
            ):
                break
            time.sleep(1)
        else:
            raise RuntimeError("Restore verification database did not start.")
        command("docker", "cp", str(target / "database.dump"), container + ":/tmp/documind.dump")
        command(
            "docker",
            "exec",
            container,
            "pg_restore",
            "--exit-on-error",
            "--no-owner",
            "-U",
            "documind",
            "-d",
            "documind",
            "/tmp/documind.dump",
        )
        counts = json.loads(
            command(
                "docker",
                "exec",
                container,
                "psql",
                "-U",
                "documind",
                "-d",
                "documind",
                "-tAc",
                COUNTS,
            ).stdout
        )
        if counts != manifest["counts"]:
            raise RuntimeError("Restored record counts differ from the snapshot.")
        blobs = (
            command(
                "docker",
                "exec",
                container,
                "psql",
                "-U",
                "documind",
                "-d",
                "documind",
                "-tAc",
                "SELECT sha256 || '|' || storage_key FROM blobs",
            )
            .stdout.decode()
            .splitlines()
        )
        for row in blobs:
            digest, name = row.split("|", 1)
            if (
                hashlib.sha256((target / "storage" / "originals" / name).read_bytes()).hexdigest()
                != digest
            ):
                raise RuntimeError("Restored original file does not match its database record.")
        report = {
            "status": "passed",
            "counts": counts,
            "originals_verified": len(blobs),
            "scope": "separate PostgreSQL restoration, record counts, and original-file checksums",
        }
        (target / "restore-verification.json").write_text(
            json.dumps(report, indent=2) + "\n", encoding="utf-8"
        )
        print(json.dumps(report))
    finally:
        command("docker", "rm", "-f", "-v", container, check=False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=["backup", "verify"])
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    (backup if args.operation == "backup" else verify)(args.directory.resolve())
