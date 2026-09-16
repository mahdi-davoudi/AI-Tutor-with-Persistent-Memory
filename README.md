# AI Tutor with Persistent Memory

A **memory-aware AI Tutor** backend that personalizes tutoring from long-term memory, a learning profile, uploaded documents, and the current conversation.

All 7 roadmap phases are implemented.

## What it does

- Saves facts about the learner (skill level, preferences, weak/strong areas).
- Retrieves those facts with **semantic search** (embeddings + Qdrant), not just keyword/importance.
- Builds a **learning profile** (mastery, level, preferred teaching style).
- Injects memory + profile + document excerpts + a rolling session summary into every prompt.
- Supports **tool/function calling** and **structured LLM output**.
- Recommends next topics and generates quizzes from the learner’s history.
- Ingests PDFs / text notes and answers from them (**RAG**).

## Tech Stack

| Layer | Technology |
|---|---|
| Web | FastAPI + Uvicorn |
| Database | MongoDB + Beanie (Motor) |
| Vector store | Qdrant (`memory_vectors`, `document_chunks`) |
| Embeddings | `sentence-transformers/all-MiniLM-L6-v2` (384-dim, cosine) |
| LLM | Hugging Face router (`/v1/chat/completions`) — structured JSON + tools |
| Auth | JWT + bcrypt |
| Validation | Pydantic v2 |
| PDF ingest | pypdf |

> `ANTHROPIC_API_KEY` still exists in settings for historical reasons. The live chat path uses **Hugging Face**.

## Architecture

### Request flow

Route → Service → Repository / Domain → MongoDB + Qdrant


- **Route**: HTTP only (auth, schemas, status codes).
- **Service**: business logic.
- **Repository**: database access only. Services must not call `Model.find(...)`.
- **Domain**: prompt building, memory extraction, skill tracking, tools.

### One chat turn

ChatService.send_message
→ get or create latest session          (ChatRepository)
→ save user message
→ load recent history
→ embed the user message
→ semantic memory search (Qdrant → Mongo)
→ learning-profile summary
→ document chunk search (RAG)
→ rolling session summary
→ PromptBuilder
→ LLM with tools (max 3 iterations)
→ save assistant message
→ extract memories → upsert Mongo + sync Qdrant
→ maybe refresh session summary
text### Embeddings and Qdrant

| Collection | What is stored | Query |
|---|---|---|
| `memory_vectors` | `key: value` of each memory, filtered by `user_id` | similar memories for the current message |
| `document_chunks` | text chunks of uploaded files, filtered by `user_id` | RAG excerpts above `document_relevance_threshold` |

Vector writes are **best-effort**: a Qdrant failure never rolls back a successful Mongo write. If semantic search fails, chat falls back to importance-sorted memories.

## Project Structure
backend/                          ← run uvicorn and pytest from here
├── .env
├── requirements.txt
├── pyproject.toml
├── pytest.ini
├── README.md
└── app/
├── main.py
├── core/
│   ├── config.py               # Pydantic Settings
│   ├── database.py             # MongoDB + Beanie
│   ├── vector_db.py            # Async Qdrant + collection bootstrap
│   ├── security.py             # JWT, bcrypt
│   └── exceptions.py
├── api/routes/
│   ├── users.py
│   ├── chat.py
│   ├── memory.py
│   ├── profile.py
│   ├── recommendation.py
│   ├── quiz.py
│   └── documents.py
├── models/                     # Beanie documents
├── schemas/                    # Pydantic v2
├── services/
│   ├── chat_service.py
│   ├── memory_service.py       # CRUD + semantic search + vector sync
│   ├── embedding_service.py    # sentence-transformers encode
│   ├── document_service.py     # ingest + RAG
│   ├── llm_service.py          # HF chat / structured / tools
│   ├── profile_service.py
│   ├── recommendation_service.py
│   ├── quiz_service.py
│   └── user_service.py
├── domain/
│   ├── prompt_builder.py
│   ├── memory_extractor.py
│   ├── session_policy.py
│   ├── session_summarizer.py
│   ├── skill_tracker.py
│   ├── mastery_estimator.py
│   ├── recommendation_engine.py
│   ├── quiz_generator.py
│   ├── chunker.py
│   ├── tools.py
│   └── tool_executor.py
├── repositories/
│   ├── chat_repository.py
│   └── recommendation_repository.py
└── tests/
text## Prerequisites

- Python 3.11+ (developed and tested on 3.13)
- MongoDB running locally (default `mongodb://localhost:27017`)
- Qdrant running locally (default `http://localhost:6333`)
- A Hugging Face token with access to the configured model

Local Qdrant (example):

```bash
docker run -p 6333:6333 -p 6334:6334 qdrant/qdrant
Setup
Bashcd backend
python -m venv venv
# Windows:
venv\Scripts\activate
# macOS / Linux:
source venv/bin/activate

pip install -r requirements.txt
Create backend/.env:
textAPP_ENV=development
SECRET_KEY=replace-with-a-long-random-string
MONGODB_URL=mongodb://localhost:27017
DATABASE_NAME=chatapp

HF_API_TOKEN=hf_...
HF_MODEL_ID=mistralai/Mistral-7B-Instruct-v0.2

QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=
QDRANT_COLLECTION_NAME=memory_vectors
QDRANT_DOCUMENT_COLLECTION_NAME=document_chunks
EMBEDDING_DIM=384
EMBEDDING_MODEL_NAME=sentence-transformers/all-MiniLM-L6-v2
DOCUMENT_RELEVANCE_THRESHOLD=0.35
The first chat request downloads the embedding model from Hugging Face (all-MiniLM-L6-v2). That can take a minute once.
If Hugging Face calls time out, check system HTTP proxy env vars. LLMService should use a longer read timeout and trust_env=False so Windows proxies are not applied blindly.
Run
From backend/:
Bashuvicorn app.main:app --reload

Health: http://127.0.0.1:8000/health
Swagger: http://127.0.0.1:8000/docs

Register / login, click Authorize in Swagger, then call the other endpoints.
Test
From backend/:
Bashpytest -v
Do not run pytest from inside app/. Imports are app.services..., app.domain....
API (prefix /api/v1 unless noted)





































AreaExamplesUsersregister, login, get/update userChatPOST /api/v1/chatMemorylist / upsert / delete memoriesProfileget / generate learning profileQuizgenerate quizDocumentsupload, list, deleteRecommendationsGET /recommendations/{user_id} (no /api/v1 prefix in current router)
Exact paths and bodies: open /docs.
Coding Standards

Async only, type hints required, Pydantic v2 only.
Business logic in services or domain. Routes stay thin.
Repository handles Mongo access. Do not call Beanie find / insert from services.
New features need tests. Bug fixes should include a regression test.

Phase map





































PhaseCapability1Backend layout, auth, CRUD, exceptions2Memory extraction + persistence3Learning profiles (skill tracker + mastery)4Prompt intelligence (memories + profile in system prompt)5Recommendation engine6Structured outputs + tool calling7Qdrant, embeddings, document RAG, session continuity
More docs

docs/ARCHITECTURE.md
docs/ROADMAP.md
