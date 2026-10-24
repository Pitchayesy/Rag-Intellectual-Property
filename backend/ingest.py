#!/usr/bin/env python3
"""Build the SQLite vector database from legal Markdown files in data/.

Reads every .md file in DATA_DIR, splits it into chunks, embeds each chunk
with a Google AI Studio embedding model, and stores everything in a single
SQLite database using sqlite-vec for vector search.

Usage:
    python ingest.py
"""

import os
import re
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from langchain_core.documents import Document
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_community.vectorstores import SQLiteVec

BASE_DIR = Path(__file__).resolve().parent.parent  # project root
DATA_DIR = BASE_DIR / "data"
DB_PATH = BASE_DIR / "legal_rag.db"

EMBED_MODEL = "models/gemini-embedding-001"
EMBED_DIM = 768  # Matryoshka-truncated dimension of gemini-embedding-001
TABLE = "law_chunks"

load_dotenv(BASE_DIR / ".env")

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass


def clean_text(text: str) -> str:
    """Strip page-heading noise produced by pdf2md.py."""
    text = re.sub(r"^## Page \d+\s*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"> Extracted from text layer of .*?\n", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def load_documents() -> list[Document]:
    return [
        Document(page_content=clean_text(p.read_text(encoding="utf-8")),
                 metadata={"source": p.name})
        for p in sorted(DATA_DIR.glob("*.md"))
    ]


def split_into_chunks(docs: list[Document]) -> list[Document]:
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1200,
        chunk_overlap=200,
        separators=["\n\n", "\n", " ", ""],
    )
    return splitter.split_documents(docs)


def _add_with_retry(db: SQLiteVec, batch: list[Document], attempts: int = 6) -> None:
    """Add one batch, backing off on 429 RESOURCE_EXHAUSTED."""
    for attempt in range(1, attempts + 1):
        try:
            db.add_documents(batch)
            return
        except Exception as exc:
            if "RESOURCE_EXHAUSTED" not in str(exc) and "429" not in str(exc):
                raise
            if attempt == attempts:
                raise
            wait = 10 * attempt
            print(f"  rate limited, retry {attempt}/{attempts - 1} in {wait}s...")
            time.sleep(wait)


def main():
    if not os.environ.get("GOOGLE_API_KEY"):
        sys.exit("Error: set GOOGLE_API_KEY in .env")
    if not DATA_DIR.exists():
        sys.exit(f"Error: data directory not found: {DATA_DIR}")

    docs = load_documents()
    if not docs:
        sys.exit(f"Error: no .md files found in {DATA_DIR}")

    chunks = split_into_chunks(docs)
    print(f"Loaded {len(docs)} document(s) -> {len(chunks)} chunks")

    embeddings = GoogleGenerativeAIEmbeddings(
        model=EMBED_MODEL,
        output_dimensionality=EMBED_DIM,
        task_type="RETRIEVAL_DOCUMENT",
    )
    db = SQLiteVec(
        table=TABLE,
        connection=None,
        db_file=str(DB_PATH),
        embedding=embeddings,
    )

    # Resume support: chunks are stored in order, so the existing row count
    # tells us how far a previous (possibly rate-limited) run got.
    done = db._connection.execute(f"SELECT count(*) AS n FROM {TABLE}").fetchone()["n"]
    if done:
        if done > len(chunks):
            sys.exit(
                f"Error: {DB_PATH.name} has {done} chunks but data/ yields {len(chunks)}. "
                "Delete the file and re-run if the source documents changed."
            )
        print(f"Resuming after {done} already-embedded chunks")
    remaining = chunks[done:]

    # Batch request size: the embedding API accepts up to 100 texts per request,
    # but free-tier quotas are tight, so keep it small.
    batch_size = 4
    for start in range(0, len(remaining), batch_size):
        batch = remaining[start : start + batch_size]
        _add_with_retry(db, batch)
        print(f"Embedded {done + min(start + batch_size, len(remaining))}/{len(chunks)} chunks")

    print(f"Done. Vector store: {DB_PATH}")


if __name__ == "__main__":
    main()
