"""
Start command handler with dual-role support and personal cabinet.
"""

from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from loguru import logger

from bot.keyboards.common import (
    get_role_selection_keyboard,
    get_main_menu_applicant,
    get_main_menu_employer,
    get_cancel_keyboard,
    get_dual_role_selection_keyboard,
    get_personal_cabinet_keyboard,
)
from backend.models import User, Resume, Vacancy
from shared.constants import UserRole
from bot.states.resume_states import ResumeCreationStates
from bot.states.vacancy_states import VacancyCreationStates
from bot.states.search_states import ChannelInviteStates, ChannelApplyStates
from bot.keyboards.positions import get_position_categories_keyboard
from aiogram.utils.keyboard import InlineKeyboardBuilder
import httpx
from beanie import PydanticObjectId
from config.settings import settings


router = Router()


async def get_user_statistics(user: User) -> dict:
    """Get user statistics for personal cabinet."""
    stats = {
        "resumes_count": 0,
        "vacancies_count": 0,
        "total_views": 0,
        "total_responses": 0,
    }

    if user.has_role(UserRole.APPLICANT):
        resumes = await Resume.find({"user.$id": user.id}).to_list()
        stats["resumes_count"] = len(resumes)
        stats["total_views"] = sum(r.views_count for r in resumes)
        stats["total_responses"] = sum(r.responses_count for r in resumes)

    if user.has_role(UserRole.EMPLOYER):
        vacancies = await Vacancy.find({"user.$id": user.id}).to_list()
        stats["vacancies_count"] = len(vacancies)
        stats["total_views"] += sum(v.views_count for v in vacancies)
        stats["total_responses"] += sum(v.responses_count for v in vacancies)

    return stats


async def get_user_photo(user: User) -> str | None:
    """Get user's photo file_id from their resume."""
    resume = await Resume.find_one(
        {"user.$id": user.id, "is_published": True},
        sort=[("created_at", -1)]
    )
    if resume and resume.photo_file_ids:
        return resume.photo_file_ids[0]
    elif resume and resume.photo_file_id:
        return resume.photo_file_id
    return None


async def show_personal_cabinet(message: Message, user: User, is_edit: bool = False):
    """Show personal cabinet with photo and statistics."""
    stats = await get_user_statistics(user)
    photo_file_id = await get_user_photo(user)

    # Determine current role display
    current_role = user.current_role or user.role
    role_name = "Соискатель" if current_role == UserRole.APPLICANT else "Работодатель"
    role_emoji = "👤" if current_role == UserRole.APPLICANT else "💼"

    # Build cabinet text
    cabinet_text = (
        f"👋 <b>С возвращением, {user.first_name or 'друг'}!</b>\n\n"
        f"{role_emoji} Роль: <b>{role_name}</b>\n"
    )

    if user.is_dual_role():
        cabinet_text += "🔄 <i>У тебя двойная роль - можешь переключаться</i>\n"

    cabinet_text += "\n📊 <b>Твоя статистика:</b>\n"

    if user.has_role(UserRole.APPLICANT):
        cabinet_text += f"📝 Резюме: {stats['resumes_count']}\n"

    if user.has_role(UserRole.EMPLOYER):
        cabinet_text += f"📋 Вакансий: {stats['vacancies_count']}\n"

    cabinet_text += (
        f"👁 Просмотров: {stats['total_views']}\n"
        f"📬 Откликов: {stats['total_responses']}\n"
    )

    keyboard = get_personal_cabinet_keyboard(
        user_has_dual_role=user.is_dual_role(),
        current_role=current_role.value
    )

    # Send with photo if available
    if photo_file_id and not is_edit:
        try:
            await message.answer_photo(
                photo=photo_file_id,
                caption=cabinet_text,
                reply_markup=keyboard
            )
        except Exception as e:
            logger.warning(f"Failed to send photo: {e}")
            await message.answer(cabinet_text, reply_markup=keyboard)
    else:
        if is_edit and hasattr(message, 'edit_text'):
            await message.edit_text(cabinet_text, reply_markup=keyboard)
        else:
            await message.answer(cabinet_text, reply_markup=keyboard)


async def show_menu_for_role(message: Message, user: User):
    """Show appropriate menu based on user's current role."""
    current_role = user.current_role or user.role

    if current_role == UserRole.APPLICANT:
        menu_keyboard = get_main_menu_applicant()
    else:
        menu_keyboard = get_main_menu_employer()

    await message.answer("📋 Главное меню:", reply_markup=menu_keyboard)


async def handle_deep_link(message: Message, state: FSMContext, user: User, param: str):
    """Handle deep link from channel publication."""
    from bot.handlers.common.complaint import handle_report_deep_link

    try:
        # Parse param: format is "resume_ID", "vacancy_ID", "report_vacancy_ID", "report_resume_ID"
        parts = param.split("_", 1)
        if len(parts) != 2:
            await message.answer("❌ Неверная ссылка. Попробуй еще раз.")
            return

        entity_type, entity_id = parts

        # Handle complaint deep links
        if entity_type == "report":
            # Further parse: entity_id contains "vacancy_ID" or "resume_ID"
            report_parts = entity_id.split("_", 1)
            if len(report_parts) != 2:
                await message.answer("❌ Неверная ссылка жалобы.")
                return
            target_type, target_id = report_parts
            await handle_report_deep_link(message, state, target_type, target_id)
            return

        if entity_type == "resume":
            # Employer clicked "Пригласить" on resume
            if not user.has_role(UserRole.EMPLOYER):
                await message.answer(
                    "❌ Эта функция доступна только работодателям.\n"
                    "Пожалуйста, зарегистрируйся как работодатель."
                )
                return

            # Set current role to employer for this action
            user.current_role = UserRole.EMPLOYER
            await user.save()

            await handle_resume_invite(message, state, user, entity_id)

        elif entity_type == "vacancy":
            # Applicant clicked "Откликнуться" on vacancy
            if not user.has_role(UserRole.APPLICANT):
                await message.answer(
                    "❌ Эта функция доступна только соискателям.\n"
                    "Пожалуйста, зарегистрируйся как соискатель."
                )
                return

            # Set current role to applicant for this action
            user.current_role = UserRole.APPLICANT
            await user.save()

            await handle_vacancy_apply(message, state, user, entity_id)

        else:
            await message.answer("❌ Неверный тип ссылки.")

    except Exception as e:
        logger.error(f"Error handling deep link: {e}")
        await message.answer("❌ Произошла ошибка. Попробуй позже.")


