def ratio(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return numerator / denominator


def task_success(successes: list[bool]) -> float:
    return ratio(sum(1 for item in successes if item), len(successes))


def preference_recall(expected: set[str], recalled: set[str]) -> float:
    return ratio(len(expected & recalled), len(expected))


def update_accuracy(expected_current: set[str], actual_current: set[str]) -> float:
    return ratio(len(expected_current & actual_current), len(expected_current | actual_current))


def conflict_resolution_accuracy(resolved: int, total_conflicts: int) -> float:
    return ratio(resolved, total_conflicts)


def critical_memory_recall(expected_critical: set[str], recalled_critical: set[str]) -> float:
    return ratio(len(expected_critical & recalled_critical), len(expected_critical))


def stale_memory_harm_rate(harmful_stale_uses: int, retrievals: int) -> float:
    return ratio(harmful_stale_uses, retrievals)


def useful_recall_precision(useful_recalled: int, recalled_total: int) -> float:
    return ratio(useful_recalled, recalled_total)


def context_tokens(token_counts: list[int]) -> int:
    return sum(token_counts)


def write_latency(milliseconds: list[float]) -> float:
    return sum(milliseconds) / len(milliseconds) if milliseconds else 0.0


def retrieval_latency(milliseconds: list[float]) -> float:
    return sum(milliseconds) / len(milliseconds) if milliseconds else 0.0
