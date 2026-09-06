import os

import pytest

os.environ["DEEPEVAL_TELEMETRY_OPT_OUT"] = "YES"
os.environ["CONFIDENT_METRIC_LOGGING_VERBOSE"] = "0"

from backend.app.config import Settings
from backend.app.service import Platform


@pytest.fixture
def platform():
    p = Platform(
        Settings(database_url="sqlite:///:memory:", seed_on_start=False, demo_latency_scale=0)
    )
    yield p
    p.store.engine.dispose()
