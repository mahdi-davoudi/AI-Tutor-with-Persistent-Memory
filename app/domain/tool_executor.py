import json
from app.services.profile_service import ProfileService


class ToolExecutor:

    def __init__(self, user_id: str):
        self.user_id = user_id

    async def execute(self, tool_name: str, arguments: dict) -> str:
        try:
            if tool_name == "get_learning_progress":
                return await self._get_learning_progress(arguments.get("topic", ""))
            if tool_name == "list_weak_areas":
                return await self._list_weak_areas()
            return json.dumps({"error": f"Unknown tool: {tool_name}"})
        except Exception as e:
            return json.dumps({"error": str(e)})

    async def _get_learning_progress(self, topic: str) -> str:
        profile = await ProfileService().get_summary(self.user_id)
        topic_key = topic.lower().strip()
        match = next(
            (name for name in profile.topics if name.lower() == topic_key),
            None,
        )
        if not match:
            return json.dumps({"topic": topic, "found": False})

        tp = profile.topics[match]
        return json.dumps({
            "topic": match,
            "found": True,
            "mastery": tp.mastery,
            "level": tp.level,
            "strong": tp.strong,
            "weak": tp.weak,
        })

    async def _list_weak_areas(self) -> str:
        profile = await ProfileService().get_summary(self.user_id)
        weak = [
            {"topic": name, "weak_skills": tp.weak}
            for name, tp in profile.topics.items()
            if tp.weak
        ]
        return json.dumps({"weak_areas": weak})