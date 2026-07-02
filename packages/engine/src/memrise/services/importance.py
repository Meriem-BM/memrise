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


class ImportanceGate:
    def should_extract(self, text: str) -> bool:
        lowered = text.lower()
        return any(marker in lowered for marker in IMPORTANT_MARKERS)
