"""Document processing agent with RAG pipeline and reranking."""
from __future__ import annotations
import os
from typing import Any
from pathlib import Path
from loguru import logger

from backend.tools.registry import ToolRegistry, get_registry, ToolSpec, ToolCategory
from backend.llm.factory import get_llm_provider_instance, resolve_model
from backend.core.registry import get_plugin_registry


CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200
TOP_K = 10
RERANK_TOP_K = 5
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "nomic-embed-text")


class DocumentAgent:
    """Agent for ingesting PDFs, chunking, embedding, storing, retrieving, and reranking."""

    def __init__(self, registry: ToolRegistry | None = None):
        self.registry = registry or get_registry()
        self.llm = get_llm_provider_instance()
        self._embedding_provider = get_plugin_registry().get_embedding()
        self._register_tools()
        logger.info("DocumentAgent ready")

    def _register_tools(self) -> None:
        from backend.tools.pdf_loader import load_pdf as pdf_fn

        try:
            self.registry.get_spec("load_pdf")
        except KeyError:
            self.registry.register(
                "load_pdf",
                pdf_fn,
                ToolSpec(
                    name="load_pdf",
                    description="Extract text from a PDF file",
                    category=ToolCategory.DOCUMENT,
                ),
            )

        try:
            self.registry.get_spec("vector_store")
        except KeyError:
            vs = get_plugin_registry().get_vector_db()
            if vs:
                self.registry.register(
                    "vector_store",
                    vs.store,
                    ToolSpec(
                        name="vector_store",
                        description="ChromaDB vector store for document chunks",
                        category=ToolCategory.VECTOR_STORE,
                    ),
                )

    def ingest_pdf(self, pdf_path: str) -> dict[str, Any]:
        """Ingest a PDF: extract text, chunk, embed, and store in vector DB."""
        path = Path(pdf_path)
        if not path.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")

        logger.info(f"Ingesting PDF: {path.name}")

        full_text, pages = self.registry.execute("load_pdf", file_path=str(path))
        chunks = self._chunk_text(full_text, doc_id=path.stem)
        embeddings = self._create_embeddings([c["content"] for c in chunks])

        self.registry.execute(
            "vector_store",
            ids=[c["chunk_id"] for c in chunks],
            documents=[c["content"] for c in chunks],
            embeddings=embeddings,
            metadatas=[c["metadata"] for c in chunks],
        )

        logger.info(f"Ingested {len(chunks)} chunks from {path.name}")
        return {"doc_id": path.stem, "filename": path.name, "chunks": len(chunks)}

    def retrieve(self, query: str, top_k: int = TOP_K) -> list[dict[str, Any]]:
        """Retrieve relevant chunks with hybrid BM25 + dense fusion + reranking."""
        if not query:
            return []

        query_embedding = self._create_embedding(query)
        if not query_embedding:
            logger.warning("Could not create query embedding, returning empty")
            return []

        vdb = get_plugin_registry().get_vector_db()
        if vdb is None:
            logger.warning("No vector DB available, returning empty")
            return []

        import asyncio
        results = asyncio.run(vdb.query(query_embedding=query_embedding, top_k=top_k * 2))

        if not results:
            return []

        from backend.search.hybrid import hybrid_rerank
        scored = hybrid_rerank(
            query,
            results,
            query_embedding=query_embedding,
            bm25_weight=0.2,
            top_k=top_k,
        )

        reranked = self._rerank(query, scored)

        return reranked[:RERANK_TOP_K]

    def _chunk_text(self, text: str, doc_id: str) -> list[dict[str, Any]]:
        """Split text into overlapping chunks with metadata."""
        if not text:
            return []

        words = text.split()
        chunks = []
        chunk_index = 0
        start = 0

        while start < len(words):
            end = start + CHUNK_SIZE
            chunk_words = words[start:end]
            chunk_text = " ".join(chunk_words)

            chunks.append({
                "chunk_id": f"{doc_id}_{chunk_index}",
                "content": chunk_text,
                "metadata": {
                    "doc_id": doc_id,
                    "chunk_index": chunk_index,
                    "word_count": len(chunk_words),
                    "char_count": len(chunk_text),
                    "source": "pdf",
                },
            })

            chunk_index += 1
            start += CHUNK_SIZE - CHUNK_OVERLAP

            if len(chunk_words) < CHUNK_SIZE:
                break

        logger.debug(f"Created {len(chunks)} chunks from {len(words)} words")
        return chunks

    def _create_embeddings(self, texts: list[str]) -> list[list[float]]:
        """Create embeddings in batches via the embedding provider."""
        if self._embedding_provider is None:
            return [[0.0] * 768 for _ in texts]
        result = self._embedding_provider.embed(texts, model=EMBEDDING_MODEL)
        if result is None:
            return [[0.0] * 768 for _ in texts]
        return result

    def _create_embedding(self, text: str) -> list[float] | None:
        """Create a single embedding via the embedding provider."""
        if self._embedding_provider is None:
            return None
        return self._embedding_provider.embed_query(text, model=EMBEDDING_MODEL)

    def _rerank(self, query: str, results: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Rerank results using cross-encoder style relevance scoring."""
        if not results:
            return results

        scored = []
        for r in results:
            score = self._compute_relevance(query, r.get("content", ""))
            r["relevance_score"] = score
            scored.append(r)

        scored.sort(key=lambda x: x.get("relevance_score", 0.0), reverse=True)

        for i, r in enumerate(scored):
            r["rank"] = i + 1

        return scored

    def _compute_relevance(self, query: str, chunk: str) -> float:
        """Score a chunk's relevance using LLM cross-encoder scoring."""
        try:
            relevance_model = os.getenv("RELEVANCE_MODEL", resolve_model("answer_agent"))
            prompt = (
                f"Rate the relevance of the following document chunk to the query "
                f"on a scale of 0.0 to 1.0 (where 0.0 is completely irrelevant "
                f"and 1.0 is perfectly relevant). Return ONLY a single float number.\n\n"
                f"Query: {query[:500]}\n\n"
                f"Chunk: {chunk[:1500]}"
            )
            raw = self.llm.generate(
                prompt=prompt,
                model=relevance_model,
                system_prompt="You are a relevance scorer. Output only a float between 0.0 and 1.0.",
                options={"temperature": 0.1, "num_predict": 10},
            )

            raw = raw.strip()
            score = float(raw)
            return max(0.0, min(1.0, score))
        except (ValueError, TypeError):
            pass
        except Exception as e:
            logger.debug(f"LLM relevance scoring failed, using cosine fallback: {e}")

        try:
            q_emb = self._create_embedding(query)
            c_emb = self._create_embedding(chunk[:2000])
            if q_emb and c_emb:
                return self._cosine_similarity(q_emb, c_emb)
        except Exception:
            pass
        return 0.0

    @staticmethod
    def _cosine_similarity(a: list[float], b: list[float]) -> float:
        if not a or not b or len(a) != len(b):
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(y * y for y in b) ** 0.5
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)
