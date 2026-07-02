from memrise_evals.metrics import critical_memory_recall, task_success, update_accuracy


def test_task_success() -> None:
    assert task_success([True, False, True]) == 2 / 3


def test_update_accuracy() -> None:
    assert update_accuracy({"pnpm"}, {"pnpm", "npm"}) == 0.5


def test_critical_recall() -> None:
    assert critical_memory_recall({"lockfile"}, {"lockfile"}) == 1.0
