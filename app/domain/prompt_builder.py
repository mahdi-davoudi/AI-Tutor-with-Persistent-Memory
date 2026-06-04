class PromptBuilder:

    @staticmethod
    def build(history, new_message: str):

        messages = [
            {"role": m["role"], "content": m["content"]}
            for m in history
            if m["role"] in ("user", "assistant")
        ]

        messages.append({
            "role": "user",
            "content": new_message
        })

        return messages