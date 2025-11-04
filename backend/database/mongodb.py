"""
MongoDB connection and initialization using Beanie ODM.
"""

from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie
from typing import Optional
from loguru import logger

from config.settings import settings
from backend.models import DOCUMENT_MODELS


class MongoDB:
    """MongoDB connection manager."""

    client: Optional[AsyncIOMotorClient] = None
    db = None

    @classmethod
    async def connect(cls):
        """Connect to MongoDB and initialize Beanie."""
        try:
            logger.info(f"Connecting to MongoDB at {settings.mongodb_url}")

            # Create Motor client
            cls.client = AsyncIOMotorClient(
                settings.mongodb_url,
                minPoolSize=settings.mongodb_min_pool_size,
                maxPoolSize=settings.mongodb_max_pool_size,
            )

            # Get database
            cls.db = cls.client[settings.mongodb_db_name]

            # Initialize Beanie with document models
            await init_beanie(
                database=cls.db,
                document_models=DOCUMENT_MODELS,
            )

            logger.success("Successfully connected to MongoDB and initialized Beanie")

        except Exception as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            raise

    @classmethod
    async def disconnect(cls):
        """Disconnect from MongoDB."""
        if cls.client:
            cls.client.close()
            logger.info("Disconnected from MongoDB")

    @classmethod
    async def ping(cls) -> bool:
        """Check MongoDB connection."""
        try:
            await cls.client.admin.command("ping")
            return True
        except Exception as e:
            logger.error(f"MongoDB ping failed: {e}")
            return False


# Global instance
mongodb = MongoDB()
