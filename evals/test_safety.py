import asyncio

from backend.app.config import Settings
from backend.app.regression import golden_cases
from backend.app.service import Platform


def test_golden_injection_cases_are_refused_without_tools():
    p = Platform(
        Settings(database_url="sqlite:///:memory:", seed_on_start=False, demo_latency_scale=0)
    )
    for case in golden_cases():
        if case["kind"] != "safety":
            continue
        t = asyncio.run(p.run(case["query"]))
        assert t["security_event"] and t["safe_response"] and not t["tool_calls"]
        assert t["evaluation"]["safety"] == 1
