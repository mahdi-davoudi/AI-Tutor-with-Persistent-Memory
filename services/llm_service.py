"""
app/services/llm_service.py
────────────────────────────
Thin wrapper around a HuggingFace text-generation pipeline.

Design decisions
----------------
1. The service is initialised once at startup and reused for every request,
   keeping the model in memory (avoids reload latency per request).
2. A MockLLMService is provided so the rest of the stack can be developed
   and tested without GPU / large model downloads.
3. Both implementations share the same abstract interface (`BaseLLMService`)
   so they can be swapped via dependency injection with zero changes in
   callers.
4. The `generate` method is `async` even though HuggingFace inference is
   currently synchronous; the blocking call is offloaded to a thread pool
   via `asyncio.to_thread` to keep the FastAPI event loop unblocked.

Future integration points
--------------------------
- Swap the local pipeline for an API-backed model (OpenAI-compatible,
  HuggingFace Inference Endpoints) by implementing a new subclass.
- Add streaming support by yielding tokens from `generate_stream`.
- Add prompt-caching or batching layers here without touching call sites.
"""

import asyncio
import logging
from abc import ABC, abstractmethod

from app.core.config import settings

logger = logging.getLogger(__name__)


# ── Abstract interface ─────────────────────────────────────────────────────────

class BaseLLMService(ABC):
    """Contract that every LLM backend must satisfy."""

    @abstractmethod
    async def generate(self, prompt: str) -> str:
        """
        Generate a text completion for `prompt`.

        Parameters
        ----------
        prompt : str
            The fully-formatted prompt (system + history + user message).

        Returns
        -------
        str
            The assistant's reply text only (no prompt echo).
        """


# ── Mock implementation ────────────────────────────────────────────────────────

class MockLLMService(BaseLLMService):
    """
    Returns a deterministic canned response.

    Useful for:
    - Local development without a GPU
    - Unit / integration tests
    - CI pipelines
    """

    async def generate(self, prompt: str) -> str:
        logger.debug("[MockLLMService] Generating mock response.")
        # Simulate a tiny async delay so callers behave the same as with a
        # real model (avoids accidentally synchronous code paths).
        await asyncio.sleep(0.05)
        return (
            "I'm a mock assistant. "
            "Set LLM_USE_MOCK=false and ensure the model is available to use the real model."
        )


# ── Real HuggingFace implementation ───────────────────────────────────────────

class HuggingFaceLLMService(BaseLLMService):
    """
    Wraps a HuggingFace `text-generation` pipeline.

    The model is loaded once during `__init__`.  Inference is offloaded to a
    thread pool so the async event loop is never blocked.
    """

    def __init__(self) -> None:
        # Import here so the import is skipped entirely when using the mock.
        from transformers import pipeline, AutoTokenizer, AutoModelForCausalLM
        import torch

        model_name = settings.llm_model_name
        logger.info("Loading model '%s' …", model_name)

        # Determine device: use GPU if available, fall back to CPU.
        device = 0 if torch.cuda.is_available() else -1
        logger.info("Using device: %s", "GPU:0" if device == 0 else "CPU")

        self._tokenizer = AutoTokenizer.from_pretrained(model_name)
        self._pipeline = pipeline(
            task="text-generation",
            model=model_name,
            tokenizer=self._tokenizer,
            device=device,
            # Recommended for inference-only use
            torch_dtype=torch.float16 if device == 0 else torch.float32,
        )
        logger.info("Model '%s' loaded successfully.", model_name)

    def _sync_generate(self, prompt: str) -> str:
        """
        Synchronous inference call.  Runs inside a thread pool via
        `asyncio.to_thread` so the event loop is not blocked.
        """
        outputs = self._pipeline(
            prompt,
            max_new_tokens=settings.llm_max_new_tokens,
            temperature=settings.llm_temperature,
            do_sample=True,
            pad_token_id=self._tokenizer.eos_token_id,
            # Return only the newly generated tokens (not the full prompt)
            return_full_text=False,
        )
        # The pipeline returns a list of dicts; grab the generated text.
        return outputs[0]["generated_text"].strip()

    async def generate(self, prompt: str) -> str:
        """Async wrapper around the synchronous pipeline call."""
        return await asyncio.to_thread(self._sync_generate, prompt)


# ── Factory ────────────────────────────────────────────────────────────────────

def build_llm_service() -> BaseLLMService:
    """
    Instantiate and return the appropriate LLM service based on configuration.

    Called once at application startup (see main.py lifespan).
    """
    if settings.llm_use_mock:
        logger.info("LLM_USE_MOCK=true → using MockLLMService.")
        return MockLLMService()

    logger.info("LLM_USE_MOCK=false → loading HuggingFaceLLMService.")
    return HuggingFaceLLMService()