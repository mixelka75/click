"""
Main FastAPI application.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
import sys

from config.settings import settings
from backend.database import mongodb
from backend.api.routes import health, users, resumes, vacancies, responses, analytics, recommendations, auth, favorites, chats
from backend.services.notification_service import notification_service
from backend.services.expiration_service import expiration_service


# Configure logging
logger.remove()
logger.add(
    sys.stdout,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
    level=settings.log_level,
)
logger.add(
    settings.log_file,
    rotation="500 MB",
    retention="10 days",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function} - {message}",
    level=settings.log_level,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events."""
    # Startup
    logger.info("Starting up CLICK application...")
    await mongodb.connect()

    # Initialize notification service with bot
    try:
        from aiogram import Bot
        bot = Bot(token=settings.bot_token)
        notification_service.initialize(bot)
        logger.success("Notification service initialized")
    except Exception as e:
        logger.error(f"Failed to initialize notification service: {e}")

    # Start expiration service
    try:
        expiration_service.start()
        logger.success("Expiration service started")
    except Exception as e:
        logger.error(f"Failed to start expiration service: {e}")

    logger.success("Application startup complete")

    yield

    # Shutdown
    logger.info("Shutting down CLICK application...")

    # Stop expiration service
    try:
        await expiration_service.stop()
        logger.info("Expiration service stopped")
    except Exception as e:
        logger.error(f"Error stopping expiration service: {e}")

    await mongodb.disconnect()

    # Close bot session
    try:
        if notification_service.bot:
            await notification_service.bot.session.close()
            logger.info("Bot session closed")
    except Exception as e:
        logger.error(f"Error closing bot session: {e}")

    logger.info("Application shutdown complete")


# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="HoReCa Recruitment Platform - API for finding jobs and employees in hospitality industry",
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    lifespan=lifespan,
)


# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.debug else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Include routers
app.include_router(health.router, prefix=settings.api_prefix, tags=["Health"])
app.include_router(auth.router, prefix=settings.api_prefix, tags=["Authentication"])
app.include_router(users.router, prefix=settings.api_prefix, tags=["Users"])
app.include_router(resumes.router, prefix=settings.api_prefix, tags=["Resumes"])
app.include_router(vacancies.router, prefix=settings.api_prefix, tags=["Vacancies"])
app.include_router(responses.router, prefix=settings.api_prefix, tags=["Responses"])
app.include_router(analytics.router, prefix=settings.api_prefix, tags=["Analytics"])
app.include_router(recommendations.router, prefix=settings.api_prefix, tags=["Recommendations"])
app.include_router(favorites.router, prefix=settings.api_prefix, tags=["Favorites"])
app.include_router(chats.router, prefix=settings.api_prefix, tags=["Chats"])


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "status": "running",
        "environment": settings.environment,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "backend.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
    )
