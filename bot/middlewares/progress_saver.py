"""
Middleware for automatically saving resume/vacancy creation progress.
Saves to MongoDB after each step to enable progress recovery.
"""

from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from loguru import logger


# FSM state prefixes that indicate resume creation
RESUME_STATE_PREFIX = "ResumeCreationStates:"

# FSM state prefixes that indicate vacancy creation
VACANCY_STATE_PREFIX = "VacancyCreationStates:"


class ProgressSaverMiddleware(BaseMiddleware):
    """
    Middleware that saves creation progress to MongoDB after each step.
    This allows users to resume from where they left off if FSM state is lost.
    """

    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any]
    ) -> Any:
        """Process message and save progress after handler completes."""
        state: FSMContext = data.get("state")

        if not state:
            return await handler(event, data)

        # Get state before processing
        state_before = await state.get_state()

        # Process the message
        result = await handler(event, data)

        # Get state and data after processing
        state_after = await state.get_state()
        fsm_data = await state.get_data()

        # Save progress if in creation flow
        if state_after:
            try:
                await self._save_progress(
                    telegram_id=event.from_user.id,
                    state_name=state_after,
                    fsm_data=fsm_data
                )
            except Exception as e:
                logger.error(f"Failed to save progress for user {event.from_user.id}: {e}")

        return result

    async def _save_progress(
        self,
        telegram_id: int,
        state_name: str,
        fsm_data: Dict[str, Any]
    ) -> None:
        """Save progress based on current state type."""
        from backend.models import save_resume_progress, save_vacancy_progress

        if state_name.startswith(RESUME_STATE_PREFIX):
            await save_resume_progress(telegram_id, state_name, fsm_data)
            logger.debug(f"Saved resume progress for user {telegram_id}, state: {state_name}")

        elif state_name.startswith(VACANCY_STATE_PREFIX):
            await save_vacancy_progress(telegram_id, state_name, fsm_data)
            logger.debug(f"Saved vacancy progress for user {telegram_id}, state: {state_name}")


class CallbackProgressSaverMiddleware(BaseMiddleware):
    """
    Middleware for callback queries that saves creation progress.
    """

    async def __call__(
        self,
        handler: Callable,
        event: CallbackQuery,
        data: Dict[str, Any]
    ) -> Any:
        """Process callback and save progress after handler completes."""
        state: FSMContext = data.get("state")

        if not state:
            return await handler(event, data)

        # Process the callback
        result = await handler(event, data)

        # Get state and data after processing
        state_after = await state.get_state()
        fsm_data = await state.get_data()

        # Save progress if in creation flow
        if state_after:
            try:
                await self._save_progress(
                    telegram_id=event.from_user.id,
                    state_name=state_after,
                    fsm_data=fsm_data
                )
            except Exception as e:
                logger.error(f"Failed to save callback progress for user {event.from_user.id}: {e}")

        return result

    async def _save_progress(
        self,
        telegram_id: int,
        state_name: str,
        fsm_data: Dict[str, Any]
    ) -> None:
        """Save progress based on current state type."""
        from backend.models import save_resume_progress, save_vacancy_progress

        if state_name.startswith(RESUME_STATE_PREFIX):
            await save_resume_progress(telegram_id, state_name, fsm_data)
            logger.debug(f"Saved resume callback progress for user {telegram_id}")

        elif state_name.startswith(VACANCY_STATE_PREFIX):
            await save_vacancy_progress(telegram_id, state_name, fsm_data)
            logger.debug(f"Saved vacancy callback progress for user {telegram_id}")
