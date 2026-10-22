"""OpenAI-compatible embeddings endpoint backed by a local bge-m3 model.

The knowledge base stores one 1024-dimension vector per chunk, produced by
BAAI/bge-m3 through a remote relay. This service reproduces the same vectors
on the server itself so retrieval no longer depends on that relay, while the
chat model can still be changed independently.

Vectors must stay in the exact space the stored index was built in: plain
`encode` with no instruction prefix, float32, no normalisation (the search
side normalises after loading).
"""

import os
import threading

from fastapi import FastAPI
from pydantic import BaseModel

MODEL_PATH = os.environ["EMBEDDING_MODEL_PATH"]
MODEL_NAME = os.environ.get("EMBEDDING_MODEL", "bge-m3")

app = FastAPI()
_model = None
_lock = threading.Lock()


def model():
    """Load the weights once, on first use, so /health answers before that."""

    global _model
    with _lock:
        if _model is None:
            from sentence_transformers import SentenceTransformer

            _model = SentenceTransformer(MODEL_PATH, device="cpu", local_files_only=True)
            _model.eval()
        return _model


class EmbeddingsRequest(BaseModel):
    model: str | None = None
    input: str | list[str]


@app.get("/health")
def health() -> dict[str, object]:
    return {"status": "ok", "model": MODEL_NAME, "loaded": _model is not None}


@app.post("/v1/embeddings")
def embeddings(request: EmbeddingsRequest) -> dict[str, object]:
    texts = [request.input] if isinstance(request.input, str) else list(request.input)
    vectors = model().encode(texts, normalize_embeddings=False, batch_size=8)
    return {
        "object": "list",
        "model": request.model or MODEL_NAME,
        "data": [
            {"object": "embedding", "index": index, "embedding": vector.tolist()}
            for index, vector in enumerate(vectors)
        ],
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8080")))
