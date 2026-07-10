from fastapi import APIRouter, Depends, HTTPException, status
from app.core.config import get_settings
from app.core.exceptions import NotFoundError
from app.domain.memory_extractor import MemoryExtractor
from app.models.chat import ChatSession
from app.repositories.chat_repository import ChatRepository
from app.schemas.chat import ChatMessageCreate, ChatMessageResponse
from app.services.chat_service import ChatService
from app.services.llm_service import LLMService
from app.services.memory_service import MemoryService

router = APIRouter(
    prefix="/chat",
    tags=["chat"],
)


def get_chat_service() -> ChatService:
    settings = get_settings()

    llm = LLMService(
        api_key=settings.anthropic_api_key,
    )

    memory_service = MemoryService()

    memory_extractor = MemoryExtractor(
        llm=llm,
    )

    return ChatService(
        repo=ChatRepository(),
        llm=llm,
        memory_service=memory_service,
        memory_extractor=memory_extractor,
    )


@router.post(
    "",
    response_model=ChatMessageResponse,
    status_code=status.HTTP_200_OK,
)
async def send_message(
    body: ChatMessageCreate,
    service: ChatService = Depends(get_chat_service),
) -> ChatMessageResponse:
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

    except Exception as exc:
        import traceback

        traceback.print_exc()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )