"""
Complaint handlers - report vacancies and resumes.
"""

from datetime import datetime, timedelta
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton
from loguru import logger
from beanie import PydanticObjectId

from backend.models import (
    User, Vacancy, Resume,
    Complaint, ReporterBan, ComplaintStats
)
from bot.states.complaint_states import ComplaintStates
from shared.constants import (
    ComplaintType, ComplaintStatus,
    VACANCY_COMPLAINT_REASONS, RESUME_COMPLAINT_REASONS,
    COMPLAINT_COOLDOWN_MINUTES, MAX_COMPLAINTS_PER_DAY,
    COMPLAINTS_FOR_AUTO_MODERATION
)
from config.settings import settings

router = Router()


async def check_reporter_ban(user_id: PydanticObjectId) -> bool:
    """Check if user is banned from reporting."""
    ban = await ReporterBan.find_one(ReporterBan.user.id == user_id)
    if ban and ban.is_active:
        return True
    return False


async def check_complaint_limits(user_id: PydanticObjectId) -> tuple[bool, str]:
    """Check if user can submit complaint (cooldown and daily limit)."""
    now = datetime.utcnow()

    # Check cooldown (last complaint within COMPLAINT_COOLDOWN_MINUTES)
    cooldown_time = now - timedelta(minutes=COMPLAINT_COOLDOWN_MINUTES)
    recent_complaint = await Complaint.find_one(
        Complaint.reporter.id == user_id,
        Complaint.created_at > cooldown_time
    )
    if recent_complaint:
        wait_minutes = COMPLAINT_COOLDOWN_MINUTES - int(
            (now - recent_complaint.created_at).total_seconds() / 60
        )
        return False, f"Подожди {wait_minutes} мин. перед следующей жалобой"

    # Check daily limit
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_complaints = await Complaint.find(
        Complaint.reporter.id == user_id,
        Complaint.created_at >= today_start
    ).count()
    if today_complaints >= MAX_COMPLAINTS_PER_DAY:
        return False, f"Достигнут лимит жалоб на сегодня ({MAX_COMPLAINTS_PER_DAY})"

    return True, ""


def get_complaint_reasons_keyboard(
    complaint_type: ComplaintType,
    target_id: str
) -> InlineKeyboardBuilder:
    """Build keyboard with complaint reasons."""
    builder = InlineKeyboardBuilder()

    reasons = (
        VACANCY_COMPLAINT_REASONS
        if complaint_type == ComplaintType.VACANCY
        else RESUME_COMPLAINT_REASONS
    )

    # Short type code for callback_data (Telegram limit 64 bytes)
    type_code = "v" if complaint_type == ComplaintType.VACANCY else "r"

    for code, text in reasons:
        # Callback format: cr:{v|r}:{target_id}:{reason_code}
        builder.row(
            InlineKeyboardButton(
                text=text,
                callback_data=f"cr:{type_code}:{target_id}:{code}"
            )
        )

    builder.row(
        InlineKeyboardButton(text="❌ Отмена", callback_data="cr_cancel")
    )

    return builder


# ============================================================================
# COMPLAINT INITIATION (from recommendations)
# ============================================================================

@router.callback_query(F.data.startswith("report_vacancy:"))
async def start_vacancy_report(callback: CallbackQuery, state: FSMContext):
    """Start vacancy complaint flow."""
    await callback.answer()

    vacancy_id = callback.data.split(":")[1]
    telegram_id = callback.from_user.id

    user = await User.find_one(User.telegram_id == telegram_id)
    if not user:
        await callback.message.answer("Пользователь не найден")
        return

    # Check if banned
    if await check_reporter_ban(user.id):
        await callback.message.answer(
            "❌ Ты временно не можешь отправлять жалобы.\n"
            "Это может быть связано с отклонёнными жалобами ранее."
        )
        return

    # Check limits
    can_report, reason = await check_complaint_limits(user.id)
    if not can_report:
        await callback.message.answer(f"⏳ {reason}")
        return

    # Check vacancy exists
    vacancy = await Vacancy.get(PydanticObjectId(vacancy_id))
    if not vacancy:
        await callback.message.answer("Вакансия не найдена")
        return

    # Check if user is trying to report their own vacancy
    author_id = str(vacancy.user.ref.id) if vacancy.user else None
    if author_id and str(user.id) == author_id:
        await callback.message.answer("❌ Нельзя пожаловаться на свою собственную вакансию.")
        return

    # Save to state
    await state.update_data(
        complaint_type=ComplaintType.VACANCY.value,
        complaint_target_id=vacancy_id,
        complaint_target_author_id=author_id
    )

    # Show reasons
    builder = get_complaint_reasons_keyboard(ComplaintType.VACANCY, vacancy_id)

    await callback.message.answer(
        "🚨 <b>Пожаловаться на вакансию</b>\n\n"
        "Выбери причину жалобы:",
        reply_markup=builder.as_markup()
    )
    await state.set_state(ComplaintStates.selecting_reason)


