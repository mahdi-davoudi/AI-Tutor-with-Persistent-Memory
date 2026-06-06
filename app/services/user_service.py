from datetime import timedelta, timezone, datetime

from beanie.operators import Set

from core.config import get_settings
from core.exceptions import AuthenticationError, ConflictError, NotFoundError
from core.security import hash_password, verify_password, create_access_token
from models.user import User
from schemas.user import (
    UserRegisterRequest,
    UserLoginRequest,
    UserUpdateRequest,
    UserResponse,
    TokenResponse,
)


def _to_response(user: User) -> UserResponse:
    return UserResponse(
        id=str(user.id),
        email=user.email,
        username=user.username,
        is_active=user.is_active,
        is_verified=user.is_verified,
        created_at=user.created_at,
    )


class UserService:
    # Auth
    # ------------------------------------------------------------------
    async def register(self, payload: UserRegisterRequest) -> UserResponse:
        if await User.find_one(User.email == payload.email):
            raise ConflictError("Email already registered.")
        if await User.find_one(User.username == payload.username):
            raise ConflictError("Username already taken.")

        user = User(
            email=payload.email,
            username=payload.username,
            hashed_password=hash_password(payload.password),
        )
        await user.insert()
        return _to_response(user)

    async def login(self, payload: UserLoginRequest) -> TokenResponse:
        user = await User.find_one(User.email == payload.email)
        if not user or not verify_password(payload.password, user.hashed_password):
            raise AuthenticationError("Invalid email or password.")
        if not user.is_active:
            raise AuthenticationError("Account is disabled.")

        settings = get_settings()
        token = create_access_token(
            subject=str(user.id),
            expires_delta=timedelta(minutes=settings.access_token_expire_minutes),
        )
        return TokenResponse(
            access_token=token,
            expires_in=settings.access_token_expire_minutes * 60,
        )

    # CRUD
    # ------------------------------------------------------------------

    async def get_by_id(self, user_id: str) -> UserResponse:
        user = await User.get(user_id)
        if not user:
            raise NotFoundError("User", user_id)
        return _to_response(user)

    async def get_by_email(self, email: str) -> User:
        user = await User.find_one(User.email == email)
        if not user:
            raise NotFoundError("User", email)
        return user

    async def update(self, user_id: str, payload: UserUpdateRequest) -> UserResponse:
        user = await User.get(user_id)
        if not user:
            raise NotFoundError("User", user_id)

        updates: dict = {"updated_at": datetime.now(timezone.utc)}

        if payload.email and payload.email != user.email:
            if await User.find_one(User.email == payload.email):
                raise ConflictError("Email already in use.")
            updates["email"] = payload.email

        if payload.username and payload.username != user.username:
            if await User.find_one(User.username == payload.username):
                raise ConflictError("Username already taken.")
            updates["username"] = payload.username

        await user.update(Set(updates))
        await user.sync()
        return _to_response(user)

    async def delete(self, user_id: str) -> None:
        user = await User.get(user_id)
        if not user:
            raise NotFoundError("User", user_id)
        await user.delete()