async def handle_resume_invite(message: Message, state: FSMContext, user: User, resume_id: str):
    """Handle employer inviting candidate from channel."""
    from backend.models import Resume, Vacancy

    try:
        # Get resume
        resume = await Resume.get(PydanticObjectId(resume_id))
        if not resume:
            await message.answer(
                "❌ Резюме не найдено или было удалено.",
                reply_markup=get_main_menu_employer()
            )
            return

        # Fetch applicant user
        await resume.fetch_link(Resume.user)
        applicant_user = resume.user
        if not applicant_user:
            await message.answer(
                "❌ Информация о кандидате недоступна.",
                reply_markup=get_main_menu_employer()
            )
            return

        # Get employer's active vacancies
        vacancies = await Vacancy.find(
            Vacancy.user.id == user.id,
            Vacancy.status == "active"
        ).to_list()

        if not vacancies:
            await message.answer(
                "❌ <b>Нет активных вакансий</b>\n\n"
                "Создайте и опубликуйте вакансию, чтобы приглашать кандидатов.",
                reply_markup=get_main_menu_employer()
            )
            return

        # Save data to state
        await state.update_data(
            invite_resume_id=resume_id,
            invite_applicant_id=str(applicant_user.id),
            invite_applicant_telegram_id=applicant_user.telegram_id,
            invite_resume_name=resume.full_name,
            invite_resume_position=resume.desired_position
        )

        # Show resume info and vacancy selection
        text = (
            f"👤 <b>Приглашение кандидата</b>\n\n"
            f"<b>Кандидат:</b> {resume.full_name}\n"
            f"<b>Должность:</b> {resume.desired_position}\n"
        )
        if resume.city:
            text += f"<b>Город:</b> {resume.city}\n"
        if resume.desired_salary:
            text += f"<b>Желаемая ЗП:</b> {resume.desired_salary:,} ₽\n"

        text += "\n<b>На какую вакансию приглашаете?</b>"

        # Build vacancy selection keyboard
        builder = InlineKeyboardBuilder()
        for vacancy in vacancies:
            salary_text = ""
            if vacancy.salary_min or vacancy.salary_max:
                if vacancy.salary_min and vacancy.salary_max:
                    salary_text = f" ({vacancy.salary_min:,}-{vacancy.salary_max:,}₽)"
                elif vacancy.salary_min:
                    salary_text = f" (от {vacancy.salary_min:,}₽)"
                else:
                    salary_text = f" (до {vacancy.salary_max:,}₽)"

            builder.row(InlineKeyboardButton(
                text=f"💼 {vacancy.position}{salary_text}",
                callback_data=f"ch_invite_vac:{vacancy.id}"
            ))

        builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="ch_invite_cancel"))

        await message.answer(text, reply_markup=builder.as_markup())
        await state.set_state(ChannelInviteStates.select_vacancy)

    except Exception as e:
        logger.error(f"Error in handle_resume_invite: {e}")
        await message.answer(
            "❌ Произошла ошибка при обработке приглашения. Попробуйте позже.",
            reply_markup=get_main_menu_employer()
        )


