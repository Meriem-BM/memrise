import re


class ApproximateTokenCounter:
    """Approximation until a Qwen tokenizer is selected and validated."""

    _pattern = re.compile(r"\w+|[^\w\s]", re.UNICODE)

    def count(self, text: str) -> int:
        if not text:
            return 0
        return max(1, len(self._pattern.findall(text)))
