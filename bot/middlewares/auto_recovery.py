"""
Auto-recovery middleware for handling stuck states.
If user sends 3 consecutive messages that don't change state,
they are returned to main menu.
"""

from typing import Callable, Dict, Any, Awaitable, Union
from collections import defaultdict
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from loguru import logger

from backend.models import User
from shared.constants import UserRole
from bot.keyboards.common import (
    get_main_menu_applicant,
    get_main_menu_employer,
    get_role_selection_keyboard,
)


# Track consecutive unhandled actions per user
# Format: {user_id: {"count": int, "last_state": str}}
_user_stuck_tracker: Dict[int, Dict[str, Any]] = defaultdict(
    lambda: {"count": 0, "last_state": None}
)

# Max consecutive unhandled actions before auto-recovery
MAX_STUCK_COUNT = 3


async def _return_to_menu(event: Union[Message, CallbackQuery], state: FSMContext):
    """Clear state and return user to main menu."""
    user_id = event.from_user.id
    await state.clear()

    # Get user and their menu
    user = await User.find_one(User.telegram_id == user_id)

    if user:
        current_role = user.current_role or user.role
        if current_role == UserRole.APPLICANT:
            keyboard = get_main_menu_applicant()
        else:
            keyboard = get_main_menu_employer()

        text = (
            "⚠️ <b>Произошёл сбой</b>\n\n"
            "Похоже, что-то пошло не так. Я вернул тебя в главное меню.\n"
            "Если проблема повторится, используй команду /start"
        )
    else:
        keyboard = get_role_selection_keyboard()
        text = (
            "👋 <b>Привет! Я — Клик.</b>\n\n"
            "Произошёл сбой. Давай начнём сначала.\n"
            "Выбери, кто ты:"
        )

    # Send message based on event type
    if isinstance(event, CallbackQuery):
        try:
            await event.answer("⚠️ Возврат в главное меню")
        except Exception:
            pass
        await event.message.answer(text, reply_markup=keyboard)
    else:
        await event.answer(text, reply_markup=keyboard)

    # Reset tracker
    _user_stuck_tracker[user_id] = {"count": 0, "last_state": None}

    logger.warning(f"Auto-recovery: User {user_id} returned to menu after stuck state")


class AutoRecoveryMiddleware(BaseMiddleware):
    """
    Middleware that tracks stuck users and auto-recovers them.

    A user is considered "stuck" if they:
    1. Are in an FSM state
    2. Send multiple messages that don't change the state
    3. This indicates the handlers aren't processing their input
    """

    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any]
    ) -> Any:
        """Process message and track stuck states."""
        user_id = event.from_user.id
        state: FSMContext = data.get("state")

        if not state:
            return await handler(event, data)

        current_state = await state.get_state()
        tracker = _user_stuck_tracker[user_id]

        # If no FSM state, reset tracker
        if not current_state:
            _user_stuck_tracker[user_id] = {"count": 0, "last_state": None}
            return await handler(event, data)

        # Skip if this is a menu button (handled by StateResetMiddleware)
        from bot.middlewares.state_reset import StateResetMiddleware
        if event.text and event.text in StateResetMiddleware.MENU_BUTTONS:
            _user_stuck_tracker[user_id] = {"count": 0, "last_state": None}
            return await handler(event, data)

        # Process the message
        result = await handler(event, data)

        # Check state after processing
        new_state = await state.get_state()

        # If state changed, user is not stuck
        if new_state != current_state:
            _user_stuck_tracker[user_id] = {"count": 0, "last_state": new_state}
            return result

        # State didn't change - increment stuck counter
        if tracker["last_state"] == current_state:
            tracker["count"] += 1
        else:
            tracker["count"] = 1
            tracker["last_state"] = current_state

        logger.debug(
            f"User {user_id} stuck count: {tracker['count']}/{MAX_STUCK_COUNT} "
            f"in state {current_state}"
        )

        # Check if stuck threshold reached
        if tracker["count"] >= MAX_STUCK_COUNT:
            logger.warning(
                f"User {user_id} exceeded stuck threshold in state {current_state}"
            )
            await _return_to_menu(event, state)

        return result


class CallbackAutoRecoveryMiddleware(BaseMiddleware):
    """
    Middleware for callback queries that tracks stuck states.
    """

    async def __call__(
        self,
        handler: Callable,
        event: CallbackQuery,
        data: Dict[str, Any]
    ) -> Any:
        """Process callback and track stuck states."""
        user_id = event.from_user.id
        state: FSMContext = data.get("state")

        if not state:
            return await handler(event, data)

        current_state = await state.get_state()
        tracker = _user_stuck_tracker[user_id]

        # If no FSM state, reset tracker
        if not current_state:
            _user_stuck_tracker[user_id] = {"count": 0, "last_state": None}
            return await handler(event, data)

        # Process the callback
        result = await handler(event, data)

        # Check state after processing
        new_state = await state.get_state()

        # If state changed, user is not stuck
        if new_state != current_state:
            _user_stuck_tracker[user_id] = {"count": 0, "last_state": new_state}
            return result

        # State didn't change - increment stuck counter only if callback wasn't answered
        # (answered callbacks usually mean the action was processed)
        if not event.answered:
            if tracker["last_state"] == current_state:
                tracker["count"] += 1
            else:
                tracker["count"] = 1
                tracker["last_state"] = current_state

            logger.debug(
                f"User {user_id} callback stuck count: {tracker['count']}/{MAX_STUCK_COUNT}"
            )

            # Check if stuck threshold reached
            if tracker["count"] >= MAX_STUCK_COUNT:
                logger.warning(
                    f"User {user_id} exceeded callback stuck threshold in state {current_state}"
                )
                await _return_to_menu(event, state)

        return result


def reset_user_tracker(user_id: int):
    """Reset stuck tracker for a user (call when user successfully completes an action)."""
    if user_id in _user_stuck_tracker:
        _user_stuck_tracker[user_id] = {"count": 0, "last_state": None}
