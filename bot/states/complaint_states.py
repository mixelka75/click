"""
FSM states for complaint submission.
"""

from aiogram.fsm.state import State, StatesGroup


class ComplaintStates(StatesGroup):
    """States for complaint submission flow."""

    # Выбор причины жалобы
    selecting_reason = State()

    # Ввод комментария (опционально)
    entering_comment = State()

    # Подтверждение отправки
    confirming = State()