async def handle_vacancy_apply(message: Message, state: FSMContext, user: User, vacancy_id: str):
    """Handle applicant applying to vacancy from channel."""
    from backend.models import Resume, Vacancy

    try:
        # Get vacancy
        vacancy = await Vacancy.get(PydanticObjectId(vacancy_id))
        if not vacancy:
            await message.answer(
                "❌ Вакансия не найдена или была удалена.",
                reply_markup=get_main_menu_applicant()
            )
            return

        # Fetch employer user
        await vacancy.fetch_link(Vacancy.user)
        employer_user = vacancy.user
        if not employer_user:
            await message.answer(
                "❌ Информация о работодателе недоступна.",
                reply_markup=get_main_menu_applicant()
            )
            return

        # Get applicant's published resumes
        all_resumes = await Resume.find({"user.$id": user.id}).to_list()
        resumes = [r for r in all_resumes if r.is_published]

        if not resumes:
            await message.answer(
                "❌ <b>Нет опубликованных резюме</b>\n\n"
                "Создайте и опубликуйте резюме, чтобы откликаться на вакансии.",
                reply_markup=get_main_menu_applicant()
            )
            return

        # Save data to state
        await state.update_data(
            apply_vacancy_id=vacancy_id,
            apply_employer_id=str(employer_user.id),
            apply_employer_telegram_id=employer_user.telegram_id,
            apply_vacancy_position=vacancy.position,
            apply_vacancy_company=vacancy.company_name
        )

        # Show vacancy info and resume selection
        text = (
            f"📬 <b>Отклик на вакансию</b>\n\n"
            f"<b>Вакансия:</b> {vacancy.position}\n"
        )
        if vacancy.company_name:
            text += f"<b>Компания:</b> {vacancy.company_name}\n"
        if vacancy.city:
            text += f"<b>Город:</b> {vacancy.city}\n"
        if vacancy.salary_min or vacancy.salary_max:
            if vacancy.salary_min and vacancy.salary_max:
                text += f"<b>Зарплата:</b> {vacancy.salary_min:,} - {vacancy.salary_max:,} ₽\n"
            elif vacancy.salary_min:
                text += f"<b>Зарплата:</b> от {vacancy.salary_min:,} ₽\n"
            else:
                text += f"<b>Зарплата:</b> до {vacancy.salary_max:,} ₽\n"

        text += "\n<b>Выберите резюме для отклика:</b>"

        # Build resume selection keyboard
        builder = InlineKeyboardBuilder()
        for resume in resumes:
            salary_text = ""
            if resume.desired_salary:
                salary_text = f" ({resume.desired_salary:,}₽)"

            builder.row(InlineKeyboardButton(
                text=f"📄 {resume.desired_position}{salary_text}",
                callback_data=f"ch_apply_res:{resume.id}"
            ))

        builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="ch_apply_cancel"))

        await message.answer(text, reply_markup=builder.as_markup())
        await state.set_state(ChannelApplyStates.select_resume)

    except Exception as e:
        logger.error(f"Error in handle_vacancy_apply: {e}")
        await message.answer(
            "❌ Произошла ошибка при обработке отклика. Попробуйте позже.",
            reply_markup=get_main_menu_applicant()
        )


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    """Handle /start command with optional deep link."""
    telegram_id = message.from_user.id

    # Parse deep link parameter (e.g., /start resume_123 or /start vacancy_456)
    command_args = message.text.split(maxsplit=1)
    deep_link_param = command_args[1] if len(command_args) > 1 else None

    # Check if user exists
    user = await User.find_one(User.telegram_id == telegram_id)

    # Handle deep link if present and user exists
    if deep_link_param and user:
        await handle_deep_link(message, state, user, deep_link_param)
        return

    # Clear state for normal start flow
    await state.clear()

    if user:
        # Existing user - show personal cabinet
        logger.info(f"Existing user {telegram_id} started bot")

        # If dual-role user and no current_role set, ask which role to enter
        if user.is_dual_role() and not user.current_role:
            welcome_text = (
                f"👋 <b>С возвращением, {user.first_name or 'друг'}!</b>\n\n"
                f"У тебя двойная роль в системе.\n"
                f"Под какой ролью хочешь войти?"
            )
            await message.answer(
                welcome_text,
                reply_markup=get_dual_role_selection_keyboard()
            )
            return

        # Show personal cabinet
        await show_personal_cabinet(message, user)

    else:
        # New user - ask for role
        logger.info(f"New user {telegram_id} started bot")

        welcome_text = (
            "👋 <b>Привет! Я — Клик.</b>\n\n"
            "Я могу помочь тебе найти работу твоей мечты "
            "или разместить вакансию для твоего заведения.\n\n"
            "Чтобы начать, скажи — <b>кто ты?</b>"
        )

        await message.answer(
            welcome_text,
            reply_markup=get_role_selection_keyboard()
        )


@router.callback_query(F.data.startswith("enter_as:"))
async def enter_as_role(callback: CallbackQuery, state: FSMContext):
    """Handle role selection for dual-role users on start."""
    await callback.answer()

    role = callback.data.split(":")[1]
    telegram_id = callback.from_user.id

    user = await User.find_one(User.telegram_id == telegram_id)
    if not user:
        await callback.message.answer("❌ Пользователь не найден. Используй /start")
        return

    # Set current role
    user.current_role = UserRole(role)
    await user.save()

    logger.info(f"User {telegram_id} entered as {role}")

    # Remove inline keyboard and show cabinet
    await callback.message.edit_reply_markup(reply_markup=None)

    # Show menu
    await show_menu_for_role(callback.message, user)


@router.callback_query(F.data.startswith("switch_role:"))
async def switch_role(callback: CallbackQuery, state: FSMContext):
    """Handle role switching for dual-role users."""
    await callback.answer("Переключаю роль...")

    new_role = callback.data.split(":")[1]
    telegram_id = callback.from_user.id

    user = await User.find_one(User.telegram_id == telegram_id)
    if not user:
        await callback.message.answer("❌ Пользователь не найден.")
        return

    if not user.is_dual_role():
        await callback.message.answer("❌ У тебя только одна роль.")
        return

    # Set new current role
    user.current_role = UserRole(new_role)
    await user.save()

    role_name = "Соискатель" if new_role == "applicant" else "Работодатель"
    logger.info(f"User {telegram_id} switched to {new_role}")

    # Update cabinet text
    await callback.message.edit_text(
        f"✅ Ты переключился на роль: <b>{role_name}</b>",
        reply_markup=None
    )

    # Show new menu
    await show_menu_for_role(callback.message, user)


@router.callback_query(F.data == "go_to_menu")
async def go_to_menu(callback: CallbackQuery):
    """Handle going to menu from personal cabinet."""
    await callback.answer()

    telegram_id = callback.from_user.id
    user = await User.find_one(User.telegram_id == telegram_id)

    if not user:
        await callback.message.answer("❌ Пользователь не найден. Используй /start")
        return

    # Remove inline keyboard
    await callback.message.edit_reply_markup(reply_markup=None)

    # Show menu
    await show_menu_for_role(callback.message, user)


