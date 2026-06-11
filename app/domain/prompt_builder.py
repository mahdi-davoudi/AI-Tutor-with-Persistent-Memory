class PromptBuilder:

    @staticmethod
    def build(history: list, new_message: str, memories: list = None) -> list[dict]:

        # 1. Build system prompt
        memory_section = ""
        if memories:
            lines = [f"- {m.key} = {m.value}" for m in memories]
            memory_section = "\n\nUser Memories:\n" + "\n".join(lines)

        system_prompt = f"You are a personalized AI tutor. Adapt your explanations based on the user's known level.{memory_section}"

        messages = [{"role": "system", "content": system_prompt}]

        # 2. Add chat history
        for m in history:
            if m["role"] in ("user", "assistant"):
                messages.append({"role": m["role"], "content": m["content"]})

        # 3. Add current message
        messages.append({"role": "user", "content": new_message})

        return messages