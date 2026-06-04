class AppError(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message

class NotFoundError(AppError):
    def __init__(self, resource: str, identifier: str | None = None) -> None:
        msg = f"{resource} not found"
        if identifier:
            msg += f": {identifier}"
        super().__init__(msg)
        self.resource = resource
        self.identifier = identifier


class ConflictError(AppError):pass
    # """Raised when a unique-constraint is violated (e.g. duplicate email)."""


class AuthenticationError(AppError):pass
    # """Raised when credentials are invalid."""


class AuthorizationError(AppError):pass
    # """Raised when the caller lacks permission."""


class ValidationError(AppError):pass
    # """Raised when business-level validation fails (not Pydantic schema)."""