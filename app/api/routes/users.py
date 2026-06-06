from fastapi import APIRouter, Depends, HTTPException, status

from app.core.exceptions import ConflictError, NotFoundError, AuthenticationError
from app.schemas.user import (
    UserRegisterRequest,
    UserLoginRequest,
    UserUpdateRequest,
    UserResponse,
    TokenResponse,
)
from app.services.user_service import UserService

router = APIRouter(prefix="/users", tags=["users"])


def get_user_service() -> UserService:
    return UserService()


@router.post(
    "",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
)
async def register(
    body: UserRegisterRequest,
    service: UserService = Depends(get_user_service),
) -> UserResponse:
    try:
        return await service.register(body)
    except ConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=exc.message)


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Login and get access token",
)
async def login(
    body: UserLoginRequest,
    service: UserService = Depends(get_user_service),
) -> TokenResponse:
    try:
        return await service.login(body)
    except AuthenticationError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=exc.message)


@router.get(
    "/{user_id}",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Get user profile by ID",
)
async def get_user(
    user_id: str,
    service: UserService = Depends(get_user_service),
) -> UserResponse:
    try:
        return await service.get_by_id(user_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message)


@router.patch(
    "/{user_id}",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Update user profile",
)
async def update_user(
    user_id: str,
    body: UserUpdateRequest,
    service: UserService = Depends(get_user_service),
) -> UserResponse:
    try:
        return await service.update(user_id, body)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message)
    except ConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=exc.message)


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete user",
)
async def delete_user(
    user_id: str,
    service: UserService = Depends(get_user_service),
) -> None:
    try:
        await service.delete(user_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message)