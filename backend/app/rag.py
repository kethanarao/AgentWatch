"""Deterministic TF-IDF demo retrieval; local sentence-transformers + FAISS in live mode."""

import hashlib
import re
from pathlib import Path

import numpy as np

from .config import ROOT, Settings

STOP = set(
    "a an the is my why how do does i in on for of to and with after can it are what should".split()
)


def terms(text: str):
    return [w for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in STOP]


def feature_embedding(text: str, dimensions: int = 64) -> list[float]:
    """Stable hashed lexical embedding for lightweight demo drift; not semantic ST vectors."""
    vector = np.zeros(dimensions)
    for word in terms(text):
        vector[int(hashlib.sha256(word.encode()).hexdigest()[:8], 16) % dimensions] += 1
    norm = np.linalg.norm(vector)
    return (vector / norm if norm else vector).tolist()


def chunks(text: str, size: int = 150, overlap: int = 25):
    words = text.split()
    return [" ".join(words[i : i + size]) for i in range(0, len(words), size - overlap)]


class Retriever:
    def __init__(self, config: Settings, directory: Path = ROOT / "data/knowledge_base"):
        self.config = config
        self.documents = []
        for path in sorted(directory.glob("*.md")):
            text = path.read_text(encoding="utf-8")
            for j, chunk in enumerate(chunks(text)):
                self.documents.append(
                    {
                        "id": path.stem,
                        "chunk_id": f"{path.stem}:{j}",
                        "title": text.splitlines()[0][2:],
                        "text": chunk,
                        "updated_at": "2026-08-01",
                        "stale": False,
                    }
                )
        if not self.documents:
            raise RuntimeError("Knowledge base is empty. Run python scripts/build_datasets.py")
        self.vocab = sorted({w for d in self.documents for w in terms(d["text"])})
        self.lookup = {w: i for i, w in enumerate(self.vocab)}
        counts = np.array([self._counts(d["text"]) for d in self.documents])
        self.idf = np.log((1 + len(counts)) / (1 + (counts > 0).sum(axis=0))) + 1
        self.vectors = self._normalize(counts * self.idf)
        self.model = None
        self.index = None
        self.cross_encoder = None
        if config.semantic_retrieval:
            import faiss
            from sentence_transformers import CrossEncoder, SentenceTransformer

            self.model = SentenceTransformer(config.embedding_model)
            self.vectors = self.model.encode(
                [d["text"] for d in self.documents], normalize_embeddings=True
            )
            self.index = faiss.IndexFlatIP(self.vectors.shape[1])
            self.index.add(np.asarray(self.vectors, dtype="float32"))
            if config.rerank:
                self.cross_encoder = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")

    def _counts(self, text):
        row = np.zeros(len(self.vocab))
        for word in terms(text):
            if word in self.lookup:
                row[self.lookup[word]] += 1
        return row

    @staticmethod
    def _normalize(vectors):
        norm = np.linalg.norm(vectors, axis=-1, keepdims=True)
        return vectors / np.maximum(norm, 1e-10)

    def embed(self, query):
        if self.model is not None:
            return self.model.encode([query], normalize_embeddings=True)[0]
        return self._normalize(self._counts(query) * self.idf)

    def search(self, query: str, top_k: int = 3, vector=None):
        vector = self.embed(query) if vector is None else vector
        if self.index is not None:
            scores, indices = self.index.search(np.array([vector], dtype="float32"), top_k)
            pairs = list(zip(indices[0], scores[0]))
        else:
            scores = self.vectors @ vector
            pairs = [(int(i), float(scores[i])) for i in np.argsort(-scores, kind="stable")[:top_k]]
        docs = [
            {**self.documents[i], "score": round(float(score), 4)} for i, score in pairs if i >= 0
        ]
        if self.cross_encoder and docs:
            reranked = self.cross_encoder.predict([(query, d["text"]) for d in docs])
            docs = [
                d for _, d in sorted(zip(reranked, docs), key=lambda x: float(x[0]), reverse=True)
            ]
        return docs
