"""
Start command handler.
"""

from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from loguru import logger

from bot.keyboards.common import get_role_selection_keyboard, get_main_menu_applicant, get_main_menu_employer
from backend.models import User
from shared.constants import UserRole


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

    # Show appropriate menu
    if role == "applicant":
        menu_keyboard = get_main_menu_applicant()
        welcome_text = (
            f"✅ Отлично, {user.first_name or 'друг'}!\n\n"
            f"Вы зарегистрированы как <b>Соискатель</b>.\n\n"
            f"Теперь вы можете:\n"
            f"📝 Создать резюме\n"
            f"🔍 Искать вакансии\n"
            f"📬 Откликаться на вакансии\n\n"
            f"Выберите действие из меню:"
        )
    else:
        menu_keyboard = get_main_menu_employer()
        welcome_text = (
            f"✅ Отлично, {user.first_name or 'друг'}!\n\n"
            f"Вы зарегистрированы как <b>Работодатель</b>.\n\n"
            f"Теперь вы можете:\n"
            f"📝 Создавать вакансии\n"
            f"🔍 Искать резюме\n"
            f"📬 Получать отклики\n\n"
            f"Выберите действие из меню:"
        )

    await callback.message.edit_text(welcome_text)
    await callback.message.answer("Главное меню:", reply_markup=menu_keyboard)


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
