import logging
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance, VectorParams
from app.core.config import get_settings

logger = logging.getLogger(__name__)


async def connect_vector_db(app) -> None:
    settings = get_settings()

    client = AsyncQdrantClient(
        url=settings.qdrant_url,
        api_key=settings.qdrant_api_key or None,
    )

    await _ensure_collection(client, settings)

    app.state.qdrant_client = client
    logger.info("Qdrant connected")


async def disconnect_vector_db(app) -> None:
    client = getattr(app.state, "qdrant_client", None)

    if client:
        await client.close()
        logger.info("Qdrant disconnected")


async def _ensure_collection(client: AsyncQdrantClient, settings) -> None:
    exists = await client.collection_exists(settings.qdrant_collection_name)

    if not exists:
        await client.create_collection(
            collection_name=settings.qdrant_collection_name,
            vectors_config=VectorParams(
                size=settings.embedding_dim,
                distance=Distance.COSINE,
            ),
        )
        logger.info(f"Created Qdrant collection '{settings.qdrant_collection_name}'")


def get_qdrant_client(app) -> AsyncQdrantClient:
    return app.state.qdrant_client