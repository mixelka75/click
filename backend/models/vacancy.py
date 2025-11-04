"""
Vacancy model for MongoDB.
"""

from datetime import datetime
from typing import Optional, List
from beanie import Document, Indexed, Link
from pydantic import Field, EmailStr
from shared.constants import VacancyStatus, SalaryType
from .user import User


class Vacancy(Document):
    """Vacancy document model."""

    # Owner (employer)
    user: Link[User]

    # Position information
    position: str
    position_category: str  # From PositionCategory enum
    specialization: Optional[str] = None  # For specific roles
    cuisines: List[str] = Field(default_factory=list)  # For cooks

    # Salary
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    salary_type: SalaryType = Field(default=SalaryType.NET)

    # Employment terms
    employment_type: str  # Полная/частичная занятость и т.д.
    work_schedule: List[str] = Field(default_factory=list)

    # Requirements
    required_experience: str  # Не требуется, от 1 года и т.д.
    required_education: str  # Не имеет значения, среднее и т.д.
    required_skills: List[str] = Field(default_factory=list)

    # Job conditions
    has_employment_contract: bool = Field(default=False)  # Оформление по ТК РФ
    has_probation_period: bool = Field(default=False)
    probation_duration: Optional[str] = None
    allows_remote_work: bool = Field(default=False)

    # Company information
    company_name: str
    company_type: str  # Ресторан, кафе и т.д.
    company_description: Optional[str] = None
    company_size: Optional[str] = None  # Количество сотрудников
    company_website: Optional[str] = None

    # Work location
    city: str
    address: str
    nearest_metro: Optional[str] = None

    # Contact person
    contact_person_name: Optional[str] = None
    contact_person_position: Optional[str] = None
    contact_email: Optional[EmailStr] = None
    contact_phone: Optional[str] = None

    # Benefits
    benefits: List[str] = Field(default_factory=list)

    # Required documents
    required_documents: List[str] = Field(default_factory=list)

    # Job description
    description: Optional[str] = None
    responsibilities: Optional[str] = None

    # Privacy
    is_anonymous: bool = Field(default=False)  # Анонимная вакансия

    # Status
    status: VacancyStatus = Field(default=VacancyStatus.ACTIVE)
    is_published: bool = Field(default=False)

    # Publication settings
    publication_duration_days: Optional[int] = Field(default=30)
    expires_at: Optional[datetime] = None

    # Analytics
    views_count: int = Field(default=0)
    responses_count: int = Field(default=0)
    conversion_rate: float = Field(default=0.0)  # responses/views

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    published_at: Optional[datetime] = None

    class Settings:
        name = "vacancies"
        indexes = [
            "user",
            "position",
            "position_category",
            "city",
            "status",
            "created_at",
            "expires_at",
        ]

    class Config:
        json_schema_extra = {
            "example": {
                "position": "Бармен",
                "position_category": "barman",
                "salary_min": 60000,
                "salary_max": 90000,
                "company_name": "Ресторан Белуга",
                "company_type": "Ресторан",
                "city": "Москва",
                "address": "ул. Пушкина, д. 10",
                "employment_type": "Полная занятость",
                "work_schedule": ["Посменный график"],
                "required_experience": "От 1 года",
            }
        }
