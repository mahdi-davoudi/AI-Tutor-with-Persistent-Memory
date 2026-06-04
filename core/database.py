from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie
import logging

from app.core.config import get_settings

logger = logging.getLogger(__name__)


async def connect_db(app) -> None:
    """
    Initialize MongoDB connection and attach to app.state
    """
    settings = get_settings()

    client = AsyncIOMotorClient(
        settings.mongodb_url,
        serverSelectionTimeoutMS=5_000,
        tz_aware=True,
    )

    database = client[settings.database_name]

    # Import models here (avoid circular imports)
    from app.models.user import User
    from app.models.chat import ChatSession, Message
    from app.models.memory import Memory

    await init_beanie(
        database=database,
        document_models=[User, ChatSession, Message, Memory],
    )

    # attach to app state (IMPORTANT FIX)
    app.state.mongo_client = client
    app.state.mongo_db = database

    logger.info("MongoDB connected")


async def disconnect_db(app) -> None:
    """
    Gracefully close MongoDB connection
    """
    client = getattr(app.state, "mongo_client", None)

    if client:
        client.close()
        logger.info("MongoDB disconnected")