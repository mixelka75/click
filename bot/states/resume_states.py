"""
FSM States for resume creation.
Updated for multi-position selection, required photos, and removed deprecated fields.
"""

from aiogram.fsm.state import State, StatesGroup


class ResumeCreationStates(StatesGroup):
    """States for creating a resume."""

    # === Basic information ===
    full_name = State()
    citizenship = State()
    birth_date = State()
    city = State()              # Button selection (Москва, Питер, Казань, Краснодар)
    city_custom = State()       # NEW: Manual city entry for "Другой город"
    ready_to_relocate = State()
    # REMOVED: ready_for_business_trips

    # === Contact information ===
    phone = State()             # Now accepts both +7 and 8 formats
    email = State()
    telegram_confirm = State()  # Confirm auto-detected telegram
    telegram = State()
    other_contacts = State()

    # === Multiple position selection ===
    position_category = State()         # Select a category
    position = State()                  # Single position selection (legacy)
    positions_in_category = State()     # Multi-select positions within category
    position_more_categories = State()  # "Add more categories?" question
    position_confirm = State()          # Confirm all selected positions
    position_custom = State()           # Custom position entry
    specialization = State()            # For cooks
    cuisines = State()                  # For cooks
    cuisines_custom = State()           # For custom cuisine input

    # === Salary and schedule ===
    desired_salary = State()
    salary_type = State()
    work_schedule = State()

    # === Experience ===
    add_work_experience = State()
    work_experience_company = State()
    work_experience_position = State()
    work_experience_start_date = State()
    work_experience_end_date = State()
    work_experience_responsibilities = State()
    work_experience_industry = State()  # Now: button selection from INDUSTRIES
    work_experience_more = State()

    # === Education ===
    add_education = State()
    education_level = State()
    education_institution = State()
    education_faculty = State()
    education_graduation_year = State()
    education_more = State()

    # === Courses ===
    add_courses = State()
    course_name = State()
    course_organization = State()
    course_year = State()
    course_more = State()

    # === Skills (conditional - only if has relevant experience) ===
    skills = State()
    custom_skills = State()

    # === Languages ===
    add_languages = State()
    language_name = State()
    custom_language_name = State()  # Manual language entry
    language_level = State()
    language_more = State()

    # === About ===
    about = State()

    # REMOVED: References section (6 states)
    # add_references, reference_name, reference_position,
    # reference_company, reference_phone, reference_more

    # === Photos (REQUIRED, 1-5 photos) ===
    photo = State()             # Now: required, minimum 1 photo
    photo_more = State()        # NEW: "Add more photos?" after first one

    # === Preview and publish ===
    preview = State()
    confirm_publish = State()


class ResumeEditStates(StatesGroup):
    """States for editing existing resume."""

    select_resume = State()         # Select which resume to edit
    select_section = State()        # NEW: Select section to edit
    edit_value = State()            # Edit the value
    confirm_changes = State()       # Confirm changes
    more_edits = State()            # NEW: "Edit more?" question


class ResumeManagementStates(StatesGroup):
    """States for resume management (archive, delete, etc.)."""

    select_resume = State()         # Select resume from list
    confirm_action = State()        # Confirm archive/delete
    select_status = State()         # Select new status (active/archive)
