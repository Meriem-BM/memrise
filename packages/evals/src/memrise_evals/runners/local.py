from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class EvaluationCase:
    id: str
    category: str
    prompt: str
    expected: list[str]


def load_jsonl_lines(lines: list[str]) -> list[EvaluationCase]:
    import json

    cases: list[EvaluationCase] = []
    for line in lines:
        if not line.strip():
            continue
        payload = json.loads(line)
        cases.append(
            EvaluationCase(
                id=str(payload["id"]),
                category=str(payload["category"]),
                prompt=str(payload["prompt"]),
                expected=[str(item) for item in payload["expected"]],
            )
        )
    return cases
