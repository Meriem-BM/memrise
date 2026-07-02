import re

_RELATION_HINTS = re.compile(
    r"\b(use[sd]?|depend(?:s|ed|ency)?|replace[sd]?|work(?:s|ed|ing)? on|belong(?:s|ed)? to|"
    r"own(?:s|ed|er)?|cause[sd]?|block(?:ed|s)? by|deploy(?:s|ed)? on|connect(?:s|ed)? to|"
    r"related to|who|what|which)\b",
    re.IGNORECASE,
)


_GENERIC_PROMPTS = re.compile(
    r"\b(format|style|tone|write|explain how to|summarize|translate)\b",
    re.IGNORECASE,
)


def should_use_graph_retrieval(query: str) -> bool:
    normalized = query.strip().lower()
    if not normalized:
        return False
    if _GENERIC_PROMPTS.search(normalized):
        return False
    if _RELATION_HINTS.search(normalized):
        return True
    if normalized.endswith("?"):
        return True
    tokens = [token for token in re.split(r"[^\w]+", normalized) if token]
    return len(tokens) >= 2 and any(token[0].isupper() for token in query.split())
