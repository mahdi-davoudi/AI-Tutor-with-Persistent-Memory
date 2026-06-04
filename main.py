"""
app/main.py
────────────
FastAPI application entry point.

What lives here
---------------
- Application factory (`create_app`)
- Lifespan context manager (startup + shutdown hooks)
- Middleware registration (CORS, logging)
- Router registration
- Service wiring (dependency injection via app.state)

What does NOT live here
-----------------------
- Business logic (→ services/)
- Database models (→ models/)
- Schemas (→ schemas/)

Running the server
------------------
    uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.database import connect_db, close_db
from app.services.llm_service import build_llm_service
from app.services.chat_service import ChatService
from app.services.memory_service import MemoryService
from app.api.routes import users, chat, memory

# ── Logging configuration ──────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.DEBUG if settings.app_env == "development" else logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ── Lifespan ───────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Manage application lifecycle resources.

    Startup
    -------
    1. Connect to MongoDB and initialise Beanie.
    2. Build and store services on app.state so routes can inject them
       via `request.app.state.<service>`.

    Shutdown
    --------
    1. Close the MongoDB connection gracefully.
    """
    logger.info("=== Application starting up (env=%s) ===", settings.app_env)

    # --- Startup ---
    await connect_db()

    # Build services once; they are singletons for the lifetime of the process.
    llm_service = build_llm_service()
    app.state.llm_service = llm_service
    app.state.chat_service = ChatService(llm_service=llm_service)
    app.state.memory_service = MemoryService()

    logger.info("Services initialised.  Application ready.")

    yield  # ← server runs here

    # --- Shutdown ---
    logger.info("=== Application shutting down ===")
    await close_db()


# ── Application factory ────────────────────────────────────────────────────────

def create_app() -> FastAPI:
    """
    Build and configure the FastAPI application.

    Separating app creation into a factory function makes it easy to
    instantiate the app in tests with different settings.
    """
    application = FastAPI(
        title="Long-Term Memory LLM Chatbot API",
        description=(
            "Production-grade chatbot backend with multi-user support, "
            "MongoDB persistence, and a foundation for long-term memory."
        ),
        version="1.0.0",
        docs_url="/docs",       # Swagger UI
        redoc_url="/redoc",     # ReDoc
        lifespan=lifespan,
    )

    # ── Middleware ─────────────────────────────────────────────────────────────

    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],        # Restrict in production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Global exception handler ───────────────────────────────────────────────

    @application.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled exception on %s %s", request.method, request.url)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "An internal server error occurred."},
        )

    # ── Routers ────────────────────────────────────────────────────────────────

    application.include_router(users.router)
    application.include_router(chat.router)
    application.include_router(memory.router)

    # ── Health check ───────────────────────────────────────────────────────────

    @application.get("/health", tags=["System"], summary="Health check")
    async def health() -> dict:
        """Returns 200 OK when the service is running."""
        return {"status": "ok", "env": settings.app_env}

    return application


# ── Singleton app instance ─────────────────────────────────────────────────────
# Uvicorn imports this object directly: `uvicorn app.main:app`

app: FastAPI = create_app()