@router.callback_query(F.data.startswith("add_role:"))
async def add_second_role(callback: CallbackQuery, state: FSMContext):
    """Handle adding a second role to user."""
    await callback.answer()

    action = callback.data.split(":")[1]

    if action == "skip":
        await callback.message.edit_reply_markup(reply_markup=None)
        return

    telegram_id = callback.from_user.id
    user = await User.find_one(User.telegram_id == telegram_id)

    if not user:
        await callback.message.answer("❌ Пользователь не найден.")
        return

    new_role = UserRole(action)

    if user.has_role(new_role):
        await callback.message.answer(f"У тебя уже есть эта роль.")
        return

    # Add new role
    user.add_role(new_role)
    await user.save()

    role_name = "Соискатель" if action == "applicant" else "Работодатель"
    logger.info(f"User {telegram_id} added role {action}")

    await callback.message.edit_text(
        f"✅ Роль <b>{role_name}</b> добавлена!\n\n"
        f"Теперь ты можешь переключаться между ролями.",
        reply_markup=None
    )

    # If added employer role, start vacancy creation
    if new_role == UserRole.EMPLOYER:
        await state.set_data({"first_vacancy": True})
        creation_text = (
            "📝 <b>Создание вакансии</b>\n\n"
            "Отлично! Давай создадим твою первую вакансию.\n"
            "Я помогу тебе заполнить все необходимые поля.\n\n"
            "<b>Какую должность ищешь?</b>\n\nВыбери категорию:"
        )
        await callback.message.answer(
            creation_text,
            reply_markup=get_position_categories_keyboard()
        )
        await state.set_state(VacancyCreationStates.position_category)

    # If added applicant role, start resume creation
    elif new_role == UserRole.APPLICANT:
        await state.set_data({"first_resume": True})
        creation_text = (
            "📝 <b>Создание резюме</b>\n\n"
            "Отлично! Давай создадим твоё резюме.\n"
            "Я буду задавать тебе вопросы шаг за шагом.\n\n"
            "<b>Как тебя зовут?</b> (ФИО полностью)"
        )
        await callback.message.answer(creation_text, reply_markup=get_cancel_keyboard())
        await state.set_state(ResumeCreationStates.full_name)


@router.callback_query(F.data.startswith("role:"))
async def select_role(callback: CallbackQuery, state: FSMContext):
    """Handle role selection for new users."""
    await callback.answer()

    role = callback.data.split(":")[1]
    telegram_id = callback.from_user.id

    # Check if user already exists (e.g., from another device)
    existing_user = await User.find_one(User.telegram_id == telegram_id)
    if existing_user:
        await callback.message.edit_text(
            "Ты уже зарегистрирован! Используй /start для входа."
        )
        return

    # Create new user with roles list
    user = User(
        telegram_id=telegram_id,
        username=callback.from_user.username,
        first_name=callback.from_user.first_name,
        last_name=callback.from_user.last_name,
        roles=[UserRole(role)],  # Use roles list instead of single role
        current_role=UserRole(role),
    )
    await user.insert()

    logger.info(f"Created new user {telegram_id} with role {role}")

    # Show appropriate menu and start creation flow
    if role == "applicant":
        menu_keyboard = get_main_menu_applicant()
        welcome_text = (
            f"✅ Отлично, {user.first_name or 'друг'}!\n\n"
            f"Ты зарегистрирован как <b>Соискатель</b>.\n\n"
            f"Давай сразу создадим твоё резюме! 📝"
        )

        await callback.message.edit_text(welcome_text)
        await callback.message.answer("Главное меню:", reply_markup=menu_keyboard)

        # Automatically start resume creation
        await state.set_data({"first_resume": True})
        creation_text = (
            "📝 <b>Создание резюме</b>\n\n"
            "Хммм… 🤔 Вижу, ты у нас впервые.\n"
            "Отлично! Тогда давай создадим твоё резюме с нуля.\n\n"
            "Я задам тебе несколько вопросов, чтобы собрать всю нужную информацию.\n"
            "Не переживай — всё просто и быстро.\n\n"
            "Ты можешь в любой момент:\n"
            "• нажать 🚫 Отменить создание\n"
            "• пропустить необязательные шаги\n\n"
            "Ну что, начнём?\n\n"
            "<b>Как тебя зовут?</b> Напиши ФИО полностью"
        )
        await callback.message.answer(creation_text, reply_markup=get_cancel_keyboard())
        await state.set_state(ResumeCreationStates.full_name)

    else:
        menu_keyboard = get_main_menu_employer()
        welcome_text = (
            f"✅ Отлично, {user.first_name or 'друг'}!\n\n"
            f"Ты зарегистрирован как <b>Работодатель</b>.\n\n"
            f"Давай сразу создадим твою первую вакансию! 📝"
        )

        await callback.message.edit_text(welcome_text)
        await callback.message.answer("Главное меню:", reply_markup=menu_keyboard)

        # Automatically start vacancy creation
        await state.set_data({"first_vacancy": True})
        creation_text = (
            "📝 <b>Создание вакансии</b>\n\n"
            "Отлично! Давайте создадим вашу вакансию.\n"
            "Я — Бот Клик, и я помогу вам заполнить все необходимые поля, "
            "чтобы кандидатам было легко найти ваше предложение.\n\n"
            "Если что-то пойдёт не так, вы всегда можете нажать 🚫 Отменить создание.\n\n"
            "Начнём с главного.\n"
            "<b>Какую должность вы хотите найти?</b>\n\nВыберите категорию из списка ниже:"
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
        await message.answer("Пожалуйста, начни с команды /start")
        return

    await show_menu_for_role(message, user)

@router.message(Command("cabinet"))
async def cmd_cabinet(message: Message):
    """Show personal cabinet."""
    telegram_id = message.from_user.id
    user = await User.find_one(User.telegram_id == telegram_id)

    if not user:
        await message.answer("Пожалуйста, начни с команды /start")
        return

    await show_personal_cabinet(message, user)


# ============================================================================
# CHANNEL INVITE HANDLERS (when employer clicks "Пригласить" in channel)
# ============================================================================

@router.callback_query(ChannelInviteStates.select_vacancy, F.data.startswith("ch_invite_vac:"))
async def process_vacancy_selection_for_invite(callback: CallbackQuery, state: FSMContext):
    """Process vacancy selection for channel invite."""
    await callback.answer()

    vacancy_id = callback.data.split(":")[1]

    # Get vacancy info
    from backend.models import Vacancy
    vacancy = await Vacancy.get(PydanticObjectId(vacancy_id))

    if not vacancy:
        await callback.message.edit_text("❌ Вакансия не найдена.")
        await state.clear()
        return

    # Save vacancy to state
    await state.update_data(
        invite_vacancy_id=vacancy_id,
        invite_vacancy_position=vacancy.position,
        invite_vacancy_company=vacancy.company_name,
        invite_vacancy_city=vacancy.city,
        invite_vacancy_salary_min=vacancy.salary_min,
        invite_vacancy_salary_max=vacancy.salary_max
    )

    data = await state.get_data()

    # Show message input prompt
    text = (
        f"✉️ <b>Напишите сообщение кандидату</b>\n\n"
        f"<b>Кандидат:</b> {data.get('invite_resume_name')}\n"
        f"<b>Вакансия:</b> {vacancy.position}\n\n"
        f"Напишите приглашение для кандидата.\n"
        f"Например: расскажите о вакансии, условиях работы, почему выбрали именно его."
    )

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="ch_invite_cancel"))

    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await state.set_state(ChannelInviteStates.enter_message)


