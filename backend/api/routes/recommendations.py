"""
Recommendation system API endpoints.
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from loguru import logger

from backend.models import User, Vacancy, Resume
from backend.api.dependencies import get_current_user
from backend.services.recommendation_service import recommendation_service
from shared.constants import UserRole

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


@router.get("/vacancies-for-resume/{resume_id}")
async def get_vacancy_recommendations(
    resume_id: str,
    limit: int = Query(10, ge=1, le=50),
    min_score: float = Query(40.0, ge=0, le=100),
    current_user: User = Depends(get_current_user)
):
    """
    Get recommended vacancies for a specific resume.

    Returns list of vacancies sorted by match score with details:
    - Vacancy object
    - Match score (0-100)
    - Match details (skills matched, location match, etc.)

    Query parameters:
    - limit: Maximum number of recommendations (1-50)
    - min_score: Minimum match score threshold (0-100)
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
                detail="Not authorized to access this resume"
            )

        # Get recommendations
        recommendations = await recommendation_service.recommend_vacancies_for_resume(
            resume=resume,
            limit=limit,
            min_score=min_score
        )

        return recommendations

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting vacancy recommendations: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve recommendations"
        )


@router.get("/resumes-for-vacancy/{vacancy_id}")
async def get_resume_recommendations(
    vacancy_id: str,
    limit: int = Query(10, ge=1, le=50),
    min_score: float = Query(40.0, ge=0, le=100),
    current_user: User = Depends(get_current_user)
):
    """
    Get recommended resumes (candidates) for a specific vacancy.

    Returns list of resumes sorted by match score with details:
    - Resume object
    - Match score (0-100)
    - Match details (skills matched, location match, etc.)

    Query parameters:
    - limit: Maximum number of recommendations (1-50)
    - min_score: Minimum match score threshold (0-100)
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
                detail="Not authorized to access this vacancy"
            )

        # Get recommendations
        recommendations = await recommendation_service.recommend_resumes_for_vacancy(
            vacancy=vacancy,
            limit=limit,
            min_score=min_score
        )

        return recommendations

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting resume recommendations: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve recommendations"
        )


@router.get("/match-score/{resume_id}/{vacancy_id}")
async def get_match_score(
    resume_id: str,
    vacancy_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Calculate match score between a specific resume and vacancy.

    Returns:
    - Match score (0-100)
    - Detailed breakdown by category
    - Match details
    """
    try:
        # Get resume and vacancy
        resume = await Resume.get(resume_id)
        vacancy = await Vacancy.get(vacancy_id)

        if not resume:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Resume not found"
            )

        if not vacancy:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Vacancy not found"
            )

        # Calculate score
        score = recommendation_service.calculate_match_score(resume, vacancy)
        match_details = recommendation_service._get_match_details(resume, vacancy)

        return {
            "resume_id": resume_id,
            "vacancy_id": vacancy_id,
            "score": round(score, 1),
            "match_details": match_details
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error calculating match score: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to calculate match score"
        )
