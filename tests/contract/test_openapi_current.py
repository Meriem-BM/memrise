import json
from pathlib import Path

from memrise_api.main import create_app


def test_openapi_export_is_current() -> None:
    expected = json.loads(Path("docs/openapi.json").read_text(encoding="utf-8"))
    actual = create_app().openapi()
    assert expected == actual
