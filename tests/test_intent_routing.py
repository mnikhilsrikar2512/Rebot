from chatbot_api.services.intent_classifier import classify_intent


def test_intent_classifier_improvement() -> None:
    assert classify_intent("How can I improve this website flow?") == "improvement"


def test_intent_classifier_research() -> None:
    assert classify_intent("Research similar websites and benchmark patterns") == "research"


def test_intent_classifier_troubleshooting() -> None:
    assert classify_intent("Checkout is broken and shows error") == "troubleshooting"
