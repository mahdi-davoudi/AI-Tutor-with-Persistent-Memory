class SessionPolicy:

    @staticmethod
    def should_auto_title(message_count: int) -> bool:
        return message_count == 0

    @staticmethod
    def generate_title(message: str) -> str:
        return message[:60] + ("…" if len(message) > 60 else "")