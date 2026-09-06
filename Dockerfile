# Single-container cloud demo: React assets served by FastAPI on port 7860.
FROM node:24-bookworm-slim AS frontend-build
WORKDIR /build
COPY frontend/package*.json ./
RUN npm ci --ignore-scripts
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim AS backend
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 DEMO_MODE=true \
    DATABASE_URL=sqlite:////app/runtime/agentwatch.db DEEPEVAL_TELEMETRY_OPT_OUT=YES LANGSMITH_TRACING=false
WORKDIR /app
COPY pyproject.toml ./
COPY backend/ ./backend/
COPY evals/ ./evals/
ARG INSTALL_LOCAL=false
RUN pip install --no-cache-dir '.[observability,postgres]' && \
    if [ "$INSTALL_LOCAL" = "true" ]; then pip install --no-cache-dir '.[local]'; fi
COPY data/ ./data/
COPY scripts/ ./scripts/
RUN useradd -m -u 1000 agentwatch && mkdir -p /app/runtime /app/reports && chown -R agentwatch:agentwatch /app
USER agentwatch
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --start-period=180s --retries=5 CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]

FROM backend AS cloud
COPY --from=frontend-build --chown=agentwatch:agentwatch /build/dist /app/frontend/dist
EXPOSE 7860
HEALTHCHECK --interval=15s --timeout=5s --start-period=180s --retries=5 CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:7860/health')"
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "7860"]