@router.message(ChannelInviteStates.enter_message)
async def process_invite_message(message: Message, state: FSMContext):
    """Process invitation message text."""
    invite_message = message.text.strip()

    if len(invite_message) < 10:
        await message.answer(
            "❌ Сообщение слишком короткое.\n"
            "Напишите хотя бы 10 символов, чтобы кандидат понял суть приглашения:"
        )
        return

    if len(invite_message) > 1000:
        await message.answer(
            "❌ Сообщение слишком длинное.\n"
            "Максимум 1000 символов. Сократите сообщение:"
        )
        return

    await state.update_data(invite_message=invite_message)
    data = await state.get_data()

    # Build salary text
    salary_text = ""
    salary_min = data.get('invite_vacancy_salary_min')
    salary_max = data.get('invite_vacancy_salary_max')
    if salary_min or salary_max:
        if salary_min and salary_max:
            salary_text = f"\n💰 <b>Зарплата:</b> {salary_min:,} - {salary_max:,} ₽"
        elif salary_min:
            salary_text = f"\n💰 <b>Зарплата:</b> от {salary_min:,} ₽"
        else:
            salary_text = f"\n💰 <b>Зарплата:</b> до {salary_max:,} ₽"

    # Show confirmation
    text = (
        f"📨 <b>Подтвердите отправку приглашения</b>\n\n"
        f"<b>Кандидат:</b> {data.get('invite_resume_name')}\n"
        f"<b>Вакансия:</b> {data.get('invite_vacancy_position')}\n"
        f"<b>Компания:</b> {data.get('invite_vacancy_company', 'Не указана')}\n"
        f"<b>Город:</b> {data.get('invite_vacancy_city', 'Не указан')}"
        f"{salary_text}\n\n"
        f"<b>Ваше сообщение:</b>\n"
        f"<i>{invite_message[:300]}{'...' if len(invite_message) > 300 else ''}</i>"
    )

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="✅ Отправить приглашение", callback_data="ch_invite_confirm"))
    builder.row(InlineKeyboardButton(text="✏️ Изменить сообщение", callback_data="ch_invite_edit_msg"))
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="ch_invite_cancel"))

    await message.answer(text, reply_markup=builder.as_markup())
    await state.set_state(ChannelInviteStates.confirm_send)


