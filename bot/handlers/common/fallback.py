"""
Fallback handlers for navigation buttons when FSM state is lost.
These handlers catch "Back" and "Cancel" buttons when no FSM handler processes them.
"""

from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command
from loguru import logger

from backend.models import User
from shared.constants import UserRole
from bot.keyboards.common import (
    get_main_menu_applicant,
    get_main_menu_employer,
    get_role_selection_keyboard,
)


router = Router(name="fallback")


async def _get_user_menu(telegram_id: int):
    """Get appropriate menu for user based on their role."""
    user = await User.find_one(User.telegram_id == telegram_id)

    if not user:
        return None, None

    current_role = user.current_role or user.role

    if current_role == UserRole.APPLICANT:
        return user, get_main_menu_applicant()
    else:
        return user, get_main_menu_employer()


@router.message(F.text == "🚫 Отменить создание")
async def fallback_cancel_creation(message: Message, state: FSMContext):
    """
    Fallback handler for Cancel button when FSM state is lost.
    Returns user to main menu.
    """
    current_state = await state.get_state()

    logger.warning(
        f"Fallback cancel handler triggered for user {message.from_user.id}, "
        f"current state: {current_state}"
    )

    # Clear any partial state
    await state.clear()

    user, keyboard = await _get_user_menu(message.from_user.id)

    if user and keyboard:
        await message.answer(
            "❌ Действие отменено.\n\n"
            "Похоже, произошёл сбой. Ты вернулся в главное меню.",
            reply_markup=keyboard
        )
    else:
        # User not found - show role selection
        await message.answer(
            "👋 <b>Привет! Я — Клик.</b>\n\n"
            "Похоже, нужно начать сначала.\n"
            "Выбери, кто ты:",
            reply_markup=get_role_selection_keyboard()
        )


@router.message(F.text == "◀️ Назад")
async def fallback_back_button(message: Message, state: FSMContext):
    """
    Fallback handler for Back button when FSM state is lost.
    Returns user to main menu.
    """
    current_state = await state.get_state()

    logger.warning(
        f"Fallback back handler triggered for user {message.from_user.id}, "
        f"current state: {current_state}"
    )

    # Clear any partial state
    await state.clear()

    user, keyboard = await _get_user_menu(message.from_user.id)

    if user and keyboard:
        await message.answer(
            "📋 Ты вернулся в главное меню:",
            reply_markup=keyboard
        )
    else:
        await message.answer(
            "👋 <b>Привет! Я — Клик.</b>\n\n"
            "Выбери, кто ты:",
            reply_markup=get_role_selection_keyboard()
        )


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    """
    /cancel command - cancels current action and returns to menu.
    """
    current_state = await state.get_state()

    if current_state:
        logger.info(f"User {message.from_user.id} cancelled state: {current_state}")

    await state.clear()

    user, keyboard = await _get_user_menu(message.from_user.id)

    if user and keyboard:
        await message.answer(
            "❌ Текущее действие отменено.\n\n"
            "📋 Главное меню:",
            reply_markup=keyboard
        )
    else:
        await message.answer(
            "👋 <b>Привет! Я — Клик.</b>\n\n"
            "Выбери, кто ты:",
            reply_markup=get_role_selection_keyboard()
        )


@router.message(F.text.startswith("⏭"))  # Skip buttons
async def fallback_skip_button(message: Message, state: FSMContext):
    """
    Fallback handler for Skip buttons when FSM state is lost.
    """
    current_state = await state.get_state()

    if not current_state:
        logger.warning(
            f"Skip button pressed without active state by user {message.from_user.id}"
        )

        await state.clear()
        user, keyboard = await _get_user_menu(message.from_user.id)

        if user and keyboard:
            await message.answer(
                "⚠️ Произошёл сбой. Ты вернулся в главное меню:",
                reply_markup=keyboard
            )
        else:
            await message.answer(
                "👋 <b>Привет! Я — Клик.</b>\n\n"
                "Выбери, кто ты:",
                reply_markup=get_role_selection_keyboard()
            )
