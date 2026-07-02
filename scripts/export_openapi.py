import json
from pathlib import Path

from memrise_api.main import create_app


def main() -> None:
    schema = create_app().openapi()
    output = Path("contracts/openapi.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
