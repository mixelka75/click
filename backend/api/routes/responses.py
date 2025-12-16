"""
Response (отклик) endpoints.
"""

from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException, status, Query
from beanie import PydanticObjectId
from pydantic import BaseModel
from loguru import logger

from backend.models import Response, User, Resume, Vacancy
from backend.services.notification_service import notification_service
from shared.constants import ResponseStatus


router = APIRouter()


@router.post(
    "/responses",
    response_model=Response,
    status_code=status.HTTP_201_CREATED,
    summary="Create new response (applicant responds to vacancy)"
)
async def create_response(
    applicant_id: PydanticObjectId,
    vacancy_id: PydanticObjectId,
    resume_id: PydanticObjectId,
    message: Optional[str] = None
):
    """Create a new response from applicant to vacancy."""
    # Validate all entities exist
    applicant = await User.get(applicant_id)
    if not applicant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Applicant not found"
        )

    vacancy = await Vacancy.get(vacancy_id, fetch_links=True)
    if not vacancy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vacancy not found"
        )

    resume = await Resume.get(resume_id)
    if not resume:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resume not found"
        )

    # Check if response already exists
    existing_response = await Response.find_one(
        Response.applicant.id == applicant_id,
        Response.vacancy.id == vacancy_id,
        Response.resume.id == resume_id
    )
    if existing_response:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You have already responded to this vacancy with this resume"
        )

    # Create response
    response = Response(
        applicant=applicant,
        employer=vacancy.user,
        resume=resume,
        vacancy=vacancy,
        message=message,
        is_invitation=False
    )
    await response.insert()

    # Update vacancy response count
    vacancy.responses_count += 1
    if vacancy.views_count > 0:
        vacancy.conversion_rate = vacancy.responses_count / vacancy.views_count
    await vacancy.save()

    # Send notification to employer (non-blocking)
    try:
        import asyncio
        asyncio.create_task(notification_service.notify_new_response(response))
    except Exception as e:
        logger.error(f"Failed to send notification: {e}")

    return response


class InvitationRequest(BaseModel):
    """Request model for creating invitation."""
    employer_id: str
    applicant_id: str
    vacancy_id: str
    resume_id: str
    invitation_message: Optional[str] = None


@router.post(
    "/responses/invitation",
    response_model=Response,
    status_code=status.HTTP_201_CREATED,
    summary="Create invitation (employer invites applicant)"
)
async def create_invitation(request: InvitationRequest):
    """Create an invitation from employer to applicant."""
    # Validate all entities exist
    employer = await User.get(PydanticObjectId(request.employer_id))
    if not employer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employer not found"
        )

    applicant = await User.get(PydanticObjectId(request.applicant_id))
    if not applicant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Applicant not found"
        )

    vacancy = await Vacancy.get(PydanticObjectId(request.vacancy_id))
    if not vacancy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vacancy not found"
        )

    resume = await Resume.get(PydanticObjectId(request.resume_id))
    if not resume:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resume not found"
        )

    # Check if invitation already exists
    existing = await Response.find_one(
        Response.employer.id == employer.id,
        Response.applicant.id == applicant.id,
        Response.vacancy.id == vacancy.id,
        Response.resume.id == resume.id,
        Response.is_invitation == True
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Вы уже приглашали этого кандидата на эту вакансию"
        )

    # Create invitation
    response = Response(
        applicant=applicant,
        employer=employer,
        resume=resume,
        vacancy=vacancy,
        message=request.invitation_message,
        is_invitation=True,
        status=ResponseStatus.INVITED
    )
    await response.insert()

    # Send notification to applicant (non-blocking)
    try:
        import asyncio
        asyncio.create_task(notification_service.notify_new_invitation(response))
    except Exception as e:
        logger.error(f"Failed to send notification: {e}")

    return response


@router.get(
    "/responses/{response_id}",
    response_model=Response,
    summary="Get response by ID"
)
async def get_response(response_id: PydanticObjectId):
    """Get response by ID."""
    response = await Response.get(response_id, fetch_links=True)
    if not response:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Response not found"
        )

    # Mark as viewed if not yet viewed
    if not response.viewed_at:
        response.viewed_at = datetime.utcnow()
        response.status = ResponseStatus.VIEWED
        await response.save()

    return response


