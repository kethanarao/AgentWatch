import asyncio

from backend.app.config import Settings
from backend.app.service import Platform


def test_degraded_retrieval_blocks_deployment():
    p = Platform(
        Settings(database_url="sqlite:///:memory:", seed_on_start=False, demo_latency_scale=0)
    )
    result = asyncio.run(p.regression(degraded=True))
    assert result["status"] == "DEPLOYMENT BLOCKED"
    assert any("context_recall" in r for r in result["reasons"])
    assert result["passed"] < result["total"]