@router.callback_query(F.data.startswith("report_resume:"))
async def start_resume_report(callback: CallbackQuery, state: FSMContext):
    """Start resume complaint flow."""
    await callback.answer()

    resume_id = callback.data.split(":")[1]
    telegram_id = callback.from_user.id

    user = await User.find_one(User.telegram_id == telegram_id)
    if not user:
        await callback.message.answer("Пользователь не найден")
        return

    # Check if banned
    if await check_reporter_ban(user.id):
        await callback.message.answer(
            "❌ Ты временно не можешь отправлять жалобы.\n"
            "Это может быть связано с отклонёнными жалобами ранее."
        )
        return

    # Check limits
    can_report, reason = await check_complaint_limits(user.id)
    if not can_report:
        await callback.message.answer(f"⏳ {reason}")
        return

    # Check resume exists
    resume = await Resume.get(PydanticObjectId(resume_id))
    if not resume:
        await callback.message.answer("Резюме не найдено")
        return

    # Check if user is trying to report their own resume
    author_id = str(resume.user.ref.id) if resume.user else None
    if author_id and str(user.id) == author_id:
        await callback.message.answer("❌ Нельзя пожаловаться на своё собственное резюме.")
        return

    # Save to state
    await state.update_data(
        complaint_type=ComplaintType.RESUME.value,
        complaint_target_id=resume_id,
        complaint_target_author_id=author_id
    )

    # Show reasons
    builder = get_complaint_reasons_keyboard(ComplaintType.RESUME, resume_id)

    await callback.message.answer(
        "🚨 <b>Пожаловаться на резюме</b>\n\n"
        "Выбери причину жалобы:",
        reply_markup=builder.as_markup()
    )
    await state.set_state(ComplaintStates.selecting_reason)


# ============================================================================
# DEEP LINK HANDLING (from channels)
# ============================================================================

async def handle_report_deep_link(
    message: Message,
    state: FSMContext,
    target_type: str,
    target_id: str
):
    """Handle deep link complaint initiation."""
    telegram_id = message.from_user.id

    user = await User.find_one(User.telegram_id == telegram_id)
    if not user:
        await message.answer("Пользователь не найден. Используй /start для регистрации.")
        return

    # Check if banned
    if await check_reporter_ban(user.id):
        await message.answer(
            "❌ Ты временно не можешь отправлять жалобы.\n"
            "Это может быть связано с отклонёнными жалобами ранее."
        )
        return

    # Check limits
    can_report, reason = await check_complaint_limits(user.id)
    if not can_report:
        await message.answer(f"⏳ {reason}")
        return

    # Determine type and check existence
    if target_type == "vacancy":
        complaint_type = ComplaintType.VACANCY
        target = await Vacancy.get(PydanticObjectId(target_id))
        if not target:
            await message.answer("Вакансия не найдена")
            return
        author_id = str(target.user.ref.id) if target.user else None
        type_text = "вакансию"
    else:
        complaint_type = ComplaintType.RESUME
        target = await Resume.get(PydanticObjectId(target_id))
        if not target:
            await message.answer("Резюме не найдено")
            return
        author_id = str(target.user.ref.id) if target.user else None
        type_text = "резюме"

    # Check if user is trying to report their own content
    if author_id and str(user.id) == author_id:
        await message.answer("❌ Нельзя пожаловаться на своё собственное объявление.")
        return

    # Save to state
    await state.update_data(
        complaint_type=complaint_type.value,
        complaint_target_id=target_id,
        complaint_target_author_id=author_id
    )

    # Show reasons
    builder = get_complaint_reasons_keyboard(complaint_type, target_id)

    await message.answer(
        f"🚨 <b>Пожаловаться на {type_text}</b>\n\n"
        "Выбери причину жалобы:",
        reply_markup=builder.as_markup()
    )
    await state.set_state(ComplaintStates.selecting_reason)


