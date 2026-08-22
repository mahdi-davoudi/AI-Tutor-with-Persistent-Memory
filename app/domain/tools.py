GET_LEARNING_PROGRESS_TOOL = {
    "type": "function",
    "function": {
        "name": "get_learning_progress",
        "description": (
            "Get the user's current mastery level, skill level, and strong/weak "
            "skills for a specific topic they are learning."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "description": "The topic name to look up, e.g. 'python', 'recursion'.",
                },
            },
            "required": ["topic"],
        },
    },
}

LIST_WEAK_AREAS_TOOL = {
    "type": "function",
    "function": {
        "name": "list_weak_areas",
        "description": (
            "List all topics and skills the user is currently weak in, "
            "across their entire learning profile."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },
}

AVAILABLE_TOOLS = [GET_LEARNING_PROGRESS_TOOL, LIST_WEAK_AREAS_TOOL]