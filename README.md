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
