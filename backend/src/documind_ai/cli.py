"""Command-line entry point. Errors go to stderr; JSON goes to stdout or a file."""

import argparse
import importlib.metadata
import json
import os
import sys
import tempfile
from pathlib import Path

from documind_ai import __version__
from documind_ai.errors import DocumentError


def write_output(path: Path, payload: str, *, overwrite: bool) -> None:
    if path.suffix.lower() != ".json":
        raise DocumentError("invalid_output_path", "Extraction output must use a .json extension.")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, prefix=".documind-", delete=False
        ) as stream:
            temporary = stream.name
            stream.write(payload + "\n")
        if overwrite:
            os.replace(temporary, path)
        else:
            # A hard link publishes the complete file without overwriting a racing writer.
            os.link(temporary, path)
    except FileExistsError as exc:
        raise DocumentError(
            "output_exists", "Output exists. Use --overwrite to replace it."
        ) from exc
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="DocuMind AI: local, evidence-linked PDF extraction"
    )
    parser.add_argument("--version", action="version", version=f"DocuMind AI {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("doctor", help="Show Python and installed core package versions")
    samples = commands.add_parser(
        "samples", help="Generate five synthetic development PDF fixtures"
    )
    samples.add_argument("--output-dir", type=Path, default=Path("data/samples"))
    samples.add_argument("--overwrite", action="store_true")
    extract = commands.add_parser(
        "extract", help="Read native PDF text and labelled invoice headers"
    )
    extract.add_argument("input", type=Path)
    extract.add_argument(
        "--output", type=Path, help="Write JSON here; otherwise print JSON to stdout"
    )
    extract.add_argument("--overwrite", action="store_true")
    extract.add_argument(
        "--ocr", action="store_true", help="Enable local OCR for PDF/PNG/JPEG (requires Tesseract)"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "doctor":
            versions = {}
            for package in ("documind-ai", "pdfplumber", "pydantic", "reportlab"):
                try:
                    versions[package] = importlib.metadata.version(package)
                except importlib.metadata.PackageNotFoundError:
                    versions[package] = "not installed"
            print(json.dumps({"python": sys.version.split()[0], "packages": versions}, indent=2))
            return int("not installed" in versions.values())
        if args.command == "samples":
            from documind_ai.samples import generate_samples

            paths = generate_samples(args.output_dir, overwrite=args.overwrite)
            print(f"Created {len(paths) - 1} synthetic PDFs and a development manifest.")
            return 0

        from documind_ai.pipeline import extract_pdf

        if args.output:
            if args.output.resolve() == args.input.resolve():
                raise DocumentError(
                    "invalid_output_path", "The output cannot replace the input PDF."
                )
            if args.output.suffix.lower() != ".json":
                raise DocumentError(
                    "invalid_output_path", "Extraction output must use a .json extension."
                )
            if args.output.exists() and not args.overwrite:
                raise DocumentError(
                    "output_exists", "Output exists. Use --overwrite to replace it."
                )
        if args.ocr:
            from documind_ai.pipeline import extract_document

            result = extract_document(args.input)
        else:
            result = extract_pdf(args.input)
        payload = result.model_dump_json(indent=2)
        if args.output:
            write_output(args.output, payload, overwrite=args.overwrite)
            print(
                f"Saved {args.output} | {result.processing_status} | "
                f"{len(result.issues)} review issue(s). Human review is required."
            )
        else:
            print(payload)
        return 0
    except DocumentError as exc:
        print(f"{exc.code}: {exc}", file=sys.stderr)
        return 2
    except OSError:
        print(
            "file_operation_failed: Check file permissions and available disk space.",
            file=sys.stderr,
        )
        return 2
