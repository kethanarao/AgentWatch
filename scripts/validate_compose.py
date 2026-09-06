"""Portable structural checks; `docker compose config` remains the authoritative check."""

from pathlib import Path

import yaml

root = Path(__file__).resolve().parents[1]
config = yaml.safe_load((root / "docker-compose.yml").read_text())
services = config["services"]
assert {"frontend", "backend", "ollama", "prometheus", "grafana"} <= services.keys()
assert "profiles" not in services["backend"] and "profiles" not in services["frontend"]
assert services["frontend"]["depends_on"]["backend"]["condition"] == "service_healthy"
for name, service in services.items():
    build = service.get("build")
    if build:
        context = root / (build if isinstance(build, str) else build["context"])
        assert (context / "Dockerfile").is_file(), name
    for volume in service.get("volumes", []):
        if volume.startswith("./"):
            assert (root / volume.split(":")[0]).exists(), volume
print("Compose YAML, build contexts, profiles, health dependency and mounted files validated.")
print("This structural check does not build or launch containers.")