@router.callback_query(ChannelInviteStates.confirm_send, F.data == "ch_invite_confirm")
async def confirm_and_send_invite(callback: CallbackQuery, state: FSMContext):
    """Confirm and send the invitation."""
    await callback.answer("Отправляю приглашение...")

    data = await state.get_data()
    telegram_id = callback.from_user.id
    user = await User.find_one(User.telegram_id == telegram_id)

    if not user:
        await callback.message.edit_text("❌ Ошибка: пользователь не найден.")
        await state.clear()
        return

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            # 1. Create invitation (Response)
            invitation_data = {
                "employer_id": str(user.id),
                "applicant_id": data.get('invite_applicant_id'),
                "vacancy_id": data.get('invite_vacancy_id'),
                "resume_id": data.get('invite_resume_id'),
                "invitation_message": data.get('invite_message')
            }

            inv_response = await client.post(
                f"{settings.api_url}/responses/invitation",
                json=invitation_data
            )

            if inv_response.status_code != 201:
                error_detail = inv_response.json().get("detail", "Unknown error")
                await callback.message.edit_text(
                    f"❌ Ошибка при создании приглашения:\n{error_detail}"
                )
                await state.clear()
                return

            invitation_result = inv_response.json()
            response_id = invitation_result.get("id") or invitation_result.get("_id")

            # 2. Create or get chat
            chat_id = None
            if response_id:
                chat_response = await client.post(
                    f"{settings.api_url}/chats/create",
                    params={"response_id": response_id}
                )
                if chat_response.status_code == 201:
                    chat_data = chat_response.json()
                    chat_id = chat_data.get("id")

                    # 3. Send the invitation message to chat
                    await client.post(
                        f"{settings.api_url}/chats/{chat_id}/messages",
                        json={
                            "sender_id": str(user.id),
                            "text": data.get('invite_message')
                        }
                    )

        # Build success message
        builder = InlineKeyboardBuilder()
        if chat_id:
            builder.row(InlineKeyboardButton(text="💬 Открыть чат", callback_data=f"chat:open:{chat_id}"))
        builder.row(InlineKeyboardButton(text="🏠 В меню", callback_data="menu:employer"))

        await callback.message.edit_text(
            f"✅ <b>Приглашение отправлено!</b>\n\n"
            f"<b>Кандидат:</b> {data.get('invite_resume_name')}\n"
            f"<b>Вакансия:</b> {data.get('invite_vacancy_position')}\n\n"
            f"Кандидат получит уведомление о вашем приглашении.\n"
            f"Вы можете продолжить общение в чате.",
            reply_markup=builder.as_markup()
        )

        # 4. Send notification to applicant
        applicant_telegram_id = data.get('invite_applicant_telegram_id')
        if applicant_telegram_id:
            # Build salary text for notification
            salary_text = ""
            salary_min = data.get('invite_vacancy_salary_min')
            salary_max = data.get('invite_vacancy_salary_max')
            if salary_min or salary_max:
                if salary_min and salary_max:
                    salary_text = f"💰 Зарплата: {salary_min:,} - {salary_max:,} ₽\n"
                elif salary_min:
                    salary_text = f"💰 Зарплата: от {salary_min:,} ₽\n"
                else:
                    salary_text = f"💰 Зарплата: до {salary_max:,} ₽\n"

            notification_builder = InlineKeyboardBuilder()
            notification_builder.row(InlineKeyboardButton(
                text="💬 Открыть сообщения",
                callback_data="open_messages"
            ))

            try:
                await callback.bot.send_message(
                    chat_id=applicant_telegram_id,
                    text=(
                        f"🎉 <b>Вас пригласили на вакансию!</b>\n\n"
                        f"💼 <b>Вакансия:</b> {data.get('invite_vacancy_position')}\n"
                        f"🏢 <b>Компания:</b> {data.get('invite_vacancy_company', 'Не указана')}\n"
                        f"📍 <b>Город:</b> {data.get('invite_vacancy_city', 'Не указан')}\n"
                        f"{salary_text}\n"
                        f"<b>Сообщение от работодателя:</b>\n"
                        f"<i>{data.get('invite_message', '')[:200]}{'...' if len(data.get('invite_message', '')) > 200 else ''}</i>\n\n"
                        f"Перейдите в раздел «💬 Сообщения» чтобы ответить."
                    ),
                    parse_mode="HTML",
                    reply_markup=notification_builder.as_markup()
                )
            except Exception as e:
                logger.error(f"Failed to send notification to applicant: {e}")

        logger.info(f"Employer {user.id} invited candidate {data.get('invite_applicant_id')} to vacancy {data.get('invite_vacancy_id')}")

    except Exception as e:
        logger.error(f"Error sending invitation: {e}")
        await callback.message.edit_text(
            "❌ Произошла ошибка при отправке приглашения. Попробуйте позже."
        )

    await state.clear()


@router.callback_query(ChannelInviteStates.confirm_send, F.data == "ch_invite_edit_msg")
async def edit_invite_message(callback: CallbackQuery, state: FSMContext):
    """Allow user to edit the invitation message."""
    await callback.answer()

    data = await state.get_data()

    text = (
        f"✏️ <b>Измените сообщение</b>\n\n"
        f"<b>Кандидат:</b> {data.get('invite_resume_name')}\n"
        f"<b>Вакансия:</b> {data.get('invite_vacancy_position')}\n\n"
        f"Напишите новое сообщение:"
    )

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="ch_invite_cancel"))

    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await state.set_state(ChannelInviteStates.enter_message)


@router.callback_query(F.data == "ch_invite_cancel")
async def cancel_channel_invite(callback: CallbackQuery, state: FSMContext):
    """Cancel channel invitation process."""
    await callback.answer()
    await state.clear()

    await callback.message.edit_text(
        "❌ Приглашение отменено.",
        reply_markup=InlineKeyboardBuilder().row(
            InlineKeyboardButton(text="🏠 В меню", callback_data="menu:employer")
        ).as_markup()
    )


@router.callback_query(F.data == "menu:employer")
async def go_to_employer_menu(callback: CallbackQuery, state: FSMContext):
    """Return to employer menu."""
    await callback.answer()
    await state.clear()

    await callback.message.answer(
        "📋 Главное меню:",
        reply_markup=get_main_menu_employer()
    )


