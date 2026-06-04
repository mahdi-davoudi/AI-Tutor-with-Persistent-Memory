from anthropic import AsyncAnthropic


class LLMService:

    def __init__(self, api_key: str):
        self.client = AsyncAnthropic(api_key=api_key)

    async def generate(self, messages: list[dict]) -> tuple[str, int]:

        response = await self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            system="You are a helpful assistant.",
            messages=messages,
        )

        text = response.content[0].text
        tokens = response.usage.output_tokens

        return text, tokens