from fastapi import APIRouter, Depends, HTTPException, status

from core.config import get_settings
from core.exceptions import NotFoundError
from repositories.chat_repository import ChatRepository
from schemas.chat import ChatMessageCreate, ChatMessageResponse
from services.chat_service import ChatService
from services.llm_service import LLMService

router = APIRouter(prefix="/chat", tags=["chat"])


def get_chat_service() -> ChatService:
    settings = get_settings()
    return ChatService(
        repo=ChatRepository(),
        llm=LLMService(api_key=settings.anthropic_api_key),
    )


@router.post("", response_model=ChatMessageResponse, status_code=status.HTTP_200_OK)
async def send_message(
    body: ChatMessageCreate,
    service: ChatService = Depends(get_chat_service),
) -> ChatMessageResponse:
    """Send a message and receive an AI response."""
    try:
        # Find or create session for user
        from models.chat import ChatSession
        from repositories.chat_repository import ChatRepository

        repo = ChatRepository()
        sessions = await ChatSession.find(
            ChatSession.user_id == body.user_id
        ).sort(-ChatSession.updated_at).limit(1).to_list()

        if sessions:
            session = sessions[0]
        else:
            session = ChatSession(user_id=body.user_id)
            await repo.create_session(session)

        result = await service.send_message(
            session_id=str(session.id),
            user_id=body.user_id,
            content=body.message,
        )

        return ChatMessageResponse(
            response=result["assistant_message"].content,
            session_id=str(session.id),
            tokens_used=result["assistant_message"].tokens_used,
        )

    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred.",
        )