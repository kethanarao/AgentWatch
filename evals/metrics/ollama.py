import asyncio
import os

import httpx
from deepeval.models import DeepEvalBaseLLM


class OllamaJudge(DeepEvalBaseLLM):
    def __init__(self):
        self.url = os.getenv("OLLAMA_URL", "http://localhost:11434")
        super().__init__(model_name=os.getenv("OLLAMA_MODEL", "qwen2.5:3b"))

    def load_model(self):
        return self.model_name

    def generate(self, prompt: str, schema=None):
        error = None
        for _ in range(2):
            try:
                response = httpx.post(
                    f"{self.url}/api/generate",
                    timeout=120,
                    json={
                        "model": self.model_name,
                        "prompt": prompt,
                        "stream": False,
                        "format": schema.model_json_schema() if schema else "json",
                        "options": {"temperature": 0},
                    },
                )
                response.raise_for_status()
                content = response.json()["response"]
                return schema.model_validate_json(content) if schema else content
            except (httpx.HTTPError, ValueError, KeyError) as exc:
                error = exc
        raise RuntimeError(
            "Local DeepEval judge unavailable or invalid after two attempts"
        ) from error

    async def a_generate(self, prompt, schema=None):
        return await asyncio.to_thread(self.generate, prompt, schema)

    def get_model_name(self):
        return f"ollama/{self.model_name}"
