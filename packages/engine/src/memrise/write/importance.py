# Rescue markers so short imperatives ("use pnpm") still pass the length check.
IMPORTANT_MARKERS = (
    "always",
    "never",
    "must",
    "use ",
    "uses ",
    "prefer",
    "preference",
    "decision",
    "constraint",
    "goal",
    "lesson",
    "now use",
    "we now",
)

MIN_CONTENT_TOKENS = 3


class ImportanceGate:
    """Recall-oriented pre-filter for extraction.

    The LLM extraction classifier is the precision layer; this gate exists only
    to avoid spending extraction calls on content that cannot hold durable
    knowledge (empty text, one-or-two-word acknowledgements). Anything longer is
    extracted and left to the classifier to accept or reject.
    """

    def should_extract(self, text: str) -> bool:
        stripped = text.strip()
        if not stripped:
            return False
        if len(stripped.split()) >= MIN_CONTENT_TOKENS:
            return True
        lowered = stripped.lower()
        return any(marker in lowered for marker in IMPORTANT_MARKERS)
