"""
Authentication utilities for Telegram Bot to API integration.
"""

from typing import Optional
from aiogram.fsm.context import FSMContext
from aiogram.types import User as TelegramUser
from loguru import logger
import httpx

from config.settings import settings


async def get_or_create_token(telegram_user: TelegramUser, state: FSMContext, role: Optional[str] = None) -> Optional[str]:
    """
    Get existing token or create new one via API authentication.

    This function is called when user starts interaction with bot.
    It authenticates user with backend and stores JWT token in FSM state.

    Args:
        telegram_user: Telegram user object from message/callback
        state: FSM context to store token
        role: Optional user role (applicant/employer)

    Returns:
        JWT token string or None if authentication failed
    """
    try:
        # Prepare authentication request
        auth_data = {
            "telegram_id": telegram_user.id,
            "username": telegram_user.username,
            "first_name": telegram_user.first_name,
            "last_name": telegram_user.last_name,
        }

        if role:
            auth_data["role"] = role

        # Call backend authentication endpoint
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"http://backend:8000{settings.api_prefix}/auth/telegram",
                json=auth_data,
                timeout=10.0
            )

            if response.status_code == 200:
                data = response.json()
                token = data.get("access_token")
                user_id = data.get("user_id")
                user_role = data.get("role")

                # Store token and user info in FSM state
                await state.update_data(
                    token=token,
                    user_id=user_id,
                    telegram_id=telegram_user.id,
                    role=user_role
                )

                logger.info(f"User authenticated: telegram_id={telegram_user.id}, role={user_role}")
                return token

            else:
                logger.error(f"Authentication failed: {response.status_code} - {response.text}")
                return None

    except Exception as e:
        logger.error(f"Error during authentication: {e}")
        return None


async def get_user_token(state: FSMContext) -> Optional[str]:
    """
    Get stored JWT token from FSM state.

    Used in handlers that require authenticated API access.

    Args:
        state: FSM context

    Returns:
        JWT token string or None if not authenticated
    """
    data = await state.get_data()
    return data.get("token")


async def get_user_id(state: FSMContext) -> Optional[str]:
    """
    Get user ID from FSM state.

    Args:
        state: FSM context

    Returns:
        MongoDB user ID or None
    """
    data = await state.get_data()
    return data.get("user_id")


async def get_user_role(state: FSMContext) -> Optional[str]:
    """
    Get user role from FSM state.

    Args:
        state: FSM context

    Returns:
        User role (applicant/employer/manager) or None
    """
    data = await state.get_data()
    return data.get("role")


async def update_user_role(state: FSMContext, role: str) -> bool:
    """
    Update user role both in FSM state and via API.

    Used when user changes their role (e.g., from applicant to employer).

    Args:
        state: FSM context
        role: New role (applicant/employer)

    Returns:
        True if successful, False otherwise
    """
    try:
        token = await get_user_token(state)
        if not token:
            return False

        user_id = await get_user_id(state)
        if not user_id:
            return False

        # Update role via API
        async with httpx.AsyncClient() as client:
            response = await client.patch(
                f"http://backend:8000{settings.api_prefix}/users/{user_id}",
                json={"role": role},
                headers={"Authorization": f"Bearer {token}"},
                timeout=10.0
            )

            if response.status_code == 200:
                # Update FSM state
                await state.update_data(role=role)
                logger.info(f"User role updated: user_id={user_id}, role={role}")
                return True
            else:
                logger.error(f"Failed to update role: {response.status_code}")
                return False

    except Exception as e:
        logger.error(f"Error updating user role: {e}")
        return False


async def refresh_token(state: FSMContext, telegram_id: int) -> Optional[str]:
    """
    Refresh expired JWT token.

    Args:
        state: FSM context
        telegram_id: Telegram user ID

    Returns:
        New JWT token or None if refresh failed
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"http://backend:8000{settings.api_prefix}/auth/refresh",
                json={"telegram_id": telegram_id},
                timeout=10.0
            )

            if response.status_code == 200:
                data = response.json()
                token = data.get("access_token")

                # Update token in FSM state
                await state.update_data(token=token)
                logger.info(f"Token refreshed for telegram_id={telegram_id}")
                return token
            else:
                logger.error(f"Token refresh failed: {response.status_code}")
                return None

    except Exception as e:
        logger.error(f"Error refreshing token: {e}")
        return None


async def is_authenticated(state: FSMContext) -> bool:
    """
    Check if user is authenticated.

    Args:
        state: FSM context

    Returns:
        True if user has valid token, False otherwise
    """
    token = await get_user_token(state)
    return token is not None


async def logout(state: FSMContext):
    """
    Clear authentication data from FSM state.

    Args:
        state: FSM context
    """
    data = await state.get_data()
    # Remove auth-related keys
    data.pop("token", None)
    data.pop("user_id", None)
    data.pop("telegram_id", None)
    data.pop("role", None)
    await state.set_data(data)
    logger.info("User logged out")
