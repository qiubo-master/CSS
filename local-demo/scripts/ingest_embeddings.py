from __future__ import annotations

import json
import sys
from pathlib import Path
import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import settings


def main():
    chunks_path = settings.data_dir / "knowledge_chunks.json"
    output_path = settings.data_dir / "knowledge_vectors.json"
    chunks = json.loads(chunks_path.read_text(encoding="utf-8"))
    texts = [x["title"] + "\n" + x["content"] for x in chunks]
    with httpx.Client(timeout=180) as client:
        response = client.post(
            f"{settings.ollama_base_url}/api/embed",
            json={"model": settings.embed_model, "input": texts},
        )
        response.raise_for_status()
        embeddings = response.json()["embeddings"]
    vectors = {chunk["chunk_id"]: vector for chunk, vector in zip(chunks, embeddings)}
    output_path.write_text(json.dumps(vectors, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {len(vectors)} vectors to {output_path}; dim={len(embeddings[0])}")


if __name__ == "__main__":
    main()
