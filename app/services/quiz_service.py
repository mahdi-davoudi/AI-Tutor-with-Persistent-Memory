from app.services.profile_service import ProfileService
from app.domain.quiz_generator import QuizGenerator
from app.services.llm_service import LLMService
from app.core.exceptions import NotFoundError
from app.models.quiz import Quiz

class QuizService:

    def __init__(self):
        self.llm = LLMService()
        self.generator = QuizGenerator(llm=self.llm)

    async def _pick_weakest_topic(self, user_id: str) -> tuple[str, list[str]]:
        profile = await ProfileService().get_summary(user_id)

        weak_candidates = [
            (name, tp.weak, tp.mastery)
            for name, tp in profile.topics.items()
            if tp.weak
        ]

        if not weak_candidates:
            raise NotFoundError("No weak areas found for this user yet.")

        weak_candidates.sort(key=lambda item: item[2]) 
        topic, weak_skills, _ = weak_candidates[0]
        return topic, weak_skills

    async def generate_quiz(self, user_id: str, topic: str | None = None) -> Quiz:
        
        # Step 1: Check Profile
        if topic:
            profile = await ProfileService().get_summary(user_id)
            tp = profile.topics.get(topic)
            weak_skills = tp.weak if tp else []
        else:
            topic, weak_skills = await self._pick_weakest_topic(user_id)

        # Step 2: Generate Quiz
        questions = await self.generator.generate(topic=topic, weak_skills=weak_skills)

        if not questions:
            raise NotFoundError("Could not generate a valid quiz for this topic.")

        # Step 3: Save
        quiz = Quiz(
            user_id=user_id,
            topic=topic,
            weak_skills=weak_skills,
            questions=questions,
        )
        await quiz.insert()
        return quiz

    async def get_recent(self, user_id: str, limit: int = 10) -> list[Quiz]:
        return (
            await Quiz.find(Quiz.user_id == user_id)
            .sort(-Quiz.created_at)
            .limit(limit)
            .to_list()
        )