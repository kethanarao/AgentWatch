from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    demo_mode: bool = True
    database_url: str = "sqlite:///./runtime/agentwatch.db"
    seed_on_start: bool = True
    demo_latency_scale: float = Field(default=1.0, ge=0, le=10)
    online_eval_sample_rate: float = Field(default=0.10, ge=0, le=1)
    demo_eval_sample_rate: float = Field(default=1, ge=0, le=1)
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:3b"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    rerank: bool = False
    otel_enabled: bool = False
    api_key: str = ""
    max_concurrent_runs: int = Field(default=4, ge=1, le=32)
    public_requests_per_minute: int = Field(default=30, ge=1, le=1000)
    public_benchmarks_per_10_minutes: int = Field(default=2, ge=1, le=100)
    public_max_active: int = Field(default=4, ge=1, le=32)
    public_max_body_bytes: int = Field(default=16384, ge=1024, le=65536)
    public_request_timeout_seconds: float = Field(default=180, ge=1, le=600)
    llm_timeout_seconds: float = Field(default=60, ge=1, le=120)
    semantic_retrieval: bool = False
    llm_tool_selection: bool = True
    llm_max_output_tokens: int = Field(default=180, ge=64, le=800)
    live_generation_retries: int = Field(default=0, ge=0, le=1)
    structured_answers: bool = False
    span_latency_budget_ms: int = Field(default=2000, ge=100, le=120000)
    request_latency_budget_ms: int = Field(default=5000, ge=100, le=300000)
    min_faithfulness: float = 0.80
    min_context_recall: float = 0.75
    min_citation_accuracy: float = 0.95
    max_p95_latency_ms: float = 5000
    max_regression_percent: float = 10
    min_latency_regression_ms: float = 100
    input_cost_per_1m: float = 0.15
    output_cost_per_1m: float = 0.60
    cost_profile: str = "production-model-A"


settings = Settings()
