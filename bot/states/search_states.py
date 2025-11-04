"""
FSM States for vacancy and resume search.
"""

from aiogram.fsm.state import State, StatesGroup


class VacancySearchStates(StatesGroup):
    """States for searching vacancies (for applicants)."""

    # Search method selection
    select_method = State()

    # Category-based search
    select_category = State()
    select_position = State()

    # Text search
    enter_query = State()

    # Filters
    select_city = State()
    enter_salary_min = State()

    # Results
    view_results = State()
    view_vacancy_details = State()

    # Application
    select_resume = State()
    enter_cover_letter = State()
    confirm_application = State()


class ResumeSearchStates(StatesGroup):
    """States for searching resumes (for employers)."""

    # Search method selection
    select_method = State()

    # Category-based search
    select_category = State()
    select_position = State()

    # Text search
    enter_query = State()

    # Filters
    select_city = State()
    enter_experience = State()

    # Results
    view_results = State()
    view_resume_details = State()

    # Invitation
    select_vacancy = State()
    enter_invitation_message = State()
    confirm_invitation = State()
