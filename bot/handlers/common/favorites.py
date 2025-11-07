"""
Favorites handlers for both applicants and employers.
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from loguru import logger
import httpx
from typing import Optional

from config.settings import settings

router = Router(name="favorites")


def get_favorites_type_keyboard() -> InlineKeyboardMarkup:
    """Keyboard for selecting favorites type."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="💼 Вакансии", callback_data="favorites:type:vacancies"),
        InlineKeyboardButton(text="📄 Резюме", callback_data="favorites:type:resumes")
    )
    builder.row(
        InlineKeyboardButton(text="📋 Все избранное", callback_data="favorites:type:all")
    )
    return builder.as_markup()


def get_favorite_item_keyboard(
    entity_id: str,
    entity_type: str,
    in_favorites: bool,
    show_back: bool = True
) -> InlineKeyboardMarkup:
    """Get keyboard with favorite button."""
    builder = InlineKeyboardBuilder()

    if in_favorites:
        builder.row(
            InlineKeyboardButton(
                text="⭐ Убрать из избранного",
                callback_data=f"fav:remove:{entity_type}:{entity_id}"
            )
        )
    else:
        builder.row(
            InlineKeyboardButton(
                text="⭐ В избранное",
                callback_data=f"fav:add:{entity_type}:{entity_id}"
            )
        )

    if show_back:
        builder.row(
            InlineKeyboardButton(text="◀️ Назад", callback_data="favorites:menu")
        )

    return builder.as_markup()


async def check_in_favorites(
    telegram_id: int,
    entity_id: str,
    entity_type: str
) -> bool:
    """Check if entity is in favorites."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{settings.api_url}/favorites/check/{entity_id}/{entity_type}",
                params={"user_telegram_id": telegram_id}
            )
            if response.status_code == 200:
                data = response.json()
                return data.get("in_favorites", False)
    except Exception as e:
        logger.error(f"Error checking favorites: {e}")
    return False


async def add_to_favorites(
    telegram_id: int,
    entity_id: str,
    entity_type: str
) -> bool:
    """Add entity to favorites."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{settings.api_url}/favorites",
                params={
                    "user_telegram_id": telegram_id,
                    "entity_id": entity_id,
                    "entity_type": entity_type
                }
            )
            return response.status_code in [200, 201]
    except Exception as e:
        logger.error(f"Error adding to favorites: {e}")
        return False


async def remove_from_favorites(
    telegram_id: int,
    entity_id: str,
    entity_type: str
) -> bool:
    """Remove entity from favorites."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.delete(
                f"{settings.api_url}/favorites/{entity_id}/{entity_type}",
                params={"user_telegram_id": telegram_id}
            )
            return response.status_code == 200
    except Exception as e:
        logger.error(f"Error removing from favorites: {e}")
        return False


async def get_user_favorites(telegram_id: int) -> Optional[dict]:
    """Get user's favorites."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{settings.api_url}/favorites/my",
                params={"user_telegram_id": telegram_id}
            )
            if response.status_code == 200:
                return response.json()
    except Exception as e:
        logger.error(f"Error fetching favorites: {e}")
    return None


def format_vacancy_short(vacancy: dict) -> str:
    """Format vacancy for favorites list."""
    lines = [
        f"💼 <b>{vacancy.get('position', 'Не указано')}</b>",
        f"🏢 {vacancy.get('company_name', 'Не указано')}",
        f"📍 {vacancy.get('city', 'Не указано')}",
    ]

    salary_min = vacancy.get("salary_min")
    salary_max = vacancy.get("salary_max")
    if salary_min and salary_max:
        lines.append(f"💰 {salary_min:,} - {salary_max:,} ₽")
    elif salary_min:
        lines.append(f"💰 От {salary_min:,} ₽")
    elif salary_max:
        lines.append(f"💰 До {salary_max:,} ₽")

    return "\n".join(lines)


def format_resume_short(resume: dict) -> str:
    """Format resume for favorites list."""
    lines = [
        f"📄 <b>{resume.get('full_name', 'Не указано')}</b>",
        f"💼 {resume.get('desired_position', 'Не указано')}",
        f"📍 {resume.get('city', 'Не указано')}",
    ]

    desired_salary = resume.get("desired_salary")
    if desired_salary:
        lines.append(f"💰 Желаемая ЗП: {desired_salary:,} ₽")

    return "\n".join(lines)