@router.callback_query(F.data == "open_messages")
async def open_messages_from_notification(callback: CallbackQuery, state: FSMContext):
    """Open messages section from notification."""
    await callback.answer()

    telegram_id = callback.from_user.id
    user = await User.find_one(User.telegram_id == telegram_id)

    if not user:
        await callback.message.answer("Пользователь не найден. Используйте /start")
        return

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{settings.api_url}/chats/user/{user.id}"
            )

            if response.status_code != 200:
                await callback.message.answer("❌ Ошибка при загрузке чатов")
                return

            chats = response.json()

            if not chats:
                await callback.message.answer(
                    "💬 <b>Сообщения</b>\n\n"
                    "У вас пока нет активных чатов.\n\n"
                    "Чаты создаются автоматически при отклике на вакансию "
                    "или приглашении кандидата."
                )
                return

            # Build chat list
            text = "💬 <b>Мои чаты</b>\n\n"
            text += "Выберите чат для просмотра:\n\n"

            builder = InlineKeyboardBuilder()

            for chat in chats[:20]:
                # Determine other participant
                if chat["applicant_id"] == str(user.id):
                    participant_role = "Работодатель"
                else:
                    participant_role = "Соискатель"

                unread = chat.get("unread_count", 0)
                unread_text = f" 🔴 {unread}" if unread > 0 else ""

                last_msg = chat.get("last_message_text") or "Нет сообщений"
                if last_msg and len(last_msg) > 50:
                    last_msg = last_msg[:50] + "..."

                preview = f"{participant_role}{unread_text}\n💬 {last_msg}"

                builder.row(
                    InlineKeyboardButton(
                        text=preview[:60],
                        callback_data=f"chat:open:{chat['id']}"
                    )
                )

            if len(chats) > 20:
                text += f"\n<i>Показаны первые 20 из {len(chats)} чатов</i>"

            await callback.message.answer(text, reply_markup=builder.as_markup())

    except Exception as e:
        logger.error(f"Error loading chats from notification: {e}")
        await callback.message.answer("❌ Ошибка при загрузке чатов")


# ============================================================================
# CHANNEL APPLY HANDLERS (when applicant clicks "Откликнуться" in channel)
# ============================================================================

@router.callback_query(ChannelApplyStates.select_resume, F.data.startswith("ch_apply_res:"))
async def process_resume_selection_for_apply(callback: CallbackQuery, state: FSMContext):
    """Process resume selection for channel apply."""
    await callback.answer()

    resume_id = callback.data.split(":")[1]

    # Get resume info
    from backend.models import Resume
    resume = await Resume.get(PydanticObjectId(resume_id))

    if not resume:
        await callback.message.edit_text("❌ Резюме не найдено.")
        await state.clear()
        return

    # Save resume to state
    await state.update_data(
        apply_resume_id=resume_id,
        apply_resume_position=resume.desired_position,
        apply_resume_name=resume.full_name
    )

    data = await state.get_data()

    # Ask for cover letter
    text = (
        f"✉️ <b>Напишите сопроводительное письмо</b>\n\n"
        f"<b>Вакансия:</b> {data.get('apply_vacancy_position')}\n"
        f"<b>Ваше резюме:</b> {resume.desired_position}\n\n"
        f"Напишите сопроводительное письмо или нажмите «Пропустить».\n"
        f"Хорошее письмо повысит шансы на приглашение!"
    )

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="⏭ Пропустить", callback_data="ch_apply_skip_letter"))
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="ch_apply_cancel"))

    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await state.set_state(ChannelApplyStates.enter_cover_letter)


@router.message(ChannelApplyStates.enter_cover_letter)
async def process_cover_letter(message: Message, state: FSMContext):
    """Process cover letter text."""
    cover_letter = message.text.strip()

    if len(cover_letter) > 1000:
        await message.answer(
            "❌ Письмо слишком длинное.\n"
            "Максимум 1000 символов. Сократите письмо:"
        )
        return

    await state.update_data(apply_cover_letter=cover_letter)
    await show_apply_confirmation(message, state, edit=False)


@router.callback_query(ChannelApplyStates.enter_cover_letter, F.data == "ch_apply_skip_letter")
async def skip_cover_letter(callback: CallbackQuery, state: FSMContext):
    """Skip cover letter."""
    await callback.answer()
    await state.update_data(apply_cover_letter=None)
    await show_apply_confirmation(callback.message, state, edit=True)


async def show_apply_confirmation(message: Message, state: FSMContext, edit: bool = False):
    """Show application confirmation."""
    data = await state.get_data()

    text = (
        f"📋 <b>Подтвердите отклик</b>\n\n"
        f"<b>Вакансия:</b> {data.get('apply_vacancy_position')}\n"
        f"<b>Компания:</b> {data.get('apply_vacancy_company', 'Не указана')}\n\n"
        f"<b>Ваше резюме:</b> {data.get('apply_resume_position')}\n"
    )

    cover_letter = data.get('apply_cover_letter')
    if cover_letter:
        preview = cover_letter[:150] + "..." if len(cover_letter) > 150 else cover_letter
        text += f"\n<b>Сопроводительное письмо:</b>\n<i>{preview}</i>\n"
    else:
        text += f"\n<i>Без сопроводительного письма</i>\n"

    text += "\n<b>Отправить отклик?</b>"

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="✅ Отправить", callback_data="ch_apply_confirm"))
    builder.row(InlineKeyboardButton(text="✏️ Изменить письмо", callback_data="ch_apply_edit_letter"))
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="ch_apply_cancel"))

    await state.set_state(ChannelApplyStates.confirm_send)

    if edit:
        await message.edit_text(text, reply_markup=builder.as_markup())
    else:
        await message.answer(text, reply_markup=builder.as_markup())


