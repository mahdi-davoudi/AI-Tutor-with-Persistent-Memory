import pytest
from types import SimpleNamespace
from app.services.chat_service import ChatService

# Fake Repository

class FakeRepository:
    def __init__(self):
        self.messages = []
        self.session = SimpleNamespace(
            id="session1",
            user_id="user123",
            message_count=0,
            title="New Chat",
            summary=None,
            last_summarized_message_count=0,
        )

    async def get_or_create_latest_session(self, user_id):
        return self.session

    async def create_message(self, message):
        self.messages.append(message)
        return message

    async def get_messages(self, session_id, limit=20):
        return self.messages

    async def update_session(self, session):
        return session

# Fake LLM
class FakeLLM:

    async def generate(self, messages):
        return (
            "سلام، من پاسخ تستی هستم",
            15,
        )

@pytest.mark.asyncio
async def test_send_message():

    repo = FakeRepository()
    llm = FakeLLM()

    service = ChatService(
        repo=repo,
        llm=llm,
    )

    result = await service.send_message(
        session_id="session1",
        user_id="user123",
        content="سلام",
    )

    assert result["assistant_message"].content == "سلام، من پاسخ تستی هستم"

    assert len(repo.messages) == 2

    assert repo.messages[0].role == "user"

    assert repo.messages[1].role == "assistant"