"""
Cancellation handlers for resume and vacancy creation.
"""

from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from loguru import logger

from backend.models import User


async def handle_cancel_resume(message: Message, state: FSMContext):
    """Handle resume creation cancellation."""
    data = await state.get_data()
    is_first_resume = data.get("first_resume", False)

    await state.clear()

    if is_first_resume:
        # Delete user and return to role selection
        telegram_id = message.from_user.id
        user = await User.find_one(User.telegram_id == telegram_id)
        if user:
            await user.delete()
            logger.info(f"Deleted user {telegram_id} after canceling first resume")

        from bot.keyboards.common import get_role_selection_keyboard
        welcome_text = (
            "👋 <b>Добро пожаловать в CLICK!</b>\n\n"
            "🎯 <b>CLICK</b> — это сервис для поиска работы и сотрудников в сфере HoReCa "
            "(рестораны, бары, кафе, гостиницы).\n\n"
            "Выберите, кто вы:"
        )
        await message.answer(welcome_text, reply_markup=get_role_selection_keyboard())
    else:
        from bot.keyboards.common import get_main_menu_applicant
        await message.answer("❌ Создание резюме отменено.", reply_markup=get_main_menu_applicant())


async def handle_cancel_vacancy(message: Message, state: FSMContext):
    """Handle vacancy creation cancellation."""
    data = await state.get_data()
    is_first_vacancy = data.get("first_vacancy", False)

    await state.clear()

    if is_first_vacancy:
        # Delete user and return to role selection
        telegram_id = message.from_user.id
        user = await User.find_one(User.telegram_id == telegram_id)
        if user:
            await user.delete()
            logger.info(f"Deleted user {telegram_id} after canceling first vacancy")

        from bot.keyboards.common import get_role_selection_keyboard
        welcome_text = (
            "👋 <b>Добро пожаловать в CLICK!</b>\n\n"
            "🎯 <b>CLICK</b> — это сервис для поиска работы и сотрудников в сфере HoReCa "
            "(рестораны, бары, кафе, гостиницы).\n\n"
            "Выберите, кто вы:"
        )
        await message.answer(welcome_text, reply_markup=get_role_selection_keyboard())
    else:
        from bot.keyboards.common import get_main_menu_employer
        await message.answer("❌ Создание вакансии отменено.", reply_markup=get_main_menu_employer())
