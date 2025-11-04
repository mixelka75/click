"""
Vacancy endpoints.
"""

from typing import List, Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, status, Query
from beanie import PydanticObjectId

from backend.models import Vacancy, User
from backend.services import telegram_publisher
from shared.constants import VacancyStatus


router = APIRouter()


@router.post(
    "/vacancies",
    response_model=Vacancy,
    status_code=status.HTTP_201_CREATED,
    summary="Create new vacancy"
)
async def create_vacancy(
    user_id: PydanticObjectId,
    position: str,
    position_category: str,
    company_name: str,
    company_type: str,
    city: str,
    address: str,
    employment_type: str,
    required_experience: str,
    required_education: str,
    **kwargs
):
    """Create a new vacancy."""
    # Check if user exists
    user = await User.get(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Set expiration date
    publication_duration = kwargs.pop("publication_duration_days", 30)
    expires_at = datetime.utcnow() + timedelta(days=publication_duration)

    vacancy = Vacancy(
        user=user,
        position=position,
        position_category=position_category,
        company_name=company_name,
        company_type=company_type,
        city=city,
        address=address,
        employment_type=employment_type,
        required_experience=required_experience,
        required_education=required_education,
        publication_duration_days=publication_duration,
        expires_at=expires_at,
        **kwargs
    )
    await vacancy.insert()
    return vacancy


@router.get(
    "/vacancies/{vacancy_id}",
    response_model=Vacancy,
    summary="Get vacancy by ID"
)
async def get_vacancy(vacancy_id: PydanticObjectId):
    """Get vacancy by ID."""
    vacancy = await Vacancy.get(vacancy_id, fetch_links=True)
    if not vacancy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vacancy not found"
        )

    # Increment views count
    vacancy.views_count += 1
    await vacancy.save()

    return vacancy


@router.get(
    "/vacancies",
    response_model=List[Vacancy],
    summary="List vacancies with filtering"
)
async def list_vacancies(
    position_category: Optional[str] = None,
    city: Optional[str] = None,
    status: Optional[VacancyStatus] = None,
    min_salary: Optional[int] = None,
    max_salary: Optional[int] = None,
    employment_type: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100)
):
    """List vacancies with optional filtering."""
    query = {}

    if position_category:
        query["position_category"] = position_category
    if city:
        query["city"] = {"$regex": city, "$options": "i"}
    if status:
        query["status"] = status
    if min_salary:
        query["salary_min"] = {"$gte": min_salary}
    if max_salary:
        query.setdefault("salary_max", {})["$lte"] = max_salary
    if employment_type:
        query["employment_type"] = employment_type

    # Only show active and published vacancies that haven't expired
    query["status"] = VacancyStatus.ACTIVE
    query["is_published"] = True
    query["expires_at"] = {"$gt": datetime.utcnow()}

    vacancies = await Vacancy.find(query).skip(skip).limit(limit).to_list()
    return vacancies


@router.get(
    "/vacancies/user/{user_id}",
    response_model=List[Vacancy],
    summary="Get all vacancies by user"
)
async def get_user_vacancies(user_id: PydanticObjectId):
    """Get all vacancies created by a specific user (employer)."""
    user = await User.get(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    vacancies = await Vacancy.find(Vacancy.user.id == user_id).to_list()
    return vacancies


@router.patch(
    "/vacancies/{vacancy_id}",
    response_model=Vacancy,
    summary="Update vacancy"
)
async def update_vacancy(vacancy_id: PydanticObjectId, **kwargs):
    """Update vacancy fields."""
    vacancy = await Vacancy.get(vacancy_id)
    if not vacancy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vacancy not found"
        )

    # Update timestamp
    kwargs["updated_at"] = datetime.utcnow()

    await vacancy.set(kwargs)
    return vacancy


