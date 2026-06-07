import httpx
from app.core.config import get_settings


class LLMService:

    SYSTEM_PROMPT = (
        "You are a helpful AI tutor. "
        "Help students learn and understand concepts clearly. "
        "Be concise, friendly, and educational."
    )

    def __init__(self, api_key: str = ""):
        settings = get_settings()
        self.api_token = settings.hf_api_token
        self.model_id = settings.hf_model_id
        self.api_url = "https://router.huggingface.co/v1/chat/completions"

    async def generate(self, messages: list[dict]) -> tuple[str, int]:
        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.model_id,
            "messages": [
                {"role": "system", "content": self.SYSTEM_PROMPT},
                *messages,
            ],
            "max_tokens": 512,
            "temperature": 0.7,
        }

        async with httpx.AsyncClient(
            timeout=60
        ) as client:
            response = await client.post(self.api_url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()

        text = data["choices"][0]["message"]["content"].strip()
        tokens = data["usage"]["total_tokens"]

        return text, tokens