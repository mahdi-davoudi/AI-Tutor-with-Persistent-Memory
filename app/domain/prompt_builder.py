from typing import Optional
from app.schemas.learning_profile import LearningProfileSummary


class PromptBuilder:

    @staticmethod
    def build(
        history: list,
        new_message: str,
        memories: list = None,
        profile: Optional[LearningProfileSummary] = None,
    ) -> list[dict]:

        system_prompt = PromptBuilder._build_system_prompt(memories, profile)
        messages = [{"role": "system", "content": system_prompt}]

        for m in history:
            if m["role"] in ("user", "assistant"):
                messages.append({"role": m["role"], "content": m["content"]})

        messages.append({"role": "user", "content": new_message})
        return messages

    @staticmethod
    def _build_system_prompt(
        memories: list = None,
        profile: Optional[LearningProfileSummary] = None,
    ) -> str:

        sections = [
            "You are a personalized AI tutor. "
            "Adapt your teaching style and depth based on the user's known level."
        ]

        # --- Learning Profile ---
        if profile and profile.topics:
            lines = []
            for topic, tp in profile.topics.items():
                strong = ", ".join(tp.strong) if tp.strong else "—"
                weak   = ", ".join(tp.weak)   if tp.weak   else "—"
                lines.append(
                    f"  - {topic}: level={tp.level}, mastery={tp.mastery:.0%}, "
                    f"strong=[{strong}], weak=[{weak}]"
                )

            style_line = (
                f"\n  Preferred style: {profile.preferred_style}"
                if profile.preferred_style
                else ""
            )

            sections.append(
                "User Learning Profile:\n"
                + "\n".join(lines)
                + style_line
            )

        # --- Raw Memories ---
        if memories:
            mem_lines = [f"  - {m.key}: {m.value}" for m in memories]
            sections.append("User Memory Notes:\n" + "\n".join(mem_lines))

        return "\n\n".join(sections)