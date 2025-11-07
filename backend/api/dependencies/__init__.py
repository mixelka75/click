"""
API dependencies and utilities for authentication and authorization.
"""

from datetime import datetime, timedelta
from typing import Optional
from fastapi import Depends, HTTPException, status, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from beanie import PydanticObjectId

from config.settings import settings
from backend.models import User, Manager
from shared.constants import UserRole


# Security scheme for Swagger UI
security = HTTPBearer()


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create JWT access token.

    Args:
        data: Dictionary with token payload (user_id, telegram_id, role)
        expires_delta: Token expiration time

    Returns:
        Encoded JWT token string
    """
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.access_token_expire_minutes)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)
    return encoded_jwt


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> User:
    """
    Get current authenticated user from JWT token.

    This dependency extracts and validates the JWT token from the Authorization header.
    Used for protecting endpoints that require user authentication.

    Usage in routes:
        @router.get("/protected")
        async def protected_route(current_user: User = Depends(get_current_user)):
            return {"user_id": str(current_user.id)}

    Raises:
        HTTPException: 401 if token is invalid or user not found
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        token = credentials.credentials
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        user_id: str = payload.get("user_id")

        if user_id is None:
            raise credentials_exception

    except JWTError:
        raise credentials_exception

    # Get user from database
    user = await User.get(PydanticObjectId(user_id))

    if user is None:
        raise credentials_exception

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive"
        )

    # Update last active timestamp
    user.last_active = datetime.utcnow()
    await user.save()

    return user


async def get_current_user_optional(
    authorization: Optional[str] = Header(None)
) -> Optional[User]:
    """
    Get current user if token is provided, otherwise return None.

    This dependency allows optional authentication - endpoint works both
    with and without authentication, but behavior may differ.

    Usage:
        @router.get("/items")
        async def list_items(current_user: Optional[User] = Depends(get_current_user_optional)):
            if current_user:
                # Show personalized content
                pass
            else:
                # Show public content
                pass
    """
    if not authorization or not authorization.startswith("Bearer "):
        return None

    try:
        token = authorization.replace("Bearer ", "")
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        user_id: str = payload.get("user_id")

        if user_id:
            user = await User.get(PydanticObjectId(user_id))
            if user and user.is_active:
                user.last_active = datetime.utcnow()
                await user.save()
                return user
    except JWTError:
        pass

    return None


async def get_current_active_applicant(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Verify that current user is an applicant (job seeker).

    Usage:
        @router.get("/my-resumes")
        async def get_my_resumes(user: User = Depends(get_current_active_applicant)):
            # Only applicants can access this
            pass

    Raises:
        HTTPException: 403 if user is not an applicant
    """
    if current_user.role != UserRole.APPLICANT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This action is only available to applicants"
        )
    return current_user


async def get_current_active_employer(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Verify that current user is an employer.

    Usage:
        @router.get("/my-vacancies")
        async def get_my_vacancies(user: User = Depends(get_current_active_employer)):
            # Only employers can access this
            pass

    Raises:
        HTTPException: 403 if user is not an employer
    """
    if current_user.role != UserRole.EMPLOYER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This action is only available to employers"
        )
    return current_user


async def get_current_manager(
    x_api_key: str = Header(..., description="API key for manager access")
) -> Manager:
    """
    Authenticate manager by API key.

    Managers have special API access for bulk operations and integrations.
    Used for Google Sheets integration and CRM operations.

    Usage:
        @router.post("/bulk-upload")
        async def bulk_upload(manager: Manager = Depends(get_current_manager)):
            # Only managers with valid API key can access
            pass

    Headers:
        X-API-Key: Manager's API key

    Raises:
        HTTPException: 401 if API key is invalid
        HTTPException: 403 if manager account is inactive
    """
    manager = await Manager.find_one(Manager.api_key == x_api_key)

    if not manager:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key"
        )

    if not manager.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Manager account is inactive"
        )

    # Update last API call timestamp
    manager.last_api_call = datetime.utcnow()
    await manager.save()

    return manager


async def verify_admin(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Verify that current user is an admin.

    Admin users are configured via ADMIN_IDS environment variable.

    Usage:
        @router.delete("/users/{user_id}")
        async def delete_user(
            user_id: str,
            admin: User = Depends(verify_admin)
        ):
            # Only admins can delete users
            pass

    Raises:
        HTTPException: 403 if user is not an admin
    """
    if current_user.telegram_id not in settings.admin_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user


__all__ = [
    "create_access_token",
    "get_current_user",
    "get_current_user_optional",
    "get_current_active_applicant",
    "get_current_active_employer",
    "get_current_manager",
    "verify_admin",
    "security",
]
