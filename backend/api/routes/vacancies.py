"""
Vacancy endpoints.
"""

from typing import List, Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, status, Query
from beanie import PydanticObjectId
from pydantic import BaseModel

from backend.models import Vacancy, User
from backend.services import telegram_publisher
from shared.constants import VacancyStatus


router = APIRouter()


class VacancyCreateRequest(BaseModel):
    """Request model for creating vacancy."""
    user_id: str
    position: str
    position_category: str
    company_name: str
    company_type: str
    company_description: Optional[str] = None
    company_size: Optional[str] = None
    company_website: Optional[str] = None
    city: str
    address: Optional[str] = None
    nearest_metro: Optional[str] = None
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    salary_type: Optional[str] = None
    employment_type: str
    work_schedule: Optional[List[str]] = None
    required_experience: str
    required_education: str
    required_skills: Optional[List[str]] = None
    has_employment_contract: Optional[bool] = False
    has_probation_period: Optional[bool] = False
    probation_duration: Optional[str] = None  # Format: "1 месяц", "3 месяца"
    allows_remote_work: Optional[bool] = False
    benefits: Optional[List[str]] = None
    required_documents: Optional[List[str]] = None
    description: Optional[str] = None
    responsibilities: Optional[List[str]] = None
    contact_person_name: Optional[str] = None
    contact_person_position: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    is_anonymous: Optional[bool] = False
    publication_duration_days: Optional[int] = 30
    cuisines: Optional[List[str]] = None


@router.post(
    "/vacancies",
    response_model=Vacancy,
    status_code=status.HTTP_201_CREATED,
    summary="Create new vacancy"
)
async def create_vacancy(request: VacancyCreateRequest):
    """Create a new vacancy."""
    # Check if user exists
    user = await User.get(PydanticObjectId(request.user_id))
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    vacancy_data = request.dict(exclude={"user_id"})

    # Set expiration date
    publication_duration = vacancy_data.pop("publication_duration_days", 30)
    expires_at = datetime.utcnow() + timedelta(days=publication_duration)

    # Ensure all list fields are not None
    list_fields = ["work_schedule", "required_skills", "benefits", "required_documents", "responsibilities", "cuisines"]
    for field in list_fields:
        if vacancy_data.get(field) is None:
            if field == "cuisines":
                vacancy_data.pop(field, None)  # Remove cuisines if None
            else:
                vacancy_data[field] = []

    # Ensure boolean fields have defaults
    bool_fields = ["has_employment_contract", "has_probation_period", "allows_remote_work", "is_anonymous"]
    for field in bool_fields:
        if vacancy_data.get(field) is None:
            vacancy_data[field] = False

    try:
        vacancy = Vacancy(
            user=user,
            publication_duration_days=publication_duration,
            expires_at=expires_at,
            **vacancy_data
        )
        await vacancy.insert()
        return vacancy
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to create vacancy: {str(e)}"
        )


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
    """Pause vacancy (temporarily hide from search and remove from channels)."""
    from backend.models import Publication
    from loguru import logger

    vacancy = await Vacancy.get(vacancy_id)
    if not vacancy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vacancy not found"
        )

    vacancy.status = VacancyStatus.PAUSED
    await vacancy.save()

    # Delete all publications from channels
    publications = await Publication.find(
        {"vacancy.$id": vacancy_id},
        Publication.is_published == True,
        Publication.is_deleted == False
    ).to_list()

    for pub in publications:
        try:
            deleted = await telegram_publisher.delete_publication(pub)
            if deleted:
                logger.info(f"Deleted publication {pub.id} from channel {pub.channel_name}")
        except Exception as e:
            logger.error(f"Failed to delete publication {pub.id}: {e}")

    return vacancy


@router.patch(
    "/vacancies/{vacancy_id}/archive",
    response_model=Vacancy,
    summary="Archive vacancy"
)
async def archive_vacancy(vacancy_id: PydanticObjectId):
    """Archive vacancy (hide from search permanently and remove from channels)."""
    from backend.models import Publication
    from loguru import logger

    vacancy = await Vacancy.get(vacancy_id)
    if not vacancy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vacancy not found"
        )

    vacancy.status = VacancyStatus.ARCHIVED
    vacancy.is_published = False
    await vacancy.save()

    # Delete all publications from channels
    publications = await Publication.find(
        {"vacancy.$id": vacancy_id},
        Publication.is_published == True,
        Publication.is_deleted == False
    ).to_list()

    for pub in publications:
        try:
            deleted = await telegram_publisher.delete_publication(pub)
            if deleted:
                logger.info(f"Deleted publication {pub.id} from channel {pub.channel_name}")
        except Exception as e:
            logger.error(f"Failed to delete publication {pub.id}: {e}")

    return vacancy


@router.delete(
    "/vacancies/{vacancy_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete vacancy"
)
async def delete_vacancy(vacancy_id: PydanticObjectId):
    """Delete vacancy permanently and remove from channels."""
    from backend.models import Publication
    from loguru import logger

    vacancy = await Vacancy.get(vacancy_id)
    if not vacancy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vacancy not found"
        )

    # Find and delete all publications for this vacancy
    publications = await Publication.find(
        {"vacancy.$id": vacancy_id},
        Publication.is_published == True,
        Publication.is_deleted == False
    ).to_list()

    for pub in publications:
        try:
            deleted = await telegram_publisher.delete_publication(pub)
            if deleted:
                logger.info(f"Deleted publication {pub.id} from channel {pub.channel_name}")
        except Exception as e:
            logger.error(f"Failed to delete publication {pub.id}: {e}")

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
