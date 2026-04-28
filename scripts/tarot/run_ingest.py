from __future__ import annotations

import argparse
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from rag_pipeline import RAGPipeline


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Tarot ingestion launcher (thin wrapper).")
    parser.add_argument(
        "--force-reindex",
        action="store_true",
        help="Recreate collection and reindex corpus from scratch.",
    )
    parser.add_argument(
        "--collection-name",
        default=None,
        help="Optional Chroma collection override.",
    )
    parser.add_argument(
        "--persist-directory",
        default=None,
        help="Optional Chroma persist directory override.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    pipeline = RAGPipeline(
        collection_name=args.collection_name,
        persist_directory=args.persist_directory,
    )
    stats = pipeline.ingest_if_needed(force_reindex=args.force_reindex)

    print("Tarot ingestion completed.")
    print(f"- collection: {stats.get('name', '')}")
    print(f"- chunks in collection: {stats.get('count', 0)}")
    print(f"- persist directory: {stats.get('persist_directory', '')}")


if __name__ == "__main__":
    main()
