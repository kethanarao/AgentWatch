import hashlib
import json

from pydantic import BaseModel, Field

from .config import ROOT


class ServiceMetrics(BaseModel):
    service: str
    cpu: float = Field(ge=0, le=100)
    memory: float = Field(ge=0, le=100)
    p50_latency_ms: int
    p95_latency_ms: int
    p99_latency_ms: int
    error_rate: float = Field(ge=0, le=1)


def metrics_tool(service: str):
    seed = int(hashlib.sha256(service.encode()).hexdigest()[:8], 16)
    return ServiceMetrics(
        service=service,
        cpu=40 + seed % 51,
        memory=45 + seed % 40,
        p50_latency_ms=80 + seed % 120,
        p95_latency_ms=500 + seed % 500,
        p99_latency_ms=1200 + seed % 1500,
        error_rate=(seed % 12) / 100,
    ).model_dump()


def incident_tool(service: str, query: str):
    incidents = json.loads((ROOT / "data/incidents/incidents.json").read_text())
    words = set(query.lower().split())
    candidates = [x for x in incidents if x["service"] == service]
    candidates.sort(
        key=lambda x: len(words & set(" ".join(x["symptoms"]).lower().split())), reverse=True
    )
    return {"service": service, "incidents": candidates[:3], "simulated": True}


def select_tools(query: str, confidence: float):
    tools = []
    if any(
        w in query.lower() for w in ["latency", "cpu", "memory", "503", "metrics", "queue", "pool"]
    ):
        tools.append("metrics_tool")
    if "historical" in query.lower() or "incident" in query.lower() or confidence < 0.08:
        tools.append("incident_tool")
    return tools
