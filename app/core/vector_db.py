import logging
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance, VectorParams
from app.core.config import get_settings

logger = logging.getLogger(__name__)

_client: AsyncQdrantClient | None = None


async def connect_vector_db(app) -> None:
    global _client
    settings = get_settings()

    _client = AsyncQdrantClient(
        url=settings.qdrant_url,
        api_key=settings.qdrant_api_key or None,
    )

    await _ensure_collection(_client, settings.qdrant_collection_name, settings.embedding_dim)
    await _ensure_collection(_client, settings.qdrant_document_collection_name, settings.embedding_dim)

    app.state.qdrant_client = _client
    logger.info("Qdrant connected")


async def disconnect_vector_db(app) -> None:
    global _client

    if _client:
        await _client.close()
        _client = None
        logger.info("Qdrant disconnected")


async def _ensure_collection(client: AsyncQdrantClient, collection_name: str, vector_size: int) -> None:
    exists = await client.collection_exists(collection_name)

    if not exists:
        await client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
        )
        logger.info(f"Created Qdrant collection '{collection_name}'")


def get_qdrant_client() -> AsyncQdrantClient:
    if _client is None:
        raise RuntimeError("Qdrant client not initialized. Call connect_vector_db during app startup.")
    return _client