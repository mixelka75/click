"""
Authentication and authorization endpoints.
"""

from datetime import timedelta
from typing import Optional
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from loguru import logger

from backend.models import User, Manager
from backend.api.dependencies import create_access_token
from shared.constants import UserRole


router = APIRouter(prefix="/auth", tags=["auth"])


class TelegramAuthRequest(BaseModel):
    """Telegram authentication request."""

    telegram_id: int = Field(..., description="Telegram user ID")
    username: Optional[str] = Field(None, description="Telegram username")
    first_name: Optional[str] = Field(None, description="First name")
    last_name: Optional[str] = Field(None, description="Last name")
    role: Optional[UserRole] = Field(None, description="User role (if known)")


class TokenResponse(BaseModel):
    """JWT token response."""

    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field(default="bearer", description="Token type")
    user_id: str = Field(..., description="User ID")
    telegram_id: int = Field(..., description="Telegram ID")
    role: UserRole = Field(..., description="User role")
    expires_in: int = Field(..., description="Token expiration time in seconds")


class ManagerAuthRequest(BaseModel):
    """Manager authentication request."""

    api_key: str = Field(..., description="API key")
    api_secret: str = Field(..., description="API secret")


@router.post(
    "/telegram",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Authenticate via Telegram",
    description="""
    Authenticate user via Telegram Bot.

    This endpoint is called by the Telegram Bot when user starts interaction.
    If user doesn't exist, creates new user account.
    Returns JWT token for API access.

    Flow:
    1. User interacts with Telegram Bot
    2. Bot calls this endpoint with Telegram user data
    3. Backend creates/updates user and returns JWT token
    4. Bot stores token for API calls on behalf of user
    """
)
async def telegram_auth(request: TelegramAuthRequest) -> TokenResponse:
    """
    Authenticate user via Telegram.

    Creates or updates user based on Telegram ID.
    Returns JWT token for subsequent API calls.
    """
    try:
        # Try to find existing user
        user = await User.find_one(User.telegram_id == request.telegram_id)

        if user:
            # Update user info from Telegram
            user.username = request.username
            user.first_name = request.first_name
            user.last_name = request.last_name

            # Update role if provided and not set
            if request.role and user.role != request.role:
                user.role = request.role

            await user.save()
            logger.info(f"Updated existing user: {user.telegram_id}")

        else:
            # Create new user
            user = User(
                telegram_id=request.telegram_id,
                username=request.username,
                first_name=request.first_name,
                last_name=request.last_name,
                role=request.role or UserRole.APPLICANT,
            )
            await user.insert()
            logger.info(f"Created new user: {user.telegram_id}")

        # Create access token
        token_data = {
            "user_id": str(user.id),
            "telegram_id": user.telegram_id,
            "role": user.role.value,
        }

        access_token = create_access_token(
            data=token_data,
            expires_delta=timedelta(days=30)  # Long-lived token for bot
        )

        return TokenResponse(
            access_token=access_token,
            token_type="bearer",
            user_id=str(user.id),
            telegram_id=user.telegram_id,
            role=user.role,
            expires_in=30 * 24 * 60 * 60,  # 30 days in seconds
        )

    except Exception as e:
        logger.error(f"Telegram auth error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication failed"
        )


@router.post(
    "/manager",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Authenticate manager",
    description="""
    Authenticate manager with API credentials.

    Managers have special access for:
    - Bulk data operations
    - Google Sheets integration
    - CRM functionality
    - Database management
    """
)
async def manager_auth(request: ManagerAuthRequest) -> TokenResponse:
    """
    Authenticate manager via API credentials.

    Returns JWT token for manager API access.
    """
    try:
        # Find manager by API key
        manager = await Manager.find_one(Manager.api_key == request.api_key)

        if not manager:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API credentials"
            )

        # Verify API secret (in production, use hashing)
        if manager.api_secret != request.api_secret:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API credentials"
            )

        if not manager.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Manager account is inactive"
            )

        # Get user associated with manager
        user = await User.find_one(User.telegram_id == manager.telegram_id)

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Manager user not found"
            )

        # Create access token with manager privileges
        token_data = {
            "user_id": str(user.id),
            "telegram_id": user.telegram_id,
            "role": UserRole.MANAGER.value,
            "manager_id": str(manager.id),
            "api_key": manager.api_key,
        }

        access_token = create_access_token(
            data=token_data,
            expires_delta=timedelta(hours=8)  # 8 hours for manager sessions
        )

        logger.info(f"Manager authenticated: {manager.email}")

        return TokenResponse(
            access_token=access_token,
            token_type="bearer",
            user_id=str(user.id),
            telegram_id=user.telegram_id,
            role=UserRole.MANAGER,
            expires_in=8 * 60 * 60,  # 8 hours in seconds
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Manager auth error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication failed"
        )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Refresh access token",
    description="Refresh an expired or expiring JWT token"
)
async def refresh_token(telegram_id: int) -> TokenResponse:
    """
    Refresh access token for a user.

    Used when the current token is expired or about to expire.
    Requires telegram_id to identify the user.
    """
    try:
        user = await User.find_one(User.telegram_id == telegram_id)

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is inactive"
            )

        # Create new access token
        token_data = {
            "user_id": str(user.id),
            "telegram_id": user.telegram_id,
            "role": user.role.value,
        }

        access_token = create_access_token(
            data=token_data,
            expires_delta=timedelta(days=30)
        )

        return TokenResponse(
            access_token=access_token,
            token_type="bearer",
            user_id=str(user.id),
            telegram_id=user.telegram_id,
            role=user.role,
            expires_in=30 * 24 * 60 * 60,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Token refresh error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Token refresh failed"
        )
