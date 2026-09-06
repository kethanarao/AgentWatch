from typing import Literal

from pydantic import BaseModel, Field

ChaosName = Literal[
    "bad_retrieval",
    "empty_retrieval",
    "outdated_document",
    "tool_timeout",
    "tool_500",
    "malformed_tool_json",
    "duplicate_tool_call",
    "slow_llm",
    "hallucinated_citation",
    "prompt_injection",
    "long_context",
    "generation_failure",
]


class ChatRequest(BaseModel):
    query: str = Field(min_length=3, max_length=4000)
    top_k: int = Field(default=3, ge=1, le=10)
    service: str = Field(default="checkout-api", pattern=r"^[a-zA-Z0-9_-]{1,60}$")


class ChaosRequest(ChatRequest):
    scenario: ChaosName


class FeedbackRequest(BaseModel):
    trace_id: str
    rating: Literal["up", "down"]
    reason: Literal[
        "Incorrect",
        "Hallucinated",
        "Missing information",
        "Wrong tool",
        "Bad citation",
        "Too slow",
        "",
    ] = ""
    comment: str = Field(default="", max_length=1000)


class JudgeResult(BaseModel):
    correctness: float = Field(ge=0, le=1)
    completeness: float = Field(ge=0, le=1)
    helpfulness: float = Field(ge=0, le=1)
    groundedness: float = Field(ge=0, le=1)
    reasoning: str = Field(max_length=2000)


class BenchmarkRequest(BaseModel):
    degraded: bool = False


class CandidateReview(BaseModel):
    status: Literal["approved", "rejected"]
