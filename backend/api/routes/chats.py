"""
Chat API endpoints.
Handles direct messaging between applicants and employers.
"""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from loguru import logger

from backend.models import Chat, Message, User, Response

router = APIRouter(prefix="/chats", tags=["chats"])


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class SendMessageRequest(BaseModel):
    """Request model for sending a message."""
    sender_id: str
    text: str
    photo_file_id: Optional[str] = None
    document_file_id: Optional[str] = None


class ChatResponse(BaseModel):
    """Response model for chat."""
    id: str
    applicant_id: str
    employer_id: str
    response_id: str
    last_message_at: datetime
    last_message_text: Optional[str]
    unread_count: int
    is_archived: bool


class MessageResponse(BaseModel):
    """Response model for message."""
    sender_id: str
    text: str
    timestamp: datetime
    is_read: bool
    photo_file_id: Optional[str] = None
    document_file_id: Optional[str] = None


class ChatDetailsResponse(BaseModel):
    """Response model for chat with messages."""
    id: str
    applicant_id: str
    employer_id: str
    response_id: str
    messages: List[MessageResponse]
    is_archived: bool


# ============================================================================
# ENDPOINTS
# ============================================================================

@router.get("/user/{user_id}", response_model=List[ChatResponse])
async def get_user_chats(user_id: str, include_archived: bool = False):
    """Get all chats for a user."""
    try:
        user = await User.get(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        # Find all chats where user is participant
        query = {
            "$or": [
                {"applicant.$id": user.id},
                {"employer.$id": user.id}
            ]
        }

        if not include_archived:
            # Add condition to exclude archived chats
            if user.role.value == "applicant":
                query["is_archived_by_applicant"] = False
            else:
                query["is_archived_by_employer"] = False

        chats = await Chat.find(query).sort("-last_message_at").to_list()

        # Format response
        result = []
        for chat in chats:
            result.append(ChatResponse(
                id=str(chat.id),
                applicant_id=str(chat.applicant.ref.id),
                employer_id=str(chat.employer.ref.id),
                response_id=str(chat.response.ref.id),
                last_message_at=chat.last_message_at,
                last_message_text=chat.last_message_text,
                unread_count=chat.get_unread_count(user_id),
                is_archived=chat.is_archived_by(user_id)
            ))

        return result

    except Exception as e:
        logger.error(f"Error getting user chats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/{chat_id}", response_model=ChatDetailsResponse)
async def get_chat_details(chat_id: str, user_id: str):
    """Get chat with all messages."""
    try:
        chat = await Chat.get(chat_id)
        if not chat:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Chat not found"
            )

        # Verify user is participant
        if str(chat.applicant.ref.id) != user_id and str(chat.employer.ref.id) != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not a participant in this chat"
            )

        # Mark messages as read
        chat.mark_as_read(user_id)
        await chat.save()

        # Format messages
        messages = [
            MessageResponse(
                sender_id=msg.sender_id,
                text=msg.text,
                timestamp=msg.timestamp,
                is_read=msg.is_read,
                photo_file_id=msg.photo_file_id,
                document_file_id=msg.document_file_id
            )
            for msg in chat.messages
        ]

        return ChatDetailsResponse(
            id=str(chat.id),
            applicant_id=str(chat.applicant.ref.id),
            employer_id=str(chat.employer.ref.id),
            response_id=str(chat.response.ref.id),
            messages=messages,
            is_archived=chat.is_archived_by(user_id)
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting chat details: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/{chat_id}/messages", status_code=status.HTTP_201_CREATED)
async def send_message(chat_id: str, request: SendMessageRequest):
    """Send a message in a chat."""
    try:
        chat = await Chat.get(chat_id)
        if not chat:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Chat not found"
            )

        # Verify sender is participant
        if (str(chat.applicant.ref.id) != request.sender_id and
            str(chat.employer.ref.id) != request.sender_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not a participant in this chat"
            )

        # Add message
        chat.add_message(
            sender_id=request.sender_id,
            text=request.text,
            photo_file_id=request.photo_file_id,
            document_file_id=request.document_file_id
        )
        await chat.save()

        logger.info(f"Message sent in chat {chat_id} by user {request.sender_id}")

        return {"status": "success", "chat_id": str(chat.id)}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending message: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/create", response_model=ChatResponse, status_code=status.HTTP_201_CREATED)
async def create_or_get_chat(response_id: str):
    """Create a new chat or get existing one for a response."""
    try:
        response_obj = await Response.get(response_id)
        if not response_obj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Response not found"
            )

        # Check if chat already exists for this response
        existing_chat = await Chat.find_one({"response.$id": response_obj.id})
        if existing_chat:
            return ChatResponse(
                id=str(existing_chat.id),
                applicant_id=str(existing_chat.applicant.ref.id),
                employer_id=str(existing_chat.employer.ref.id),
                response_id=str(existing_chat.response.ref.id),
                last_message_at=existing_chat.last_message_at,
                last_message_text=existing_chat.last_message_text,
                unread_count=0,
                is_archived=False
            )

        # Create new chat
        chat = Chat(
            applicant=response_obj.applicant,
            employer=response_obj.employer,
            response=response_obj
        )
        await chat.create()

        logger.info(f"Chat created for response {response_id}")

        return ChatResponse(
            id=str(chat.id),
            applicant_id=str(chat.applicant.ref.id),
            employer_id=str(chat.employer.ref.id),
            response_id=str(chat.response.ref.id),
            last_message_at=chat.last_message_at,
            last_message_text=chat.last_message_text,
            unread_count=0,
            is_archived=False
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating chat: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.patch("/{chat_id}/archive", status_code=status.HTTP_200_OK)
async def archive_chat(chat_id: str, user_id: str):
    """Archive a chat for a user."""
    try:
        chat = await Chat.get(chat_id)
        if not chat:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Chat not found"
            )

        # Verify user is participant
        if str(chat.applicant.ref.id) != user_id and str(chat.employer.ref.id) != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not a participant in this chat"
            )

        # Archive for this user
        if str(chat.applicant.ref.id) == user_id:
            chat.is_archived_by_applicant = True
        else:
            chat.is_archived_by_employer = True

        await chat.save()

        logger.info(f"Chat {chat_id} archived by user {user_id}")

        return {"status": "success"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error archiving chat: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.patch("/{chat_id}/unarchive", status_code=status.HTTP_200_OK)
async def unarchive_chat(chat_id: str, user_id: str):
    """Unarchive a chat for a user."""
    try:
        chat = await Chat.get(chat_id)
        if not chat:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Chat not found"
            )

        # Verify user is participant
        if str(chat.applicant.ref.id) != user_id and str(chat.employer.ref.id) != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not a participant in this chat"
            )

        # Unarchive for this user
        if str(chat.applicant.ref.id) == user_id:
            chat.is_archived_by_applicant = False
        else:
            chat.is_archived_by_employer = False

        await chat.save()

        logger.info(f"Chat {chat_id} unarchived by user {user_id}")

        return {"status": "success"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error unarchiving chat: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