@router.get(
    "/responses/vacancy/{vacancy_id}",
    response_model=List[Response],
    summary="Get all responses to a vacancy"
)
async def get_vacancy_responses(
    vacancy_id: PydanticObjectId,
    status: Optional[ResponseStatus] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100)
):
    """Get all responses to a specific vacancy."""
    vacancy = await Vacancy.get(vacancy_id)
    if not vacancy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vacancy not found"
        )

    # Use Beanie's attribute-based query for Link references
    if status:
        responses = await Response.find(
            Response.vacancy.id == vacancy_id,
            Response.status == status,
            fetch_links=True
        ).skip(skip).limit(limit).to_list()
    else:
        responses = await Response.find(
            Response.vacancy.id == vacancy_id,
            fetch_links=True
        ).skip(skip).limit(limit).to_list()
    return responses


@router.get(
    "/responses/applicant/{applicant_id}",
    response_model=List[Response],
    summary="Get all responses by applicant"
)
async def get_applicant_responses(
    applicant_id: PydanticObjectId,
    status: Optional[ResponseStatus] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100)
):
    """Get all responses created by a specific applicant."""
    applicant = await User.get(applicant_id)
    if not applicant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Applicant not found"
        )

    # Use Beanie's attribute-based query for Link references
    if status:
        responses = await Response.find(
            Response.applicant.id == applicant_id,
            Response.status == status,
            fetch_links=True
        ).skip(skip).limit(limit).to_list()
    else:
        responses = await Response.find(
            Response.applicant.id == applicant_id,
            fetch_links=True
        ).skip(skip).limit(limit).to_list()
    return responses


@router.patch(
    "/responses/{response_id}/status",
    response_model=Response,
    summary="Update response status"
)
async def update_response_status(
    response_id: PydanticObjectId,
    status: str,  # Changed from new_status to match request body
    rejection_reason: Optional[str] = None,
    interview_date: Optional[datetime] = None,
    interview_location: Optional[str] = None
):
    """Update response status (invite, accept, reject, etc.)."""
    response = await Response.get(response_id, fetch_links=True)
    if not response:
        raise HTTPException(
            status_code=404,
            detail="Response not found"
        )

    old_status = response.status
    new_status = ResponseStatus(status) if isinstance(status, str) else status

    response.status = new_status
    response.updated_at = datetime.utcnow()
    response.responded_at = datetime.utcnow()

    if new_status == ResponseStatus.REJECTED and rejection_reason:
        response.rejection_reason = rejection_reason

    if new_status == ResponseStatus.INVITED:
        if interview_date:
            response.interview_date = interview_date
        if interview_location:
            response.interview_location = interview_location

    await response.save()

    # Send notification to applicant (non-blocking)
    try:
        import asyncio
        asyncio.create_task(
            notification_service.notify_response_status_changed(response, old_status)
        )
    except Exception as e:
        logger.error(f"Failed to send notification: {e}")

    return response


@router.delete(
    "/responses/{response_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete response"
)
async def delete_response(response_id: PydanticObjectId):
    """Delete response permanently."""
    response = await Response.get(response_id)
    if not response:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Response not found"
        )

    await response.delete()


@router.get(
    "/responses/employer/{employer_id}",
    response_model=List[Response],
    summary="Get all responses for employer's vacancies"
)
async def get_employer_responses(
    employer_id: PydanticObjectId,
    status: Optional[ResponseStatus] = None,
    vacancy_id: Optional[PydanticObjectId] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100)
):
    """Get all responses to all vacancies of an employer."""
    employer = await User.get(employer_id)
    if not employer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employer not found"
        )

    # Use Beanie's attribute-based query for Link references
    conditions = [Response.employer.id == employer_id]
    if status:
        conditions.append(Response.status == status)
    if vacancy_id:
        conditions.append(Response.vacancy.id == vacancy_id)

    responses = await Response.find(*conditions, fetch_links=True).skip(skip).limit(limit).to_list()
    return responses
