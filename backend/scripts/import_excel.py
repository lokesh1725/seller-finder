#!/usr/bin/env python3
"""Idempotent Excel import CLI.

Usage:
    python scripts/import_excel.py                 # import default workbook
    python scripts/import_excel.py --path FILE      # custom workbook
    python scripts/import_excel.py --dry-run        # validate without writing

Safe to run repeatedly: existing companies are matched by normalised name and
never duplicated. Empty spreadsheet cells never overwrite valid stored values.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.schema import ensure_indexes  # noqa: E402
from app.services import importer  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Import the leads workbook into MongoDB")
    parser.add_argument("--path", default=str(importer.DEFAULT_WORKBOOK), help="Path to .xlsx")
    parser.add_argument("--dry-run", action="store_true", help="Parse and report without writing")
    parser.add_argument("--no-indexes", action="store_true", help="Skip index creation")
    args = parser.parse_args()

    if not args.no_indexes and not args.dry_run:
        ensure_indexes()

    summary = importer.import_workbook(args.path, dry_run=args.dry_run)
    printable = dict(summary)
    printable.pop("notes", None)
    print(json.dumps(printable, indent=2, default=str))
    print(
        f"\nImported={summary['imported']} Updated={summary['updated']} "
        f"Unchanged={summary['unchanged']} Skipped={summary['skipped']} "
        f"Duplicates={summary['duplicates']} Prospects={summary['prospects']}"
    )
    if summary.get("notes"):
        print("\nNotes (reference only):")
        for note in summary["notes"]:
            print(f"  - {note}")
    return 0 if not summary["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
