import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.app.config import Settings
from backend.app.service import Platform


if __name__ == "__main__":
    platform = Platform(Settings(demo_mode=True))
    asyncio.run(platform.seed())
    if platform.seed_error:
        raise SystemExit(platform.seed_error)
    print("Demo store ready. Existing stores are preserved; seeding is idempotent.")
