import os

import pytest


def database_url() -> str:
    url = os.getenv("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL is required for PostgreSQL integration tests")
    return url