@router.message(F.text == "⭐ Избранное")
async def show_favorites_menu(message: Message):
    """Show favorites menu."""
    await message.answer(
        "⭐ <b>Избранное</b>\n\n"
        "Здесь вы можете просмотреть сохраненные вакансии и резюме.",
        reply_markup=get_favorites_type_keyboard()
    )


@router.callback_query(F.data == "favorites:menu")
async def show_favorites_menu_callback(callback: CallbackQuery):
    """Show favorites menu (callback)."""
    await callback.message.edit_text(
        "⭐ <b>Избранное</b>\n\n"
        "Здесь вы можете просмотреть сохраненные вакансии и резюме.",
        reply_markup=get_favorites_type_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "favorites:type:all")
async def show_all_favorites(callback: CallbackQuery):
    """Show all favorites."""
    telegram_id = callback.from_user.id

    favorites = await get_user_favorites(telegram_id)

    if not favorites:
        await callback.message.edit_text(
            "❌ Не удалось загрузить избранное. Попробуйте позже.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="◀️ Назад", callback_data="favorites:menu")
            ]])
        )
        await callback.answer()
        return

    vacancies = favorites.get("vacancies", [])
    resumes = favorites.get("resumes", [])
    total = favorites.get("total", 0)

    if total == 0:
        await callback.message.edit_text(
            "📭 Ваше избранное пусто.\n\n"
            "Добавляйте интересные вакансии и резюме в избранное, "
            "чтобы быстро находить их позже!",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="◀️ Назад", callback_data="favorites:menu")
            ]])
        )
        await callback.answer()
        return

    text = f"⭐ <b>Избранное</b> ({total})\n\n"

    if vacancies:
        text += f"💼 <b>Вакансии ({len(vacancies)}):</b>\n\n"
        for i, vacancy in enumerate(vacancies[:5], 1):  # Show max 5
            text += f"{i}. {format_vacancy_short(vacancy)}\n\n"

        if len(vacancies) > 5:
            text += f"<i>И ещё {len(vacancies) - 5} вакансий...</i>\n\n"

    if resumes:
        text += f"📄 <b>Резюме ({len(resumes)}):</b>\n\n"
        for i, resume in enumerate(resumes[:5], 1):  # Show max 5
            text += f"{i}. {format_resume_short(resume)}\n\n"

        if len(resumes) > 5:
            text += f"<i>И ещё {len(resumes) - 5} резюме...</i>\n\n"

    text += "Для просмотра конкретной категории выберите её из меню."

    await callback.message.edit_text(
        text,
        reply_markup=get_favorites_type_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "favorites:type:vacancies")
async def show_favorite_vacancies(callback: CallbackQuery):
    """Show favorite vacancies."""
    telegram_id = callback.from_user.id

    favorites = await get_user_favorites(telegram_id)

    if not favorites:
        await callback.answer("❌ Ошибка загрузки", show_alert=True)
        return

    vacancies = favorites.get("vacancies", [])

    if not vacancies:
        await callback.message.edit_text(
            "📭 У вас пока нет избранных вакансий.\n\n"
            "Найдите интересные вакансии через поиск и добавьте их в избранное!",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="◀️ Назад", callback_data="favorites:menu")
            ]])
        )
        await callback.answer()
        return

    text = f"💼 <b>Избранные вакансии</b> ({len(vacancies)})\n\n"

    builder = InlineKeyboardBuilder()

    for i, vacancy in enumerate(vacancies, 1):
        vacancy_id = vacancy.get("id")
        position = vacancy.get("position") or "Не указана должность"
        city = vacancy.get("city", "")
        salary_min = vacancy.get("salary_min")
        salary_max = vacancy.get("salary_max")

        salary_str = ""
        if salary_min and salary_max:
            salary_str = f"{salary_min//1000}-{salary_max//1000}к₽"
        elif salary_min:
            salary_str = f"от {salary_min//1000}к₽"
        else:
            salary_str = "не указана"

        button_text = f"{i}. {position} | {salary_str} | {city}"

        builder.row(
            InlineKeyboardButton(
                text=button_text[:64],  # Truncate long text
                callback_data=f"vacancy:view:{vacancy_id}"
            )
        )

    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data="favorites:menu")
    )

    await callback.message.edit_text(
        text + "Выберите вакансию для просмотра:",
        reply_markup=builder.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data == "favorites:type:resumes")
