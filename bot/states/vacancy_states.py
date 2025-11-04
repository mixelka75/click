"""
FSM States for vacancy creation.
"""

from aiogram.fsm.state import State, StatesGroup


class VacancyCreationStates(StatesGroup):
    """States for creating a vacancy."""

    # Position information
    position_category = State()
    position = State()
    specialization = State()  # For specific roles
    cuisines = State()  # For cooks

    # Salary
    salary_min = State()
    salary_max = State()
    salary_type = State()

    # Employment terms
    employment_type = State()
    work_schedule = State()

    # Requirements
    required_experience = State()
    required_education = State()
    required_skills = State()

    # Job conditions
    has_employment_contract = State()
    has_probation_period = State()
    probation_duration = State()
    allows_remote_work = State()

    # Company information
    company_name = State()
    company_type = State()
    company_description = State()
    company_size = State()
    company_website = State()

    # Work location
    city = State()
    address = State()
    nearest_metro = State()

    # Contact person
    contact_person_name = State()
    contact_person_position = State()
    contact_email = State()
    contact_phone = State()

    # Benefits
    benefits = State()

    # Required documents
    required_documents = State()

    # Job description
    description = State()
    responsibilities = State()

    # Privacy
    is_anonymous = State()

    # Publication settings
    publication_duration_days = State()

    # Preview and publish
    preview = State()
    confirm_publish = State()


class VacancyEditStates(StatesGroup):
    """States for editing existing vacancy."""

    select_vacancy = State()
    select_field = State()
    edit_value = State()
    confirm_changes = State()


class VacancyManagementStates(StatesGroup):
    """States for managing vacancies."""

    select_vacancy = State()
    view_details = State()
    view_responses = State()
    select_response = State()
    response_action = State()
    archive_confirm = State()
