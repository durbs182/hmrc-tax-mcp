"""
Upload chunked HMRC documents (with embeddings) to Azure AI Search.

Reads from data/chunked/{manual}/{chunk_id}.json and batch-uploads
to the hmrc-guidance index.

Usage:
    python upload_to_search.py [--manual PTM] [--ref PTM063300]
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient

CHUNKED_DIR = Path("data/chunked")
BATCH_SIZE = 100


def get_search_client() -> SearchClient:
    return SearchClient(
        endpoint=os.environ["AZURE_SEARCH_ENDPOINT"],
        index_name=os.environ.get("AZURE_SEARCH_INDEX", "hmrc-guidance"),
        credential=AzureKeyCredential(os.environ["AZURE_SEARCH_KEY"]),
    )


def upload_chunks(chunks: list[dict], client: SearchClient) -> None:
    """Upload chunks in batches, raising on any failure."""
    for i in range(0, len(chunks), BATCH_SIZE):
        batch = chunks[i : i + BATCH_SIZE]
        results = client.upload_documents(documents=batch)
        failed = [r for r in results if not r.succeeded]
        if failed:
            ids = [r.key for r in failed]
            raise RuntimeError(f"Upload failed for {len(failed)} chunks: {ids}")
    print(f"  Uploaded {len(chunks)} chunks.")


def upload_manual(manual_name: str, ref_filter: str | None, client: SearchClient) -> int:
    """Upload all chunks for a manual, optionally filtered to one ref."""
    chunked_dir = CHUNKED_DIR / manual_name
    if not chunked_dir.exists():
        print(f"  No chunked data for {manual_name} — run chunk_and_embed.py first.")
        return 0

    paths = list(chunked_dir.glob("*.json"))
    if ref_filter:
        paths = [p for p in paths if p.name.startswith(ref_filter.upper())]

    chunks = [json.loads(p.read_text()) for p in paths]
    if not chunks:
        print(f"  No chunks to upload for {manual_name} {ref_filter or ''}.")
        return 0

    print(f"Uploading {len(chunks)} chunks for {manual_name} …")
    upload_chunks(chunks, client)
    return len(chunks)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manual", help="Upload one manual only (e.g. PTM)")
    parser.add_argument("--ref", help="Upload one section only (e.g. PTM063300)")
    args = parser.parse_args()

    client = get_search_client()

    if args.ref:
        # Infer manual from ref prefix
        manual = "".join(c for c in args.ref if c.isalpha()).upper()
        upload_manual(manual, args.ref, client)
    elif args.manual:
        upload_manual(args.manual, None, client)
    else:
        manuals = [d.name for d in CHUNKED_DIR.iterdir() if d.is_dir()]
        total = 0
        for manual in manuals:
            total += upload_manual(manual, None, client)
        print(f"\nDone. Total uploaded: {total} chunks.")


if __name__ == "__main__":
    main()