async def show_favorite_resumes(callback: CallbackQuery):
    """Show favorite resumes."""
    telegram_id = callback.from_user.id

    favorites = await get_user_favorites(telegram_id)

    if not favorites:
        await callback.answer("❌ Ошибка загрузки", show_alert=True)
        return

    resumes = favorites.get("resumes", [])

    if not resumes:
        await callback.message.edit_text(
            "📭 У вас пока нет избранных резюме.\n\n"
            "Найдите подходящих кандидатов через поиск и добавьте их резюме в избранное!",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="◀️ Назад", callback_data="favorites:menu")
            ]])
        )
        await callback.answer()
        return

    text = f"📄 <b>Избранные резюме</b> ({len(resumes)})\n\n"

    builder = InlineKeyboardBuilder()

    for i, resume in enumerate(resumes, 1):
        resume_id = resume.get("id")
        position = resume.get("desired_position") or "Не указана должность"
        city = resume.get("city", "")
        salary = resume.get("desired_salary")

        salary_str = f"{salary:,}₽" if salary else "не указана"
        button_text = f"{i}. {position} | {salary_str} | {city}"

        builder.row(
            InlineKeyboardButton(
                text=button_text[:64],  # Truncate long text
                callback_data=f"resume:view:{resume_id}"
            )
        )

    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data="favorites:menu")
    )

    await callback.message.edit_text(
        text + "Выберите резюме для просмотра:",
        reply_markup=builder.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data.startswith("fav:add:"))
async def add_favorite_callback(callback: CallbackQuery):
    """Add entity to favorites."""
    telegram_id = callback.from_user.id

    # Parse callback data: fav:add:vacancy|resume:entity_id
    parts = callback.data.split(":")
    if len(parts) != 4:
        await callback.answer("❌ Ошибка", show_alert=True)
        return

    entity_type = parts[2]
    entity_id = parts[3]

    success = await add_to_favorites(telegram_id, entity_id, entity_type)

    if success:
        await callback.answer("⭐ Добавлено в избранное!", show_alert=False)

        # Update keyboard to show "remove from favorites"
        if callback.message and callback.message.reply_markup:
            # Get current keyboard
            keyboard = callback.message.reply_markup
            new_buttons = []

            for row in keyboard.inline_keyboard:
                new_row = []
                for button in row:
                    if button.callback_data and button.callback_data.startswith("fav:add:"):
                        # Replace add button with remove button
                        new_row.append(InlineKeyboardButton(
                            text="⭐ Убрать из избранного",
                            callback_data=f"fav:remove:{entity_type}:{entity_id}"
                        ))
                    else:
                        new_row.append(button)
                new_buttons.append(new_row)

            try:
                await callback.message.edit_reply_markup(
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=new_buttons)
                )
            except Exception:
                pass  # Message might be too old to edit
    else:
        await callback.answer("❌ Не удалось добавить в избранное", show_alert=True)


@router.callback_query(F.data.startswith("fav:remove:"))
async def remove_favorite_callback(callback: CallbackQuery):
    """Remove entity from favorites."""
    telegram_id = callback.from_user.id

    # Parse callback data: fav:remove:vacancy|resume:entity_id
    parts = callback.data.split(":")
    if len(parts) != 4:
        await callback.answer("❌ Ошибка", show_alert=True)
        return

    entity_type = parts[2]
    entity_id = parts[3]

    success = await remove_from_favorites(telegram_id, entity_id, entity_type)

    if success:
        await callback.answer("Убрано из избранного", show_alert=False)

        # Update keyboard to show "add to favorites"
        if callback.message and callback.message.reply_markup:
            # Get current keyboard
            keyboard = callback.message.reply_markup
            new_buttons = []

            for row in keyboard.inline_keyboard:
                new_row = []
                for button in row:
                    if button.callback_data and button.callback_data.startswith("fav:remove:"):
                        # Replace remove button with add button
                        new_row.append(InlineKeyboardButton(
                            text="⭐ В избранное",
                            callback_data=f"fav:add:{entity_type}:{entity_id}"
                        ))
                    else:
                        new_row.append(button)
                new_buttons.append(new_row)

            try:
                await callback.message.edit_reply_markup(
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=new_buttons)
                )
            except Exception:
                pass  # Message might be too old to edit
    else:
        await callback.answer("❌ Не удалось убрать из избранного", show_alert=True)