# ============================================================================
# REASON SELECTION
# ============================================================================

@router.callback_query(F.data.startswith("cr:"))
async def select_complaint_reason(callback: CallbackQuery, state: FSMContext):
    """Handle reason selection."""
    await callback.answer()

    parts = callback.data.split(":")
    # cr:{v|r}:{target_id}:{reason_code}
    type_code = parts[1]
    target_id = parts[2]
    reason_code = parts[3]

    # Convert short code to full type
    complaint_type = "vacancy" if type_code == "v" else "resume"

    # Get reason text
    reasons = (
        VACANCY_COMPLAINT_REASONS
        if complaint_type == "vacancy"
        else RESUME_COMPLAINT_REASONS
    )
    reason_text = next((text for code, text in reasons if code == reason_code), reason_code)

    # Save to state
    await state.update_data(
        complaint_reason_code=reason_code,
        complaint_reason_text=reason_text
    )

    # Ask for comment (optional)
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="📝 Добавить комментарий",
            callback_data="complaint_add_comment"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="✅ Отправить без комментария",
            callback_data="complaint_submit"
        )
    )
    builder.row(
        InlineKeyboardButton(text="❌ Отмена", callback_data="complaint_cancel")
    )

    await callback.message.edit_text(
        f"🚨 <b>Жалоба</b>\n\n"
        f"Причина: {reason_text}\n\n"
        "Хочешь добавить комментарий?",
        reply_markup=builder.as_markup()
    )


@router.callback_query(F.data == "complaint_add_comment")
async def request_comment(callback: CallbackQuery, state: FSMContext):
    """Request additional comment."""
    await callback.answer()

    await callback.message.edit_text(
        "📝 Напиши дополнительный комментарий к жалобе:\n\n"
        "<i>Или отправь /cancel для отмены</i>"
    )
    await state.set_state(ComplaintStates.entering_comment)


@router.message(ComplaintStates.entering_comment)
async def process_comment(message: Message, state: FSMContext):
    """Process comment input."""
    if message.text == "/cancel":
        await state.clear()
        await message.answer("Жалоба отменена.")
        return

    comment = message.text[:500] if message.text else ""
    await state.update_data(complaint_comment=comment)

    # Show confirmation
    data = await state.get_data()
    reason_text = data.get("complaint_reason_text", "")

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Отправить", callback_data="complaint_submit")
    )
    builder.row(
        InlineKeyboardButton(text="❌ Отмена", callback_data="complaint_cancel")
    )

    await message.answer(
        f"🚨 <b>Подтверждение жалобы</b>\n\n"
        f"Причина: {reason_text}\n"
        f"Комментарий: {comment}\n\n"
        "Отправить жалобу?",
        reply_markup=builder.as_markup()
    )
    await state.set_state(ComplaintStates.confirming)


# ============================================================================
# SUBMISSION
# ============================================================================