@router.patch(
    "/vacancies/{vacancy_id}/publish",
    response_model=Vacancy,
    summary="Publish vacancy"
)
async def publish_vacancy(vacancy_id: PydanticObjectId):
    """Publish vacancy (make it visible)."""
    vacancy = await Vacancy.get(vacancy_id, fetch_links=True)
    if not vacancy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vacancy not found"
        )

    vacancy.is_published = True
    vacancy.status = VacancyStatus.ACTIVE
    vacancy.published_at = datetime.utcnow()

    # Set expiration if not set
    if not vacancy.expires_at:
        duration = vacancy.publication_duration_days or 30
        vacancy.expires_at = datetime.utcnow() + timedelta(days=duration)

    await vacancy.save()

    # Publish to Telegram channels
    try:
        await telegram_publisher.publish_vacancy(vacancy)
    except Exception as e:
        # Log error but don't fail the request
        from loguru import logger
        logger.error(f"Failed to publish vacancy {vacancy_id} to Telegram: {e}")

    return vacancy


@router.patch(
    "/vacancies/{vacancy_id}/pause",
    response_model=Vacancy,
    summary="Pause vacancy"
)
async def pause_vacancy(vacancy_id: PydanticObjectId):
    """Pause vacancy (temporarily hide from search)."""
    vacancy = await Vacancy.get(vacancy_id)
    if not vacancy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vacancy not found"
        )

    vacancy.status = VacancyStatus.PAUSED
    await vacancy.save()

    return vacancy


@router.patch(
    "/vacancies/{vacancy_id}/archive",
    response_model=Vacancy,
    summary="Archive vacancy"
)
async def archive_vacancy(vacancy_id: PydanticObjectId):
    """Archive vacancy (hide from search permanently)."""
    vacancy = await Vacancy.get(vacancy_id)
    if not vacancy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vacancy not found"
        )

    vacancy.status = VacancyStatus.ARCHIVED
    vacancy.is_published = False
    await vacancy.save()

    return vacancy


@router.delete(
    "/vacancies/{vacancy_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete vacancy"
)
async def delete_vacancy(vacancy_id: PydanticObjectId):
    """Delete vacancy permanently."""
    vacancy = await Vacancy.get(vacancy_id)
    if not vacancy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vacancy not found"
        )

    await vacancy.delete()


@router.get(
    "/vacancies/search",
    response_model=List[Vacancy],
    summary="Search vacancies with advanced filters"
)
async def search_vacancies(
    q: Optional[str] = None,  # Search query
    position: Optional[str] = None,
    category: Optional[str] = None,
    city: Optional[str] = None,
    company_type: Optional[str] = None,
    required_skills: Optional[str] = None,  # Comma-separated
    min_salary: Optional[int] = None,
    max_salary: Optional[int] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100)
):
    """Advanced search for vacancies."""
    query = {
        "status": VacancyStatus.ACTIVE,
        "is_published": True,
        "expires_at": {"$gt": datetime.utcnow()}
    }

    if q:
        # Full-text search
        query["$or"] = [
            {"position": {"$regex": q, "$options": "i"}},
            {"description": {"$regex": q, "$options": "i"}},
            {"company_name": {"$regex": q, "$options": "i"}},
        ]

    if position:
        query["position"] = {"$regex": position, "$options": "i"}

    if category:
        query["position_category"] = category

    if city:
        query["city"] = {"$regex": city, "$options": "i"}

    if company_type:
        query["company_type"] = company_type

    if required_skills:
        skill_list = [s.strip() for s in required_skills.split(",")]
        query["required_skills"] = {"$in": skill_list}

    if min_salary:
        query["salary_min"] = {"$gte": min_salary}

    if max_salary:
        query["salary_max"] = {"$lte": max_salary}

    vacancies = await Vacancy.find(query).skip(skip).limit(limit).to_list()
    return vacancies


@router.get(
    "/vacancies/{vacancy_id}/analytics",
    summary="Get vacancy analytics"
)
async def get_vacancy_analytics(vacancy_id: PydanticObjectId):
    """Get analytics for a specific vacancy."""
    vacancy = await Vacancy.get(vacancy_id)
    if not vacancy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vacancy not found"
        )

    return {
        "vacancy_id": str(vacancy.id),
        "views_count": vacancy.views_count,
        "responses_count": vacancy.responses_count,
        "conversion_rate": vacancy.conversion_rate,
        "created_at": vacancy.created_at,
        "published_at": vacancy.published_at,
        "expires_at": vacancy.expires_at,
        "days_active": (datetime.utcnow() - vacancy.created_at).days if vacancy.published_at else 0,
    }
