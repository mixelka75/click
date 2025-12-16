"""
Draft models for saving resume/vacancy creation progress.
These are used to restore progress when FSM state is lost.
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from beanie import Document, Indexed
from pydantic import Field


class DraftResume(Document):
    """
    Draft resume for saving creation progress.
    Stores all data collected during resume creation wizard.
    """

    # User identification (telegram_id for faster lookup)
    telegram_id: int = Indexed(unique=True)

    # Current step in the wizard
    current_state: Optional[str] = None

    # Basic information
    full_name: Optional[str] = None
    citizenship: Optional[str] = None
    birth_date: Optional[str] = None
    city: Optional[str] = None
    ready_to_relocate: Optional[bool] = None

    # Contact information
    phone: Optional[str] = None
    email: Optional[str] = None
    telegram_username: Optional[str] = None

    # Position selection (supports multiple)
    selected_positions: List[str] = Field(default_factory=list)
    selected_categories: List[str] = Field(default_factory=list)
    cuisines: List[str] = Field(default_factory=list)

    # Salary and schedule
    desired_salary: Optional[int] = None
    work_schedule: List[str] = Field(default_factory=list)

    # Work experience entries
    work_experience: List[Dict[str, Any]] = Field(default_factory=list)

    # Temporary work experience (being entered)
    temp_company: Optional[str] = None
    temp_position: Optional[str] = None
    temp_start_date: Optional[str] = None
    temp_end_date: Optional[str] = None
    temp_responsibilities: Optional[str] = None

    # Education entries
    education: List[Dict[str, Any]] = Field(default_factory=list)

    # Temporary education (being entered)
    temp_education_level: Optional[str] = None
    temp_education_institution: Optional[str] = None
    temp_education_faculty: Optional[str] = None

    # Courses
    courses: List[Dict[str, Any]] = Field(default_factory=list)

    # Skills
    skills: List[str] = Field(default_factory=list)

    # Languages
    languages: List[Dict[str, Any]] = Field(default_factory=list)

    # About
    about: Optional[str] = None

    # Photos
    photo_file_ids: List[str] = Field(default_factory=list)

    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Is this the user's first resume (affects cancel behavior)
    is_first_resume: bool = False

    class Settings:
        name = "draft_resumes"
        use_state_management = True

    async def update_from_fsm_data(self, data: Dict[str, Any]) -> None:
        """Update draft from FSM state data."""
        # Map FSM data keys to model fields
        field_mapping = {
            "full_name": "full_name",
            "citizenship": "citizenship",
            "birth_date": "birth_date",
            "city": "city",
            "ready_to_relocate": "ready_to_relocate",
            "phone": "phone",
            "email": "email",
            "detected_telegram": "telegram_username",
            "selected_positions": "selected_positions",
            "selected_categories": "selected_categories",
            "desired_positions": "selected_positions",
            "position_categories": "selected_categories",
            "cuisines": "cuisines",
            "desired_salary": "desired_salary",
            "work_schedule": "work_schedule",
            "work_experience": "work_experience",
            "education": "education",
            "courses": "courses",
            "skills": "skills",
            "languages": "languages",
            "about": "about",
            "photo_file_ids": "photo_file_ids",
            "first_resume": "is_first_resume",
            # Temp fields
            "temp_company": "temp_company",
            "temp_position": "temp_position",
            "temp_start_date": "temp_start_date",
            "temp_end_date": "temp_end_date",
            "temp_responsibilities": "temp_responsibilities",
            "temp_education_level": "temp_education_level",
            "temp_education_institution": "temp_education_institution",
            "temp_education_faculty": "temp_education_faculty",
        }

        for fsm_key, model_field in field_mapping.items():
            if fsm_key in data and data[fsm_key] is not None:
                setattr(self, model_field, data[fsm_key])

        self.updated_at = datetime.utcnow()

    def to_fsm_data(self) -> Dict[str, Any]:
        """Convert draft to FSM state data format."""
        data = {}

        if self.full_name:
            data["full_name"] = self.full_name
        if self.citizenship:
            data["citizenship"] = self.citizenship
        if self.birth_date:
            data["birth_date"] = self.birth_date
        if self.city:
            data["city"] = self.city
        if self.ready_to_relocate is not None:
            data["ready_to_relocate"] = self.ready_to_relocate
        if self.phone:
            data["phone"] = self.phone
        if self.email:
            data["email"] = self.email
        if self.telegram_username:
            data["detected_telegram"] = self.telegram_username
        if self.selected_positions:
            data["selected_positions"] = self.selected_positions
            data["desired_positions"] = self.selected_positions
        if self.selected_categories:
            data["selected_categories"] = self.selected_categories
            data["position_categories"] = self.selected_categories
        if self.cuisines:
            data["cuisines"] = self.cuisines
        if self.desired_salary is not None:
            data["desired_salary"] = self.desired_salary
        if self.work_schedule:
            data["work_schedule"] = self.work_schedule
        if self.work_experience:
            data["work_experience"] = self.work_experience
        if self.education:
            data["education"] = self.education
        if self.courses:
            data["courses"] = self.courses
        if self.skills:
            data["skills"] = self.skills
        if self.languages:
            data["languages"] = self.languages
        if self.about:
            data["about"] = self.about
        if self.photo_file_ids:
            data["photo_file_ids"] = self.photo_file_ids
        if self.is_first_resume:
            data["first_resume"] = self.is_first_resume

        return data


class DraftVacancy(Document):
    """
    Draft vacancy for saving creation progress.
    Stores all data collected during vacancy creation wizard.
    """

    # User identification
    telegram_id: int = Indexed(unique=True)

    # Current step in the wizard
    current_state: Optional[str] = None

    # Position
    position: Optional[str] = None
    position_category: Optional[str] = None

    # Company info
    company_name: Optional[str] = None
    company_type: Optional[str] = None
    company_description: Optional[str] = None
    company_size: Optional[str] = None
    company_website: Optional[str] = None

    # Location
    city: Optional[str] = None
    metro_stations: List[str] = Field(default_factory=list)

    # Salary
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None

    # Requirements
    requirements: Optional[str] = None
    experience_required: Optional[str] = None

    # Conditions
    work_schedule: List[str] = Field(default_factory=list)
    employment_type: Optional[str] = None
    benefits: List[str] = Field(default_factory=list)

    # Description
    description: Optional[str] = None

    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Is this the user's first vacancy
    is_first_vacancy: bool = False

    class Settings:
        name = "draft_vacancies"
        use_state_management = True

    async def update_from_fsm_data(self, data: Dict[str, Any]) -> None:
        """Update draft from FSM state data."""
        field_mapping = {
            "position": "position",
            "position_category": "position_category",
            "company_name": "company_name",
            "company_type": "company_type",
            "company_description": "company_description",
            "company_size": "company_size",
            "company_website": "company_website",
            "city": "city",
            "metro_stations": "metro_stations",
            "salary_min": "salary_min",
            "salary_max": "salary_max",
            "requirements": "requirements",
            "experience_required": "experience_required",
            "work_schedule": "work_schedule",
            "employment_type": "employment_type",
            "benefits": "benefits",
            "description": "description",
            "first_vacancy": "is_first_vacancy",
        }

        for fsm_key, model_field in field_mapping.items():
            if fsm_key in data and data[fsm_key] is not None:
                setattr(self, model_field, data[fsm_key])

        self.updated_at = datetime.utcnow()

    def to_fsm_data(self) -> Dict[str, Any]:
        """Convert draft to FSM state data format."""
        data = {}

        if self.position:
            data["position"] = self.position
        if self.position_category:
            data["position_category"] = self.position_category
        if self.company_name:
            data["company_name"] = self.company_name
        if self.company_type:
            data["company_type"] = self.company_type
        if self.company_description:
            data["company_description"] = self.company_description
        if self.company_size:
            data["company_size"] = self.company_size
        if self.company_website:
            data["company_website"] = self.company_website
        if self.city:
            data["city"] = self.city
        if self.metro_stations:
            data["metro_stations"] = self.metro_stations
        if self.salary_min is not None:
            data["salary_min"] = self.salary_min
        if self.salary_max is not None:
            data["salary_max"] = self.salary_max
        if self.requirements:
            data["requirements"] = self.requirements
        if self.experience_required:
            data["experience_required"] = self.experience_required
        if self.work_schedule:
            data["work_schedule"] = self.work_schedule
        if self.employment_type:
            data["employment_type"] = self.employment_type
        if self.benefits:
            data["benefits"] = self.benefits
        if self.description:
            data["description"] = self.description
        if self.is_first_vacancy:
            data["first_vacancy"] = self.is_first_vacancy

        return data


# Helper functions for progress saving

async def save_resume_progress(
    telegram_id: int,
    state_name: str,
    fsm_data: Dict[str, Any]
) -> DraftResume:
    """
    Save or update resume creation progress.

    Args:
        telegram_id: User's Telegram ID
        state_name: Current FSM state name
        fsm_data: Current FSM state data

    Returns:
        Updated DraftResume document
    """
    # Try to find existing draft
    draft = await DraftResume.find_one(DraftResume.telegram_id == telegram_id)

    if not draft:
        draft = DraftResume(telegram_id=telegram_id)

    draft.current_state = state_name
    await draft.update_from_fsm_data(fsm_data)
    await draft.save()

    return draft


async def get_resume_progress(telegram_id: int) -> Optional[DraftResume]:
    """
    Get saved resume creation progress.

    Args:
        telegram_id: User's Telegram ID

    Returns:
        DraftResume if exists, None otherwise
    """
    return await DraftResume.find_one(DraftResume.telegram_id == telegram_id)


async def delete_resume_progress(telegram_id: int) -> bool:
    """
    Delete resume creation progress (after successful publication or cancel).

    Args:
        telegram_id: User's Telegram ID

    Returns:
        True if deleted, False if not found
    """
    draft = await DraftResume.find_one(DraftResume.telegram_id == telegram_id)
    if draft:
        await draft.delete()
        return True
    return False


async def save_vacancy_progress(
    telegram_id: int,
    state_name: str,
    fsm_data: Dict[str, Any]
) -> DraftVacancy:
    """Save or update vacancy creation progress."""
    draft = await DraftVacancy.find_one(DraftVacancy.telegram_id == telegram_id)

    if not draft:
        draft = DraftVacancy(telegram_id=telegram_id)

    draft.current_state = state_name
    await draft.update_from_fsm_data(fsm_data)
    await draft.save()

    return draft


async def get_vacancy_progress(telegram_id: int) -> Optional[DraftVacancy]:
    """Get saved vacancy creation progress."""
    return await DraftVacancy.find_one(DraftVacancy.telegram_id == telegram_id)


async def delete_vacancy_progress(telegram_id: int) -> bool:
    """Delete vacancy creation progress."""
    draft = await DraftVacancy.find_one(DraftVacancy.telegram_id == telegram_id)
    if draft:
        await draft.delete()
        return True
    return False