@router.callback_query(F.data == "complaint_submit")
async def submit_complaint(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Submit the complaint."""
    await callback.answer("Отправка жалобы...")

    telegram_id = callback.from_user.id
    user = await User.find_one(User.telegram_id == telegram_id)

    if not user:
        await callback.message.edit_text("Пользователь не найден")
        await state.clear()
        return

    data = await state.get_data()
    complaint_type = ComplaintType(data.get("complaint_type"))
    target_id = PydanticObjectId(data.get("complaint_target_id"))
    target_author_id = data.get("complaint_target_author_id")
    reason_code = data.get("complaint_reason_code")
    comment = data.get("complaint_comment")

    try:
        # Get target author
        target_author = None
        if target_author_id:
            target_author = await User.get(PydanticObjectId(target_author_id))

        # Create complaint
        complaint = Complaint(
            reporter=user,
            target_type=complaint_type,
            target_id=target_id,
            target_author=target_author,
            reason_code=reason_code,
            comment=comment,
            status=ComplaintStatus.PENDING
        )
        await complaint.insert()

        # Update stats
        stats = await ComplaintStats.get_or_create(complaint_type, target_id)
        await stats.increment()

        # Check if should auto-send to moderation
        if stats.total_complaints >= COMPLAINTS_FOR_AUTO_MODERATION and not stats.sent_to_moderation:
            stats.sent_to_moderation = True
            stats.sent_to_moderation_at = datetime.utcnow()
            await stats.save()

            # Send to moderation group
            await send_to_moderation(bot, complaint, stats)

        await callback.message.edit_text(
            "✅ <b>Жалоба отправлена!</b>\n\n"
            "Мы рассмотрим её в ближайшее время.\n"
            "Спасибо, что помогаешь улучшить платформу!"
        )

        logger.info(f"Complaint submitted: {complaint.id} by user {user.id}")

    except Exception as e:
        logger.error(f"Error submitting complaint: {e}")
        await callback.message.edit_text("❌ Ошибка при отправке жалобы")

    await state.clear()


@router.callback_query(F.data == "cr_cancel")
async def cancel_complaint(callback: CallbackQuery, state: FSMContext):
    """Cancel complaint submission."""
    await callback.answer("Отменено")
    await callback.message.edit_text("❌ Жалоба отменена.")
    await state.clear()


# ============================================================================
# MODERATION GROUP
# ============================================================================

async def send_to_moderation(bot: Bot, complaint: Complaint, stats: ComplaintStats):
    """Send complaint to moderation group."""
    moderation_chat_id = getattr(settings, 'moderation_chat_id', None)
    if not moderation_chat_id:
        logger.warning("Moderation chat ID not configured")
        return

    try:
        # Get target info
        if complaint.target_type == ComplaintType.VACANCY:
            target = await Vacancy.get(complaint.target_id)
            target_text = f"📋 Вакансия: {target.position}" if target else "Вакансия удалена"
            if target and target.company_name:
                target_text += f"\n🏢 {target.company_name}"
        else:
            target = await Resume.get(complaint.target_id)
            target_text = f"📄 Резюме: {target.desired_position}" if target else "Резюме удалено"
            if target and target.full_name:
                target_text += f"\n👤 {target.full_name}"

        # Get reason text
        reasons = (
            VACANCY_COMPLAINT_REASONS
            if complaint.target_type == ComplaintType.VACANCY
            else RESUME_COMPLAINT_REASONS
        )
        reason_text = next(
            (text for code, text in reasons if code == complaint.reason_code),
            complaint.reason_code
        )

        # Format message
        text = (
            "🚨 <b>ЖАЛОБА НА МОДЕРАЦИЮ</b>\n\n"
            f"{target_text}\n\n"
            f"📊 <b>Всего жалоб:</b> {stats.total_complaints}\n"
            f"⚠️ <b>Причина:</b> {reason_text}\n"
        )

        if complaint.comment:
            text += f"💬 <b>Комментарий:</b> {complaint.comment}\n"

        text += f"\n🆔 ID жалобы: <code>{complaint.id}</code>"

        # Build moderation buttons
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(
                text="✅ Оставить",
                callback_data=f"mod_dismiss:{complaint.id}"
            ),
            InlineKeyboardButton(
                text="🗑 Удалить",
                callback_data=f"mod_delete:{complaint.id}"
            )
        )
        builder.row(
            InlineKeyboardButton(
                text="⚠️ Предупреждение",
                callback_data=f"mod_warn:{complaint.id}"
            ),
            InlineKeyboardButton(
                text="🚫 Бан автора",
                callback_data=f"mod_ban:{complaint.id}"
            )
        )
        builder.row(
            InlineKeyboardButton(
                text="🔇 Игнор жалобщика (1д)",
                callback_data=f"mod_ignore:{complaint.id}:24"
            )
        )
        builder.row(
            InlineKeyboardButton(
                text="🔇 Игнор (1нед)",
                callback_data=f"mod_ignore:{complaint.id}:168"
            ),
            InlineKeyboardButton(
                text="🔇 Навсегда",
                callback_data=f"mod_ignore:{complaint.id}:-1"
            )
        )

        msg = await bot.send_message(
            chat_id=moderation_chat_id,
            text=text,
            reply_markup=builder.as_markup()
        )

        # Save message info for updates
        complaint.moderation_message_id = msg.message_id
        complaint.moderation_chat_id = moderation_chat_id
        await complaint.save()

        logger.info(f"Complaint {complaint.id} sent to moderation")

    except Exception as e:
        logger.error(f"Failed to send to moderation: {e}")
