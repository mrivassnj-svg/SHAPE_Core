"""
Tool: DocSearch
Searches an offline FAISS vector index of programming docs / snippets.
Gives SHAPE a knowledge base that works without internet on the Pi.

Group 3 — ITAI2376-14562
Members: Cherluk Sumdin, Olubukola Kukoyi, Taki Eddine Boubekri, Michael Rivas
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from langchain_core.tools import Tool

logger = logging.getLogger(__name__)


class DocSearchTool:
    """
    Semantic search over a local FAISS index of programming documentation.

    At startup the tool looks for a pre-built index at `index_path`.
    If no index exists it falls back to a lightweight keyword search over
    plain-text doc files in `docs_dir`, so the agent always has *something*
    to work with even before the index is built.

    Building the index (one-time, offline)
    ---------------------------------------
    Run:  python -m shape.tools.doc_search --build
    This embeds all .md/.txt files in docs_dir using a small sentence-
    transformer (all-MiniLM-L6-v2, ~80 MB) and saves a FAISS index.
    The model runs on CPU — perfectly fine on a Pi 5.
    """

    name = "doc_search"
    description = (
        "Searches the local offline documentation index for code examples, "
        "API references, and programming patterns. "
        "Input is a plain-language query string such as "
        "'how to open a file in Python' or 'list comprehension examples'."
    )

    def __init__(self, config: dict[str, Any]) -> None:
        self.index_path = Path(config.get("doc_index_path", "data/doc_index"))
        self.docs_dir = Path(config.get("docs_dir", "data/docs"))
        self.top_k = config.get("doc_top_k", 3)
        self._vectorstore = None
        self._load_index()

    # ------------------------------------------------------------------
    # Index loading
    # ------------------------------------------------------------------

    def _load_index(self) -> None:
        """Try to load the FAISS vector index; fall back gracefully."""
        if not self.index_path.exists():
            logger.info("DocSearch: no index found at %s — using keyword fallback.", self.index_path)
            return
        try:
            from langchain_community.embeddings import HuggingFaceEmbeddings
            from langchain_community.vectorstores import FAISS

            embeddings = HuggingFaceEmbeddings(
                model_name="sentence-transformers/all-MiniLM-L6-v2",
                model_kwargs={"device": "cpu"},
            )
            self._vectorstore = FAISS.load_local(
                str(self.index_path),
                embeddings,
                allow_dangerous_deserialization=True,
            )
            logger.info("DocSearch: FAISS index loaded from %s.", self.index_path)
        except Exception as exc:  # noqa: BLE001
            logger.warning("DocSearch: could not load FAISS index: %s", exc)

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def _vector_search(self, query: str) -> list[str]:
        docs = self._vectorstore.similarity_search(query, k=self.top_k)
        return [d.page_content for d in docs]

    def _keyword_fallback(self, query: str) -> list[str]:
        """Simple case-insensitive keyword search over plain text files."""
        if not self.docs_dir.exists():
            return []
        terms = query.lower().split()
        matches: list[tuple[int, str]] = []
        for doc_file in self.docs_dir.rglob("*.md"):
            try:
                text = doc_file.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            score = sum(1 for t in terms if t in text.lower())
            if score > 0:
                # Return a short excerpt around the first matching line
                for line in text.splitlines():
                    if any(t in line.lower() for t in terms):
                        matches.append((score, f"[{doc_file.name}] {line.strip()}"))
                        break
        matches.sort(key=lambda x: -x[0])
        return [m for _, m in matches[: self.top_k]]

    def _run(self, query: str) -> str:
        if not query.strip():
            return "[DocSearch] Please provide a search query."

        try:
            if self._vectorstore is not None:
                snippets = self._vector_search(query)
            else:
                snippets = self._keyword_fallback(query)
        except Exception as exc:  # noqa: BLE001
            return f"[DocSearch] Search error: {exc}"

        if not snippets:
            return "[DocSearch] No relevant documentation found for that query."

        return "\n\n---\n\n".join(snippets)

    def as_tool(self) -> Tool:
        return Tool(
            name=self.name,
            func=self._run,
            description=self.description,
        )


# ---------------------------------------------------------------------------
# Index builder (run directly: python -m shape.tools.doc_search --build)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Build SHAPE offline doc index.")
    parser.add_argument("--build", action="store_true")
    parser.add_argument("--docs-dir", default="data/docs")
    parser.add_argument("--index-path", default="data/doc_index")
    args = parser.parse_args()

    if args.build:
        from langchain.text_splitter import RecursiveCharacterTextSplitter
        from langchain_community.document_loaders import DirectoryLoader
        from langchain_community.embeddings import HuggingFaceEmbeddings
        from langchain_community.vectorstores import FAISS

        print("Loading documents…")
        loader = DirectoryLoader(args.docs_dir, glob="**/*.md")
        docs = loader.load()
        splitter = RecursiveCharacterTextSplitter(chunk_size=512, chunk_overlap=64)
        chunks = splitter.split_documents(docs)
        print(f"  {len(chunks)} chunks from {len(docs)} documents.")

        print("Embedding (CPU — this takes a few minutes on Pi)…")
        embeddings = HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-MiniLM-L6-v2",
            model_kwargs={"device": "cpu"},
        )
        vs = FAISS.from_documents(chunks, embeddings)
        vs.save_local(args.index_path)
        print(f"Index saved to {args.index_path}")
