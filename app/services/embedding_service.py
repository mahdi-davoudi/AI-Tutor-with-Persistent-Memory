import asyncio
from functools import lru_cache

from sentence_transformers import SentenceTransformer

from app.core.config import get_settings


class EmbeddingService:
    def __init__(self):
        settings = get_settings()
        self._model = SentenceTransformer(settings.embedding_model_name)

    def _encode(self, texts: list[str]) -> list[list[float]]:
        vectors = self._model.encode(texts, normalize_embeddings=True)
        return vectors.tolist()

    async def embed(self, text: str) -> list[float]:
        vectors = await asyncio.to_thread(self._encode, [text])
        return vectors[0]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return await asyncio.to_thread(self._encode, texts)


@lru_cache
def get_embedding_service() -> EmbeddingService:
    return EmbeddingService()