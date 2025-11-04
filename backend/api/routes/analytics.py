"""
Analytics and statistics API endpoints.
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from loguru import logger

from backend.models import User, Vacancy, Resume
from backend.api.dependencies import get_current_user
from backend.services.analytics_service import analytics_service
from shared.constants import UserRole

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/my-statistics")
async def get_my_statistics(current_user: User = Depends(get_current_user)):
    """
    Get statistics for current user.

    Returns different data based on user role:
    - Applicant: resume views, applications, success rate
    - Employer: vacancy views, responses, conversion rate
    """
    try:
        stats = await analytics_service.get_user_statistics(current_user)
        return stats
    except Exception as e:
        logger.error(f"Error getting user statistics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve statistics"
        )


@router.get("/vacancy/{vacancy_id}")
async def get_vacancy_analytics(
    vacancy_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Get detailed analytics for a specific vacancy.

    Returns:
    - Days active
    - Views count
    - Responses count
    - Conversion rate
    - Response breakdown by status
    - Average response time
    """
    try:
        # Get vacancy and verify ownership
        vacancy = await Vacancy.get(vacancy_id)
        if not vacancy:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Vacancy not found"
            )

        if str(vacancy.user.id) != str(current_user.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to view this vacancy's analytics"
            )

        analytics = await analytics_service.get_vacancy_analytics(vacancy)
        return analytics

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting vacancy analytics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve vacancy analytics"
        )


@router.get("/resume/{resume_id}")
async def get_resume_analytics(
    resume_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Get detailed analytics for a specific resume.

    Returns:
    - Days active
    - Views count
    - Applications sent vs invitations received
    - Success rate
    - Response breakdown by status
    """
    try:
        # Get resume and verify ownership
        resume = await Resume.get(resume_id)
        if not resume:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Resume not found"
            )

        if str(resume.user.id) != str(current_user.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to view this resume's analytics"
            )

        analytics = await analytics_service.get_resume_analytics(resume)
        return analytics

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting resume analytics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve resume analytics"
        )


@router.get("/trending-positions")
async def get_trending_positions(
    limit: int = 10,
    current_user: User = Depends(get_current_user)
):
    """
    Get trending job positions based on recent activity.

    Returns list of positions with:
    - Position name
    - Count of active vacancies
    - Total views
    - Total responses
    """
    try:
        trending = await analytics_service.get_trending_positions(limit=limit)
        return trending
    except Exception as e:
        logger.error(f"Error getting trending positions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve trending positions"
        )
