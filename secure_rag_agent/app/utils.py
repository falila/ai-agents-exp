import re


def filter_think_tags(response: str) -> str:
    """Remove chain-of-thought markers from generated responses."""
    return re.sub(r"<think>.*?</think>", "", response, flags=re.DOTALL).strip()
