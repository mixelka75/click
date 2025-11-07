"""
FSM States for resume creation.
"""

from aiogram.fsm.state import State, StatesGroup


class ResumeCreationStates(StatesGroup):
    """States for creating a resume."""

    # Basic information
    full_name = State()
    citizenship = State()
    birth_date = State()
    city = State()
    ready_to_relocate = State()
    ready_for_business_trips = State()

    # Contact information
    phone = State()
    email = State()
    telegram = State()
    other_contacts = State()

    # Position and salary
    position_category = State()
    position = State()
    position_custom = State()
    specialization = State()  # For cooks
    cuisines = State()  # For cooks
    desired_salary = State()
    salary_type = State()
    work_schedule = State()

    # Experience
    add_work_experience = State()
    work_experience_start_date = State()
    work_experience_end_date = State()
    work_experience_company = State()
    work_experience_position = State()
    work_experience_responsibilities = State()
    work_experience_industry = State()
    work_experience_more = State()

    # Education
    add_education = State()
    education_level = State()
    education_institution = State()
    education_faculty = State()
    education_graduation_year = State()
    education_more = State()

    # Courses
    add_courses = State()
    course_name = State()
    course_organization = State()
    course_year = State()
    course_more = State()

    # Skills
    skills = State()
    custom_skills = State()

    # Languages
    add_languages = State()
    language_name = State()
    language_level = State()
    language_more = State()

    # About
    about = State()

    # References
    add_references = State()
    reference_name = State()
    reference_position = State()
    reference_company = State()
    reference_phone = State()
    reference_more = State()

    # Photo
    photo = State()

    # Preview and publish
    preview = State()
    confirm_publish = State()


class ResumeEditStates(StatesGroup):
    """States for editing existing resume."""

    select_resume = State()
    select_field = State()
    edit_value = State()
    confirm_changes = State()