@router.callback_query(ChannelApplyStates.confirm_send, F.data == "ch_apply_confirm")
async def confirm_channel_apply(callback: CallbackQuery, state: FSMContext):
    """Confirm and send application."""
    await callback.answer("Отправка отклика...")

    data = await state.get_data()
    telegram_id = callback.from_user.id
    user = await User.find_one(User.telegram_id == telegram_id)

    if not user:
        await callback.message.edit_text("❌ Ошибка: пользователь не найден.")
        await state.clear()
        return

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # 1. Create Response (application)
            response_data = {
                "applicant_id": str(user.id),
                "employer_id": data.get('apply_employer_id'),
                "vacancy_id": data.get('apply_vacancy_id'),
                "resume_id": data.get('apply_resume_id'),
                "message": data.get('apply_cover_letter')
            }

            response = await client.post(
                f"{settings.api_url}/responses",
                params=response_data
            )

            if response.status_code not in (200, 201):
                error_detail = response.json().get("detail", "Неизвестная ошибка")
                await callback.message.edit_text(f"❌ Ошибка: {error_detail}")
                await state.clear()
                return

            application_result = response.json()
            response_id = application_result.get("id") or application_result.get("_id")

            # 2. Create or get chat
            chat_id = None
            if response_id:
                chat_response = await client.post(
                    f"{settings.api_url}/chats/create",
                    params={"response_id": response_id}
                )
                if chat_response.status_code == 201:
                    chat_data = chat_response.json()
                    chat_id = chat_data.get("id")

                    # 3. Send cover letter as first message if exists
                    cover_letter = data.get('apply_cover_letter')
                    if cover_letter and chat_id:
                        await client.post(
                            f"{settings.api_url}/chats/{chat_id}/messages",
                            json={
                                "sender_id": str(user.id),
                                "text": cover_letter
                            }
                        )

        # Build success message
        builder = InlineKeyboardBuilder()
        if chat_id:
            builder.row(InlineKeyboardButton(text="💬 Открыть чат", callback_data=f"chat:open:{chat_id}"))
        builder.row(InlineKeyboardButton(text="🏠 В меню", callback_data="menu:applicant"))

        await callback.message.edit_text(
            f"✅ <b>Отклик отправлен!</b>\n\n"
            f"<b>Вакансия:</b> {data.get('apply_vacancy_position')}\n"
            f"<b>Компания:</b> {data.get('apply_vacancy_company', 'Не указана')}\n\n"
            f"Работодатель получит уведомление о вашем отклике.\n"
            f"Ожидайте ответа или напишите в чат.",
            reply_markup=builder.as_markup()
        )

        # 4. Send notification to employer
        employer_telegram_id = data.get('apply_employer_telegram_id')
        if employer_telegram_id:
            notification_builder = InlineKeyboardBuilder()
            notification_builder.row(InlineKeyboardButton(
                text="💬 Открыть сообщения",
                callback_data="open_messages"
            ))

            try:
                await callback.bot.send_message(
                    chat_id=employer_telegram_id,
                    text=(
                        f"📬 <b>Новый отклик на вакансию!</b>\n\n"
                        f"💼 <b>Вакансия:</b> {data.get('apply_vacancy_position')}\n"
                        f"👤 <b>Кандидат:</b> {data.get('apply_resume_name', 'Не указано')}\n"
                        f"📄 <b>Должность в резюме:</b> {data.get('apply_resume_position')}\n\n"
                        f"Перейдите в раздел «💬 Сообщения» чтобы ответить."
                    ),
                    parse_mode="HTML",
                    reply_markup=notification_builder.as_markup()
                )
            except Exception as e:
                logger.error(f"Failed to send notification to employer: {e}")

        logger.info(f"Applicant {user.id} applied to vacancy {data.get('apply_vacancy_id')}")

    except Exception as e:
        logger.error(f"Error sending application: {e}")
        await callback.message.edit_text(
            "❌ Произошла ошибка при отправке отклика. Попробуйте позже."
        )

    await state.clear()


@router.callback_query(ChannelApplyStates.confirm_send, F.data == "ch_apply_edit_letter")
async def edit_cover_letter(callback: CallbackQuery, state: FSMContext):
    """Allow user to edit the cover letter."""
    await callback.answer()

    data = await state.get_data()

    text = (
        f"✏️ <b>Измените сопроводительное письмо</b>\n\n"
        f"<b>Вакансия:</b> {data.get('apply_vacancy_position')}\n"
        f"<b>Ваше резюме:</b> {data.get('apply_resume_position')}\n\n"
        f"Напишите новое письмо или нажмите «Пропустить»:"
    )

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="⏭ Пропустить", callback_data="ch_apply_skip_letter"))
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="ch_apply_cancel"))

    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await state.set_state(ChannelApplyStates.enter_cover_letter)


@router.callback_query(F.data == "ch_apply_cancel")
async def cancel_channel_apply(callback: CallbackQuery, state: FSMContext):
    """Cancel channel application process."""
    await callback.answer()
    await state.clear()

    await callback.message.edit_text(
        "❌ Отклик отменён.",
        reply_markup=InlineKeyboardBuilder().row(
            InlineKeyboardButton(text="🏠 В меню", callback_data="menu:applicant")
        ).as_markup()
    )


@router.callback_query(F.data == "menu:applicant")
async def go_to_applicant_menu(callback: CallbackQuery, state: FSMContext):
    """Return to applicant menu."""
    await callback.answer()
    await state.clear()

    await callback.message.answer(
        "📋 Главное меню:",
        reply_markup=get_main_menu_applicant()
    )
