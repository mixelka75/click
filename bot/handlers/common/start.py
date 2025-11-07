"""
Start command handler.
"""

from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from loguru import logger

from bot.keyboards.common import get_role_selection_keyboard, get_main_menu_applicant, get_main_menu_employer, get_cancel_keyboard
from backend.models import User
from shared.constants import UserRole
from bot.states.resume_states import ResumeCreationStates
from bot.states.vacancy_states import VacancyCreationStates
from bot.keyboards.positions import get_position_categories_keyboard


router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    """Handle /start command."""
    await state.clear()

    telegram_id = message.from_user.id

    # Check if user exists
    user = await User.find_one(User.telegram_id == telegram_id)

    if user:
        # Existing user - show menu
        logger.info(f"Existing user {telegram_id} started bot")

        if user.role == UserRole.APPLICANT:
            menu_keyboard = get_main_menu_applicant()
            welcome_text = f"👋 С возвращением, {user.first_name or 'друг'}!\n\n" \
                          f"Вы зарегистрированы как <b>Соискатель</b>.\n\n" \
                          f"Выберите действие из меню:"
        else:
            menu_keyboard = get_main_menu_employer()
            welcome_text = f"👋 С возвращением, {user.first_name or 'друг'}!\n\n" \
                          f"Вы зарегистрированы как <b>Работодатель</b>.\n\n" \
                          f"Выберите действие из меню:"

        await message.answer(welcome_text, reply_markup=menu_keyboard)

    else:
        # New user - ask for role
        logger.info(f"New user {telegram_id} started bot")

        welcome_text = (
            "👋 <b>Добро пожаловать в CLICK!</b>\n\n"
            "🎯 <b>CLICK</b> — это сервис для поиска работы и сотрудников в сфере HoReCa "
            "(рестораны, бары, кафе, гостиницы).\n\n"
            "Выберите, кто вы:"
        )

        await message.answer(
            welcome_text,
            reply_markup=get_role_selection_keyboard()
        )


@router.callback_query(F.data.startswith("role:"))
async def select_role(callback: CallbackQuery, state: FSMContext):
    """Handle role selection."""
    await callback.answer()

    role = callback.data.split(":")[1]
    telegram_id = callback.from_user.id

    # Create new user
    user = User(
        telegram_id=telegram_id,
        username=callback.from_user.username,
        first_name=callback.from_user.first_name,
        last_name=callback.from_user.last_name,
        role=UserRole(role),
    )
    await user.insert()

    logger.info(f"Created new user {telegram_id} with role {role}")

    # Show appropriate menu and start creation flow
    if role == "applicant":
        menu_keyboard = get_main_menu_applicant()
        welcome_text = (
            f"✅ Отлично, {user.first_name or 'друг'}!\n\n"
            f"Вы зарегистрированы как <b>Соискатель</b>.\n\n"
            f"Давайте сразу создадим ваше резюме! 📝"
        )

        await callback.message.edit_text(welcome_text)
        await callback.message.answer("Главное меню:", reply_markup=menu_keyboard)

        # Automatically start resume creation
        await state.set_data({"first_resume": True})  # Mark as first resume
        creation_text = (
            "📝 <b>Создание резюме</b>\n\n"
            "Отлично! Давайте создадим ваше резюме.\n"
            "Я буду задавать вам вопросы шаг за шагом.\n\n"
            "Вы можете в любой момент:\n"
            "• Использовать кнопку '🚫 Отменить создание' для отмены\n"
            "• Пропустить необязательные поля\n\n"
            "Начнём с основной информации.\n\n"
            "<b>Как вас зовут?</b> (ФИО полностью)"
        )
        await callback.message.answer(creation_text, reply_markup=get_cancel_keyboard())
        logger.error(f"🚨 start.py: ResumeCreationStates class ID: {id(ResumeCreationStates)}")
        logger.error(f"🚨 start.py: ResumeCreationStates.full_name = {ResumeCreationStates.full_name}")
        await state.set_state(ResumeCreationStates.full_name)
        logger.warning(f"🔥 start.py set state to: {await state.get_state()}")

    else:
        menu_keyboard = get_main_menu_employer()
        welcome_text = (
            f"✅ Отлично, {user.first_name or 'друг'}!\n\n"
            f"Вы зарегистрированы как <b>Работодатель</b>.\n\n"
            f"Давайте сразу создадим вашу первую вакансию! 📝"
        )

        await callback.message.edit_text(welcome_text)
        await callback.message.answer("Главное меню:", reply_markup=menu_keyboard)

        # Automatically start vacancy creation
        await state.set_data({"first_vacancy": True})  # Mark as first vacancy
        creation_text = (
            "📝 <b>Создание вакансии</b>\n\n"
            "Отлично! Давайте создадим вашу вакансию.\n"
            "Я помогу вам заполнить все необходимые поля.\n\n"
            "Вы можете в любой момент использовать кнопку '🚫 Отменить создание'.\n\n"
            "<b>Какую должность вы ищете?</b>\n\nВыберите категорию:"
        )
        await callback.message.answer(
            creation_text,
            reply_markup=get_position_categories_keyboard()
        )
        await state.set_state(VacancyCreationStates.position_category)


@router.message(Command("menu"))
async def cmd_menu(message: Message):
    """Show main menu."""
    telegram_id = message.from_user.id
    user = await User.find_one(User.telegram_id == telegram_id)

    if not user:
        await message.answer("Пожалуйста, начните с команды /start")
        return

    if user.role == UserRole.APPLICANT:
        menu_keyboard = get_main_menu_applicant()
    else:
        menu_keyboard = get_main_menu_employer()

    await message.answer("📋 Главное меню:", reply_markup=menu_keyboard)
