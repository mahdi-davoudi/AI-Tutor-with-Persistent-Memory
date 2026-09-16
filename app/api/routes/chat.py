import logging
from fastapi import APIRouter, Depends, HTTPException, status

from app.core.config import get_settings
from app.core.exceptions import NotFoundError
from app.core.security import get_current_user
from app.domain.memory_extractor import MemoryExtractor
from app.models.user import User
from app.repositories.chat_repository import ChatRepository
from app.schemas.chat import ChatMessageCreate, ChatMessageResponse
from app.services.chat_service import ChatService
from app.services.document_service import DocumentService
from app.services.llm_service import LLMService
from app.services.memory_service import MemoryService
from app.services.profile_service import ProfileService

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/chat",
    tags=["chat"],
)


def get_chat_service() -> ChatService:
    settings = get_settings()
    llm = LLMService(api_key=settings.anthropic_api_key)

    return ChatService(
        repo=ChatRepository(),
        llm=llm,
        memory_service=MemoryService(),
        memory_extractor=MemoryExtractor(llm=llm),
        document_service=DocumentService(),
        profile_service=ProfileService(),
    )


@router.post(
    "",
    response_model=ChatMessageResponse,
    status_code=status.HTTP_200_OK,
)
async def send_message(
    body: ChatMessageCreate,
    service: ChatService = Depends(get_chat_service),
    current_user: User = Depends(get_current_user),
) -> ChatMessageResponse:
    if str(current_user.id) != body.user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed.")

    try:
        result = await service.send_message(
            user_id=body.user_id,
            content=body.message,
        )
        return ChatMessageResponse(
            response=result["assistant_message"].content,
            session_id=result["session_id"],
            tokens_used=result["assistant_message"].tokens_used,
        )
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        )
    except NotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=exc.message,
        )
    except Exception:
        logger.exception("send_message failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )