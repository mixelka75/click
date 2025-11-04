"""
Health check endpoints.
"""

from fastapi import APIRouter, status
from datetime import datetime
from pydantic import BaseModel

from config.settings import settings
from backend.database import mongodb


router = APIRouter()


class HealthResponse(BaseModel):
    """Health check response model."""
    status: str
    timestamp: datetime
    version: str
    environment: str
    database: str


class DetailedHealthResponse(HealthResponse):
    """Detailed health check response."""
    mongodb_connected: bool


@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Basic health check"
)
async def health_check():
    """Basic health check endpoint."""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.utcnow(),
        version=settings.app_version,
        environment=settings.environment,
        database="mongodb"
    )


@router.get(
    "/health/detailed",
    response_model=DetailedHealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Detailed health check with DB status"
)
async def detailed_health_check():
    """Detailed health check including database connectivity."""
    mongodb_connected = await mongodb.ping()

    return DetailedHealthResponse(
        status="healthy" if mongodb_connected else "degraded",
        timestamp=datetime.utcnow(),
        version=settings.app_version,
        environment=settings.environment,
        database="mongodb",
        mongodb_connected=mongodb_connected
    )


@router.get(
    "/ping",
    status_code=status.HTTP_200_OK,
    summary="Simple ping endpoint"
)
async def ping():
    """Simple ping endpoint."""
    return {"ping": "pong"}
