import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.core.database import connect_db, disconnect_db
from app.core.exceptions import (
    AppError,
    AuthenticationError,
    AuthorizationError,
    ConflictError,
    NotFoundError,
    ValidationError,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up...")
    await connect_db(app)
    yield
    logger.info("Shutting down...")
    await disconnect_db(app)


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="AI Tutor with Persistent Memory",
        description="Personalized learning system with long-term memory",
        version="1.0.0",
        debug=settings.debug,
        lifespan=lifespan,
    )

    # CORS
    # ------------------------------------------------------------------ 
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if not settings.is_production else [],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Exception handlers
    # ------------------------------------------------------------------ 
    @app.exception_handler(NotFoundError)
    async def not_found_handler(request: Request, exc: NotFoundError):
        return JSONResponse(
            status_code=404,
            content={"detail": exc.message},
        )

    @app.exception_handler(ConflictError)
    async def conflict_handler(request: Request, exc: ConflictError):
        return JSONResponse(
            status_code=409,
            content={"detail": exc.message},
        )

    @app.exception_handler(AuthenticationError)
    async def auth_error_handler(request: Request, exc: AuthenticationError):
        return JSONResponse(
            status_code=401,
            content={"detail": exc.message},
        )

    @app.exception_handler(AuthorizationError)
    async def authz_error_handler(request: Request, exc: AuthorizationError):
        return JSONResponse(
            status_code=403,
            content={"detail": exc.message},
        )

    @app.exception_handler(ValidationError)
    async def validation_error_handler(request: Request, exc: ValidationError):
        return JSONResponse(
            status_code=422,
            content={"detail": exc.message},
        )

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError):
        return JSONResponse(
            status_code=400,
            content={"detail": exc.message},
        )

    # Routers
    # ------------------------------------------------------------------
    from app.api.routes.users import router as users_router
    from app.api.routes.chat import router as chat_router
    from app.api.routes.memory import router as memory_router
    from app.api.routes.profile import router as profile_router

    app.include_router(users_router,  prefix="/api/v1")
    app.include_router(chat_router,   prefix="/api/v1")
    app.include_router(memory_router, prefix="/api/v1")  
    app.include_router(profile_router, prefix="/api/v1")

    # Health check
    # ------------------------------------------------------------------
    @app.get("/health", tags=["system"])
    async def health():
        return {"status": "ok"}

    return app


app = create_app()