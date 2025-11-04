"""
User management endpoints.
"""

from typing import List, Optional
from fastapi import APIRouter, HTTPException, status, Query
from beanie import PydanticObjectId

from backend.models import User
from shared.constants import UserRole


router = APIRouter()


@router.post(
    "/users",
    response_model=User,
    status_code=status.HTTP_201_CREATED,
    summary="Create new user"
)
async def create_user(
    telegram_id: int,
    role: UserRole,
    username: Optional[str] = None,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
):
    """Create a new user."""
    # Check if user already exists
    existing_user = await User.find_one(User.telegram_id == telegram_id)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this telegram_id already exists"
        )

    user = User(
        telegram_id=telegram_id,
        role=role,
        username=username,
        first_name=first_name,
        last_name=last_name,
    )
    await user.insert()
    return user


@router.get(
    "/users/{user_id}",
    response_model=User,
    summary="Get user by ID"
)
async def get_user(user_id: PydanticObjectId):
    """Get user by ID."""
    user = await User.get(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return user


@router.get(
    "/users/telegram/{telegram_id}",
    response_model=User,
    summary="Get user by Telegram ID"
)
async def get_user_by_telegram_id(telegram_id: int):
    """Get user by Telegram ID."""
    user = await User.find_one(User.telegram_id == telegram_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return user


@router.get(
    "/users",
    response_model=List[User],
    summary="List users"
)
async def list_users(
    role: Optional[UserRole] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100)
):
    """List users with optional filtering."""
    query = {}
    if role:
        query["role"] = role

    users = await User.find(query).skip(skip).limit(limit).to_list()
    return users


@router.patch(
    "/users/{user_id}",
    response_model=User,
    summary="Update user"
)
async def update_user(user_id: PydanticObjectId, **kwargs):
    """Update user fields."""
    user = await User.get(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    await user.set(kwargs)
    return user


@router.delete(
    "/users/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete user"
)
async def delete_user(user_id: PydanticObjectId):
    """Delete user."""
    user = await User.get(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    await user.delete()
