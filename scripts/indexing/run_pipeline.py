#!/usr/bin/env python3
"""
Full indexing pipeline runner.

Runs all four steps in sequence:
  1. tag_rules.py       — regenerate citation_map.json from rule YAMLs
  2. fetch_hmrc_sources — download HMRC manual sections
  3. chunk_and_embed    — split into chunks and generate embeddings
  4. upload_to_search   — push chunks to Azure AI Search

Usage:
    python run_pipeline.py [--manual PTM] [--dry-run] [--skip-fetch]
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).parent


def run(script: str, extra_args: list[str]) -> None:
    cmd = [sys.executable, str(SCRIPTS / script)] + extra_args
    print(f"\n{'─' * 60}")
    print(f"Running: {' '.join(cmd)}")
    print(f"{'─' * 60}")
    result = subprocess.run(cmd)
    if result.returncode != 0:
        print(f"\nERROR: {script} failed (exit {result.returncode})")
        sys.exit(result.returncode)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manual", help="Scope to one manual (e.g. PTM)")
    parser.add_argument("--ref", help="Scope to one section ref (e.g. PTM063300)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Skip embeddings and upload")
    parser.add_argument("--skip-fetch", action="store_true",
                        help="Skip fetch step (use existing raw data)")
    args = parser.parse_args()

    manual_args = (["--manual", args.manual] if args.manual else [])
    ref_args = (["--ref", args.ref] if args.ref else [])
    dry_args = (["--dry-run"] if args.dry_run else [])

    # Step 1: regenerate citation map from rule YAMLs
    run("tag_rules.py", [])

    # Step 2: fetch source material
    if not args.skip_fetch:
        run("fetch_hmrc_sources.py", manual_args + dry_args)

    # Step 3: chunk and embed
    run("chunk_and_embed.py", manual_args + dry_args)

    # Step 4: upload (skipped in dry-run)
    if not args.dry_run:
        run("upload_to_search.py", manual_args + ref_args)

    print("\n✓ Pipeline complete.")


if __name__ == "__main__":
    main()
