# Deployment

## 1. Local lightweight demo

Docker Engine/Desktop + Compose v2.24 or later:

```bash
cp .env.example .env
docker compose up --build
```

The frontend serves at http://localhost:3000 and proxies to FastAPI. SQLite lives in the named `agentwatch-data` volume. Both public ports bind to loopback. The backend completes initial seed execution before its health check passes; frontend starts after that. The runtime uses no external credentials or model calls in demo mode. Build-time package/image downloads still need internet.

To run the cloud image locally instead:

```bash
docker build -t agentwatch .
docker run --rm -p 127.0.0.1:7860:7860 -v agentwatch-cloud:/app/runtime agentwatch
```

This serves both UI and API on http://localhost:7860. The default final Docker stage is `cloud`; Compose selects the `backend` stage for its split deployment. No Node process is needed in the cloud runtime.

## 2. Free-friendly cloud demo

Verified against official documentation on **2026-09-05**: Hugging Face documents **CPU Basic as free**, with two CPU cores, 16 GB RAM and non-persistent disk. Free hardware can sleep when inactive. Availability and account eligibility can change; confirm the CPU Basic option is free before creating a Space. Do not select a paid hardware upgrade.

Sources: [Spaces overview](https://huggingface.co/docs/hub/en/spaces-overview), [Docker Spaces](https://huggingface.co/docs/hub/main/spaces-sdks-docker), [hardware and sleep behavior](https://huggingface.co/docs/hub/spaces-gpus).

1. Create a Hugging Face Space using Docker and CPU Basic, after confirming current free eligibility.
2. Push this repository's source to that Space. The README already includes `sdk: docker` and `app_port: 7860` metadata.
3. Leave `DEMO_MODE=true` and `SEED_ON_START=true`. No API secret is needed for a deliberately public synthetic demo.
4. Wait for the multi-stage Docker build and initial seeding. Open the Space URL and test Overview, Run agent, Chaos Lab and Regression tests.
5. Treat local traces and feedback as disposable: free storage is ephemeral and may reset. Do not buy persistent storage merely for the portfolio demo.

If free Docker hosting is not offered for your account, keep the fully functional local demo and record a short walkthrough. No hosted account is necessary to use the repository. This deliverable includes deployment instructions; no account or remote project has been created or published on your behalf.

The Sites skill's hosted runtime is a JavaScript Cloudflare Worker, not Python. AgentWatch's LangGraph/FastAPI backend cannot run there. A static-only Sites deployment would leave the main requested features nonfunctional, so this project uses the Docker deployment path.

## 3. Self-hosted observability

```bash
docker compose --profile observability up --build
```

Prometheus scrapes backend:8000 every 15 seconds. Grafana provisions an AgentWatch dashboard and a Prometheus datasource. Open http://localhost:3001 (anonymous, read-only, bound to loopback). Panels show request rate, histogram-based P95, tool error ratio and lexical grounding proxy. Rates require multiple scrapes; initially empty panels are expected. Long-term retention and authentication should be configured before exposing observability services.

### Optional Langfuse OSS through OpenTelemetry

Deploy Langfuse separately using its maintained [self-hosting documentation](https://langfuse.com/self-hosting). AgentWatch does not force the full Langfuse service stack into its lightweight Compose startup.

Install the backend observability extra (the Docker image includes it), create a project in your self-hosted Langfuse, and configure:

```dotenv
OTEL_ENABLED=true
OTEL_EXPORTER_OTLP_ENDPOINT=http://your-langfuse-host:3000/api/public/otel
OTEL_EXPORTER_OTLP_HEADERS=Authorization=Basic%20<base64-of-public-key:secret-key>
```

For deployments using Langfuse's v4 ingestion, add the documented `x-langfuse-ingestion-version=4` header. Follow the version-specific [OTEL integration guide](https://langfuse.com/integrations/native/opentelemetry) for the exact header requirements of your installed version. Docker containers must use a reachable hostname, not their own loopback address. Secrets belong in local environment variables or the hosting secret store, never Git.

The OTEL exporter sends spans asynchronously. The local trace store is authoritative for the UI; no Langfuse instance or key is required. Raw user text is not added to OTEL attributes by default. Internal SQLite traces do store request content, so use sanitized support questions.

### PostgreSQL

Install `.[postgres]` and set `DATABASE_URL=postgresql+psycopg://USER:PASSWORD@HOST:5432/agentwatch`. Tables are created at startup. No external database is provided or required by the default demo. Use a separate database for each environment and add migrations before evolving a shared production schema.

## Operational boundaries

Use one backend worker. The benchmark lock and metric registry are process-local; a multi-worker production installation needs coordinated jobs and aggregation. API_KEY can protect reads and writes; the frontend accepts it through session-scoped Connection settings. This is a simple demonstration control, not full account-level authorization. Health and Prometheus endpoints are public; protect them at the ingress if necessary. Use a reverse proxy for HTTPS and resource/rate limits when exposing the app.
