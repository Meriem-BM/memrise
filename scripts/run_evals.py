from pathlib import Path

from memrise_evals.runners.local import load_jsonl_lines


def main() -> None:
    dataset = Path("packages/evals/src/memrise_evals/datasets/local_cases.jsonl")
    cases = load_jsonl_lines(dataset.read_text(encoding="utf-8").splitlines())
    print(f"Loaded {len(cases)} local evaluation cases. No benchmark results are claimed.")


if __name__ == "__main__":
    main()
