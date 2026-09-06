import asyncio
import hmac
import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles

from .config import ROOT, Settings, settings
from .database import (
    Alert,
    Candidate,
    DriftSnapshot,
    Evaluation,
    Experiment,
    Feedback,
    RegressionRun,
    Trace,
)
from .monitoring import overview
from .public_limits import PublicActionGuard
from .schemas import BenchmarkRequest, CandidateReview, ChaosRequest, ChatRequest, FeedbackRequest
from .service import SCENARIOS, Platform
from .tracing import configure_otel


def create_app(config: Settings = settings):
    @asynccontextmanager
    async def lifespan(app):
        logging.basicConfig(level=logging.INFO, format="%(message)s")
        configure_otel(config.otel_enabled)
        app.state.platform = Platform(config)
        if config.seed_on_start and config.demo_mode:
            await app.state.platform.seed()
        yield
        app.state.platform.store.engine.dispose()

    app = FastAPI(
        title="AgentWatch",
        version="1.0.0",
        lifespan=lifespan,
        description="Local-first AI evaluation and reliability. Demo responses and costs are simulated.",
    )

    def platform():
        return app.state.platform

    def authorize(x_api_key: str = Header(default="")):
        if config.api_key and not hmac.compare_digest(x_api_key, config.api_key):
            raise HTTPException(401, "A valid X-API-Key is required")

    auth = [Depends(authorize)]
    app.add_middleware(PublicActionGuard, config=config)

    @app.get("/health")
    def health():
        p = platform()
        return {
            "status": "ok",
            "demo_mode": config.demo_mode,
            "seeding": p.seeding,
            "seed_error": p.seed_error,
            "model": "demo-deterministic-v1" if config.demo_mode else config.ollama_model,
        }

    @app.get("/metrics")
    def prometheus():
        return Response(
            platform().metrics.render(), media_type="text/plain; version=0.0.4; charset=utf-8"
        )

    @app.post("/api/chat", dependencies=auth)
    async def chat(body: ChatRequest):
        return await platform().run(**body.model_dump())

    @app.post("/api/chaos/run", dependencies=auth)
    async def chaos(body: ChaosRequest):
        return await platform().run(**body.model_dump())

    @app.get("/api/chaos/scenarios", dependencies=auth)
    def scenarios():
        return [
            {"id": id, "name": name, "description": description, "group": group}
            for id, name, description, group in SCENARIOS
        ]

    @app.get("/api/traces", dependencies=auth)
    def traces(
        limit: int = Query(100, ge=1, le=1000),
        offset: int = Query(0, ge=0),
        q: str = "",
        status: str = "",
    ):
        rows = platform().store.list(Trace)
        rows = [
            t
            for t in rows
            if q.lower() in (t["query"] + t["trace_id"]).lower()
            and (not status or t["status"] == status)
        ]
        return {
            "total": len(rows),
            "items": [
                {
                    k: t[k]
                    for k in [
                        "trace_id",
                        "query",
                        "status",
                        "duration_ms",
                        "timestamp",
                        "evaluation",
                        "failures",
                        "scenario",
                        "model",
                    ]
                }
                for t in rows[offset : offset + limit]
            ],
        }

    @app.get("/api/traces/{trace_id}", dependencies=auth)
    def trace(trace_id: str):
        row = platform().store.get(Trace, trace_id)
        if not row:
            raise HTTPException(404, "Trace not found")
        return row

    @app.get("/api/metrics/overview", dependencies=auth)
    def metrics_overview():
        result = overview(platform().store.list(Trace))
        result["demo_mode"] = config.demo_mode
        result["active_alerts"] = sum(a["active"] for a in platform().store.list(Alert))
        return result

    @app.get("/api/evaluations", dependencies=auth)
    def evaluations():
        return platform().store.list(Evaluation)

    @app.get("/api/drift", dependencies=auth)
    def drift():
        return {**platform().drift(), "history": platform().store.list(DriftSnapshot, 50)}

    @app.post("/api/drift/demo", dependencies=auth)
    async def drift_demo():
        await asyncio.gather(
            *(
                platform().run(
                    "Show checkout-api metrics for high P95 latency and historical incidents. " * 8,
                    top_k=5,
                )
                for _ in range(30)
            )
        )
        platform().refresh_alerts()
        return platform().drift()

    @app.get("/api/alerts", dependencies=auth)
    def alerts():
        return platform().store.list(Alert)

    @app.post("/api/feedback", dependencies=auth)
    def feedback(body: FeedbackRequest):
        t = platform().store.get(Trace, body.trace_id)
        if not t:
            raise HTTPException(404, "Trace not found")
        id = uuid.uuid4().hex
        platform().store.put(Feedback, id, {"id": id, **body.model_dump()})
        if body.rating == "down":
            existing = platform().store.get(Candidate, body.trace_id)
            platform().store.put(
                Candidate,
                body.trace_id,
                {
                    "id": body.trace_id,
                    "trace_id": body.trace_id,
                    "query": t["query"],
                    "source": "human_feedback",
                    "status": existing["status"] if existing else "pending",
                    "reason": body.reason,
                    "comment": body.comment,
                },
            )
        return {"id": id, "status": "stored"}

    @app.get("/api/candidates", dependencies=auth)
    def candidates():
        return platform().store.list(Candidate)

    @app.post("/api/candidates/{id}/review", dependencies=auth)
    def review(id: str, body: CandidateReview):
        candidate = platform().store.get(Candidate, id)
        if not candidate:
            raise HTTPException(404, "Candidate not found")
        candidate["status"] = body.status
        platform().store.put(Candidate, id, candidate)
        return candidate

    @app.get("/api/candidates/export", dependencies=auth)
    def export_candidates():
        return [c for c in platform().store.list(Candidate) if c["status"] == "approved"]

    @app.post("/api/experiments/run", dependencies=auth)
    async def experiment():
        return await platform().experiment()

    @app.get("/api/experiments", dependencies=auth)
    def experiments():
        return platform().store.list(Experiment)

    @app.post("/api/regression/run", dependencies=auth)
    async def regression(body: BenchmarkRequest):
        return await platform().regression(body.degraded)

    @app.get("/api/regression", dependencies=auth)
    def regressions():
        return platform().store.list(RegressionRun)

    static = ROOT / "frontend/dist"
    if static.exists():
        app.mount("/", StaticFiles(directory=static, html=True), name="dashboard")
    return app


app = create_app()
