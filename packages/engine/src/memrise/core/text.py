def normalize_lookup(value: str) -> str:
    return " ".join(value.strip().lower().split())


def search_terms(text: str) -> set[str]:
    """Lowercased, punctuation-trimmed terms shared by retrieval scoring and channel queries."""
    return {part.strip(".,:;!?()[]{}\"'").lower() for part in text.split() if part.strip()}
