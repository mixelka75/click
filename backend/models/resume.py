"""
Resume model for MongoDB.
"""

from datetime import datetime
from typing import Optional, List
from beanie import Document, Indexed, Link
from pydantic import BaseModel, Field, field_validator
from shared.constants import ResumeStatus, EducationLevel, SalaryType
from .user import User


class WorkExperience(BaseModel):
    """Work experience entry."""
    start_date: Optional[str] = None  # Format: "ММ.ГГГГ" or empty
    end_date: Optional[str] = None  # Format: "ММ.ГГГГ" or "по настоящее время"
    company: str
    position: str
    responsibilities: Optional[str] = None
    industry: Optional[str] = None  # Сфера деятельности компании


class Education(BaseModel):
    """Education entry."""
    level: Optional[str] = None  # Changed to string for flexibility
    institution: str
    faculty: Optional[str] = None
    specialization: Optional[str] = None
    graduation_year: Optional[int] = None


class Course(BaseModel):
    """Training course or certification."""
    name: str
    organization: Optional[str] = None
    completion_year: Optional[int] = None
    certificate_url: Optional[str] = None


class Language(BaseModel):
    """Language proficiency."""
    language: str
    level: str  # A1, A2, B1, B2, C1, C2, Native


class Reference(BaseModel):
    """Professional reference."""
    full_name: str
    position: str
    company: str
    phone: Optional[str] = None
    email: Optional[str] = None


class Resume(Document):
    """Resume document model."""

    # Owner
    user: Link[User]

    # Basic information
    full_name: str
    citizenship: Optional[str] = None
    birth_date: Optional[str] = None  # ISO format YYYY-MM-DD
    city: str
    ready_to_relocate: bool = Field(default=False)
    # DEPRECATED: ready_for_business_trips - kept for backward compatibility
    ready_for_business_trips: bool = Field(default=False)

    # Work format preferences
    prefers_remote: Optional[bool] = None  # Wants to work remotely
    prefers_office: Optional[bool] = None  # Wants to work in office
    prefers_hybrid: Optional[bool] = None  # Wants hybrid format

    # Contact information (for internal use only, not displayed publicly)
    phone: str
    email: Optional[str] = None

    # Photos (NEW: support multiple photos, min 1, max 5)
    photo_file_ids: List[str] = Field(default_factory=list)  # List of Telegram file_ids
    # DEPRECATED: photo_file_id - kept for backward compatibility (first photo)
    photo_file_id: Optional[str] = None  # Telegram file_id for photo

    # Position and salary (NEW: support multiple positions from multiple categories)
    desired_positions: List[str] = Field(default_factory=list)  # ["Бармен", "Официант"]
    position_categories: List[str] = Field(default_factory=list)  # ["barman", "waiter"]
    # DEPRECATED: single position fields - kept for backward compatibility
    desired_position: Optional[str] = None  # First position (deprecated)
    position_category: Optional[str] = None  # First category (deprecated)
    # DEPRECATED: specialization - temporarily removed
    specialization: Optional[str] = None  # For cooks: specific type
    cuisines: List[str] = Field(default_factory=list)  # For cooks only
    desired_salary: Optional[int] = None
    salary_type: SalaryType = Field(default=SalaryType.NET)
    work_schedule: List[str] = Field(default_factory=list)

    # Experience
    work_experience: List[WorkExperience] = Field(default_factory=list)
    total_experience_years: Optional[int] = None

    # Education
    education: List[Education] = Field(default_factory=list)

    # Courses
    courses: List[Course] = Field(default_factory=list)

    # Skills
    skills: List[str] = Field(default_factory=list)

    # Languages
    languages: List[Language] = Field(default_factory=list)

    # About
    about: Optional[str] = None

    # DEPRECATED: References - removed from creation flow, kept for backward compatibility
    references: List[Reference] = Field(default_factory=list)

    # Photo URL (external storage, if used)
    photo_url: Optional[str] = None

    # Status
    status: ResumeStatus = Field(default=ResumeStatus.ACTIVE)
    is_published: bool = Field(default=False)

    # Publication settings
    publication_duration_days: Optional[int] = Field(default=30)
    expires_at: Optional[datetime] = None

    # Analytics
    views_count: int = Field(default=0)
    responses_count: int = Field(default=0)

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    published_at: Optional[datetime] = None

    @field_validator("salary_type", mode="before")
    def _normalize_salary_type(cls, v):
        # Allow None to be converted to default NET
        if v is None:
            return SalaryType.NET
        # If string provided, attempt to map to enum by value or name
        if isinstance(v, str):
            # Try to match by value
            for st in SalaryType:
                if v == st.value or v == st.name:
                    return st
            # Fallback: keep original string to let Pydantic raise if incompatible
            return v
        return v

    class Settings:
        name = "resumes"
        indexes = [
            "user",
            "desired_positions",  # Updated for multi-position
            "position_categories",  # Updated for multi-category
            "city",
            "status",
            "is_published",
            "created_at",
            "published_at",
            [("is_published", 1), ("status", 1)],  # Composite index for filtering active resumes
            [("position_categories", 1), ("is_published", 1)],  # For category-based recommendations
            [("city", 1), ("is_published", 1)],  # For location-based filtering
        ]

    class Config:
        json_schema_extra = {
            "example": {
                "full_name": "Иван Иванов",
                "city": "Москва",
                "phone": "+79001234567",
                "desired_positions": ["Бармен", "Официант"],
                "position_categories": ["barman", "waiter"],
                "desired_salary": 80000,
                "work_schedule": ["Полный день", "Посменный график"],
                "skills": ["Классические коктейли", "Флэр"],
                "photo_file_ids": ["file_id_1", "file_id_2"],
            }
        }

    def migrate_single_to_multi(self) -> None:
        """Migrate old single-value fields to new multi-value fields.
        Call this for backward compatibility with old resumes.
        """
        # Migrate single position to list
        if self.desired_position and not self.desired_positions:
            self.desired_positions = [self.desired_position]

        # Migrate single category to list
        if self.position_category and not self.position_categories:
            self.position_categories = [self.position_category]

        # Migrate single photo to list
        if self.photo_file_id and not self.photo_file_ids:
            self.photo_file_ids = [self.photo_file_id]

    def sync_deprecated_fields(self) -> None:
        """Sync deprecated fields from new multi-value fields.
        Call this before saving to maintain backward compatibility.
        """
        # Sync first position to deprecated field
        if self.desired_positions:
            self.desired_position = self.desired_positions[0]

        # Sync first category to deprecated field
        if self.position_categories:
            self.position_category = self.position_categories[0]

        # Sync first photo to deprecated field
        if self.photo_file_ids:
            self.photo_file_id = self.photo_file_ids[0]

    @property
    def primary_photo(self) -> Optional[str]:
        """Get the primary (first) photo file_id."""
        if self.photo_file_ids:
            return self.photo_file_ids[0]
        return self.photo_file_id

    @property
    def primary_position(self) -> Optional[str]:
        """Get the primary (first) desired position."""
        if self.desired_positions:
            return self.desired_positions[0]
        return self.desired_position

    @property
    def primary_category(self) -> Optional[str]:
        """Get the primary (first) position category."""
        if self.position_categories:
            return self.position_categories[0]
        return self.position_category
