from domain.states import InteractionKind

QUESTION_RESPONSES = ("ANSWER", "USE_RECOMMENDATION", "DELEGATE_REMAINING")
CONFIRMATION_RESPONSES = ("CONFIRM", "REQUEST_CHANGE")

TITLES = {
    InteractionKind.QUESTION: "Requirements question",
    InteractionKind.FINAL_INTENT_CONFIRMATION: "Final intent confirmation",
}

_ENGINE_KINDS = {
    "QUESTION": InteractionKind.QUESTION,
    "FINAL_INTENT_CONFIRMATION": InteractionKind.FINAL_INTENT_CONFIRMATION,
}


def allowed_responses(kind: InteractionKind) -> list[str]:
    if kind is InteractionKind.FINAL_INTENT_CONFIRMATION:
        return list(CONFIRMATION_RESPONSES)
    return list(QUESTION_RESPONSES)


def interaction_kind(engine_kind: str) -> InteractionKind:
    """Stable Kallula kind for an adapter-normalized interaction kind."""
    return _ENGINE_KINDS.get(engine_kind, InteractionKind.QUESTION)
