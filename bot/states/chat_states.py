"""
FSM states for chat.
"""

from aiogram.fsm.state import State, StatesGroup


class ChatStates(StatesGroup):
    """States for chat conversation."""

    # Viewing chat list
    viewing_chats = State()

    # In active chat conversation
    in_chat = State()

    # Waiting for message input
    waiting_for_message = State()
