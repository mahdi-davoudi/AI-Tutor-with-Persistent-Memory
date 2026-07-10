# AI Tutor Backend

A **memory-aware AI Tutor** backend that provides personalized, adaptive learning support.

## Tech Stack

| Layer | Technology |
|---|---|
| Web Framework | FastAPI |
| Database | MongoDB |
| ODM | Beanie |
| LLM Provider | Anthropic API |
| Auth | JWT + bcrypt (`passlib`, `python-jose`) |
| Validation | Pydantic v2 |

## Architecture

### Request Flow

```
Route → Service → Repository → Database
```

### LLM (Chat) Flow

```
ChatService → PromptBuilder → LLMService → Save Response
```

- **Route**: HTTP concerns only (validate input via schemas, call the service, return the response).
- **Service**: Core business logic lives here.
- **Repository**: Database access only; no business logic allowed in this layer.
- **Domain**: Prompt-building and tutoring logic.

⚠️ **Hard rules:**
- Never access MongoDB directly from routes.
- Never call the LLM provider directly from routes.
- No business logic inside repositories.

## Project Structure

```
backend/                   ← run uvicorn from here
├── .env                   ← SECRET_KEY, ANTHROPIC_API_KEY, MONGODB_URL
├── requirements.txt
├── pyproject.toml
├── pytest.ini
└── app/
    ├── main.py            ← FastAPI app, lifespan, routers
    ├── core/
    │   ├── config.py      ← Pydantic Settings, .env loader
    │   ├── database.py    ← MongoDB + Beanie init
    │   ├── security.py    ← JWT, bcrypt
    │   └── exceptions.py  ← NotFoundError, ConflictError, ...
    ├── api/
    │   └── routes/
    │       ├── chat.py    ← POST /chat
    │       ├── users.py   ← POST /users, GET /users/{id}
    │       └── memory.py  ← POST/GET /memory/{user_id}
    ├── models/
    │   ├── user.py        ← Beanie Document: users collection
    │   ├── chat.py        ← ChatSession, Message documents
    │   └── memory.py      ← Memory document
    ├── schemas/
    │   ├── user.py        ← UserRegisterRequest, UserResponse, ...
    │   ├── chat.py        ← ChatMessageCreate, ChatMessageResponse
    │   └── memory.py      ← UpsertMemoryRequest, MemoryResponse
    ├── services/
    │   ├── user_service.py    ← register, login, get_by_id, update, delete
    │   ├── chat_service.py    ← send_message (load → prompt → LLM → save)
    │   ├── memory_service.py  ← upsert, list_memories, delete
    │   └── llm_service.py     ← generate() → Anthropic API
    ├── domain/
    │   ├── prompt_builder.py  ← build(history, message) → list[dict]
    │   └── session_policy.py  ← should_auto_title, generate_title
    ├── repositories/
    │   └── chat_repository.py ← get/create session, get/create message
    └── tests/
```

## Setup

```bash
cd backend
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate

pip install -r requirements.txt
```

Create a `.env` file in the `backend/` root with the following values:

```
SECRET_KEY=...
ANTHROPIC_API_KEY=...
MONGODB_URL=...
```

## Running the App

```bash
uvicorn app.main:app --reload
```

## Testing

```bash
pytest -v
```

**Testing rules:**
- New features require tests.
- Bug fixes should include a regression test.
- Existing test behavior must not break.

## Coding Standards

- **Async only.**
- **Type hints** are required.
- Follow **Pydantic v2** conventions.
- Business logic must stay in `services/`.
- Routes should remain thin.
- The repository layer handles database access only.
- The domain layer contains prompt and tutoring logic.
- Avoid duplicated logic.
- Follow existing project patterns before introducing new abstractions.

## API Guidelines

- Validate all requests with Pydantic schemas.
- Return consistent response models.
- Use custom exceptions from `core/exceptions.py`.
- Keep routes focused on HTTP concerns only.

## Current Focus

1. Backend stabilization
2. Memory intelligence layer
3. Learning profiles
4. Recommendation engine

## Additional Documentation

> ⚠️ The files below are referenced in `claude.md` but were not found under a `docs/` folder in the project's Google Drive structure — they still need to be created (or point me to their actual location so I can fix the links):

- `docs/ARCHITECTURE.md`
- `docs/ROADMAP.md`
- `docs/MEMORY_SYSTEM.md`
- `docs/API.md`