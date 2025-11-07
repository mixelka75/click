"""
Resume endpoints.
"""

from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException, status, Query, Body
from beanie import PydanticObjectId
from pydantic import BaseModel

from backend.models import Resume, User, WorkExperience, Education
from backend.services import telegram_publisher
from shared.constants import ResumeStatus


router = APIRouter()


class ResumeCreateRequest(BaseModel):
    """Request model for creating resume."""
    user_id: str
    full_name: str
    city: str
    phone: str
    desired_position: str
    position_category: str
    ready_to_relocate: Optional[bool] = False
    ready_for_business_trips: Optional[bool] = False
    email: Optional[str] = None
    desired_salary: Optional[int] = None
    salary_type: Optional[str] = None
    work_schedule: Optional[List[str]] = None
    skills: Optional[List[str]] = None
    about: Optional[str] = None
    cuisines: Optional[List[str]] = None
    work_experience: Optional[List[dict]] = None
    education: Optional[List[dict]] = None


@router.post(
    "/resumes",
    response_model=Resume,
    status_code=status.HTTP_201_CREATED,
    summary="Create new resume"
)
async def create_resume(request: ResumeCreateRequest):
    """Create a new resume."""
    # Check if user exists
    user = await User.get(PydanticObjectId(request.user_id))
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    resume_data = request.dict(exclude={"user_id"})

    # Convert work_experience dicts to WorkExperience objects
    if resume_data.get("work_experience"):
        try:
            resume_data["work_experience"] = [
                WorkExperience(**exp) for exp in resume_data["work_experience"]
            ]
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid work experience data: {str(e)}"
            )
    else:
        resume_data["work_experience"] = []

    # Convert education dicts to Education objects
    if resume_data.get("education"):
        try:
            resume_data["education"] = [
                Education(**edu) for edu in resume_data["education"]
            ]
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid education data: {str(e)}"
            )
    else:
        resume_data["education"] = []

    # Ensure all list fields are not None
    list_fields = ["work_schedule", "skills", "cuisines"]
    for field in list_fields:
        if resume_data.get(field) is None:
            if field == "cuisines":
                resume_data.pop(field, None)  # Remove cuisines if None
            else:
                resume_data[field] = []

    # Ensure boolean fields have defaults
    bool_fields = ["ready_to_relocate", "ready_for_business_trips"]
    for field in bool_fields:
        if resume_data.get(field) is None:
            resume_data[field] = False

    try:
        resume = Resume(
            user=user,
            **resume_data
        )
        await resume.insert()
        return resume
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to create resume: {str(e)}"
        )


@router.get(
    "/resumes/{resume_id}",
    response_model=Resume,
    summary="Get resume by ID"
)
async def get_resume(resume_id: PydanticObjectId):
    """Get resume by ID."""
    resume = await Resume.get(resume_id, fetch_links=True)
    if not resume:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resume not found"
        )

    # Increment views count
    resume.views_count += 1
    await resume.save()

    return resume


@router.get(
    "/resumes",
    response_model=List[Resume],
    summary="List resumes with filtering"
)
async def list_resumes(
    position_category: Optional[str] = None,
    city: Optional[str] = None,
    status: Optional[ResumeStatus] = None,
    min_salary: Optional[int] = None,
    max_salary: Optional[int] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100)
):
    """List resumes with optional filtering."""
    query = {}

    if position_category:
        query["position_category"] = position_category
    if city:
        query["city"] = {"$regex": city, "$options": "i"}  # Case-insensitive search
    if status:
        query["status"] = status
    if min_salary:
        query["desired_salary"] = {"$gte": min_salary}
    if max_salary:
        query.setdefault("desired_salary", {})["$lte"] = max_salary

    # Only show active and published resumes
    query["status"] = ResumeStatus.ACTIVE
    query["is_published"] = True

    resumes = await Resume.find(query).skip(skip).limit(limit).to_list()
    return resumes


@router.get(
    "/resumes/user/{user_id}",
    response_model=List[Resume],
    summary="Get all resumes by user"
)
async def get_user_resumes(user_id: PydanticObjectId):
    """Get all resumes created by a specific user."""
    user = await User.get(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    resumes = await Resume.find(Resume.user.id == user_id).to_list()
    return resumes


@router.patch(
    "/resumes/{resume_id}",
    response_model=Resume,
    summary="Update resume"
)
async def update_resume(resume_id: PydanticObjectId, **kwargs):
    """Update resume fields."""
    resume = await Resume.get(resume_id)
    if not resume:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resume not found"
        )

    # Update timestamp
    kwargs["updated_at"] = datetime.utcnow()

    await resume.set(kwargs)
    return resume


@router.patch(
    "/resumes/{resume_id}/publish",
    response_model=Resume,
    summary="Publish resume"
)
async def publish_resume(resume_id: PydanticObjectId):
    """Publish resume (make it visible)."""
    resume = await Resume.get(resume_id, fetch_links=True)
    if not resume:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resume not found"
        )

    resume.is_published = True
    resume.status = ResumeStatus.ACTIVE
    resume.published_at = datetime.utcnow()
    await resume.save()

    # Publish to Telegram channels
    try:
        await telegram_publisher.publish_resume(resume)
    except Exception as e:
        # Log error but don't fail the request
        from loguru import logger
        logger.error(f"Failed to publish resume {resume_id} to Telegram: {e}")

    return resume


@router.patch(
    "/resumes/{resume_id}/archive",
    response_model=Resume,
    summary="Archive resume"
)
async def archive_resume(resume_id: PydanticObjectId):
    """Archive resume (hide from search)."""
    resume = await Resume.get(resume_id)
    if not resume:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resume not found"
        )

    resume.status = ResumeStatus.ARCHIVED
    resume.is_published = False
    await resume.save()

    return resume


@router.delete(
    "/resumes/{resume_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete resume"
)
async def delete_resume(resume_id: PydanticObjectId):
    """Delete resume permanently."""
    resume = await Resume.get(resume_id)
    if not resume:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resume not found"
        )

    await resume.delete()


@router.get(
    "/resumes/search",
    response_model=List[Resume],
    summary="Search resumes with advanced filters"
)
async def search_resumes(
    q: Optional[str] = None,  # Search query
    position: Optional[str] = None,
    category: Optional[str] = None,
    city: Optional[str] = None,
    skills: Optional[str] = None,  # Comma-separated
    experience_years: Optional[int] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100)
):
    """Advanced search for resumes."""
    query = {
        "status": ResumeStatus.ACTIVE,
        "is_published": True
    }

    if q:
        # Full-text search in multiple fields
        query["$or"] = [
            {"full_name": {"$regex": q, "$options": "i"}},
            {"about": {"$regex": q, "$options": "i"}},
            {"desired_position": {"$regex": q, "$options": "i"}},
        ]

    if position:
        query["desired_position"] = {"$regex": position, "$options": "i"}

    if category:
        query["position_category"] = category

    if city:
        query["city"] = {"$regex": city, "$options": "i"}

    if skills:
        skill_list = [s.strip() for s in skills.split(",")]
        query["skills"] = {"$in": skill_list}

    if experience_years:
        query["total_experience_years"] = {"$gte": experience_years}

    resumes = await Resume.find(query).skip(skip).limit(limit).to_list()
    return resumes
