import time
import uuid
from contextlib import contextmanager, nullcontext
from datetime import datetime, timezone


class Recorder:
    def __init__(self, model: str, otel_enabled: bool = False):
        self.trace_id = uuid.uuid4().hex
        self.origin = time.perf_counter()
        self.spans = []
        self.stack = []
        self.model = model
        self.otel_enabled = otel_enabled

    @contextmanager
    def span(self, name: str, input=None, metadata=None):
        start = time.perf_counter()
        item = {
            "span_id": uuid.uuid4().hex[:16],
            "parent_id": self.stack[-1] if self.stack else None,
            "name": name,
            "start_time": datetime.now(timezone.utc).isoformat(),
            "offset_ms": (start - self.origin) * 1000,
            "duration_ms": 0,
            "input": input,
            "output_summary": None,
            "status": "OK",
            "error": None,
            "token_estimate": 0,
            "model": self.model,
            "metadata": metadata or {},
        }
        self.spans.append(item)
        self.stack.append(item["span_id"])
        context = nullcontext()
        if self.otel_enabled:
            from opentelemetry import trace

            context = trace.get_tracer("agentwatch").start_as_current_span(name)
        try:
            with context as external:
                if external:
                    external.set_attribute("agentwatch.trace_id", self.trace_id)
                yield item
        except Exception as exc:
            item.update(status="ERROR", error=str(exc)[:500])
            raise
        finally:
            item["duration_ms"] = round((time.perf_counter() - start) * 1000, 3)
            self.stack.pop()


def configure_otel(enabled: bool):
    if not enabled:
        return
    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    provider = TracerProvider(resource=Resource.create({"service.name": "agentwatch"}))
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(provider)
