import httpx
from app.core.config import get_settings
import json  



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

    
    async def generate(
        self,
        messages: list[dict],
    ) -> tuple[str, int]:
        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.model_id,
            "messages": messages,
            "max_tokens": 512,
            "temperature": 0.7,
        }

        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(self.api_url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()

        text = data["choices"][0]["message"]["content"].strip()
        tokens = data["usage"]["total_tokens"]

        return text, tokens

    async def generate_structured(
        self,
        messages: list[dict],
        schema: dict,
        schema_name: str = "structured_response",
        max_tokens: int = 1500,
    ) -> tuple[dict, int]:
        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.model_id,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": 0.7,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": schema_name,
                    "schema": schema,
                    "strict": True,
                },
            },
        }

        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(self.api_url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()

        raw_content = data["choices"][0]["message"]["content"].strip()
        tokens = data["usage"]["total_tokens"]

        parsed = json.loads(raw_content)
        return parsed, tokens
    
    async def generate_with_tools(
        self,
        messages: list[dict],
        tools: list[dict],
    ) -> dict:
        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.model_id,
            "messages": messages,
            "max_tokens": 512,
            "temperature": 0.7,
            "tools": tools,
            "tool_choice": "auto",
        }

        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(self.api_url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()

        message = data["choices"][0]["message"]
        tokens = data["usage"]["total_tokens"]

        return {
            "content": message.get("content"),
            "tool_calls": message.get("tool_calls") or [],
            "tokens": tokens,
        }