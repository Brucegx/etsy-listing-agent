import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Configure structured JSON logging as early as possible so every subsequent
# log record (including import-time warnings) uses the JSON formatter.
from app.logging_config import RequestIdMiddleware, configure_logging

# Use LOG_LEVEL env var directly here because settings hasn't been imported yet
configure_logging(level=os.environ.get("LOG_LEVEL", "INFO"))

# Export API keys to os.environ BEFORE importing engine-dependent modules.
# The engine reads os.environ at module-import time, so this must come first.
from app.config import settings  # noqa: E402

for _key in ("anthropic_api_key", "gemini_api_key", "minimax_api_key"):
    _value = getattr(settings, _key, "")
    if _value:
        os.environ.setdefault(_key.upper(), _value)

# Set PROJECT_ROOT so the engine can find config files from venv installs
from pathlib import Path as _Path  # noqa: E402

os.environ.setdefault("PROJECT_ROOT", str(_Path(__file__).resolve().parent.parent.parent))

from app.api.auth import router as auth_router  # noqa: E402
from app.api.drive import router as drive_router  # noqa: E402
from app.api.generate import router as generate_router  # noqa: E402
from app.api.images import router as images_router  # noqa: E402
from app.api.jobs import router as jobs_router  # noqa: E402
from app.api.keys import router as keys_router  # noqa: E402
from app.api.products import router as products_router  # noqa: E402
from app.api.save import router as save_router  # noqa: E402
from app.api.v1.generate import router as v1_generate_router  # noqa: E402
from app.database import init_db  # noqa: E402

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Application starting up")
    init_db()
    logger.info("Database initialised")
    yield
    logger.info("Application shutting down")


app = FastAPI(title="Etsy Listing Agent API", lifespan=lifespan)

# Request ID middleware must be added BEFORE CORS so every response carries
# the X-Request-ID header (including preflight OPTIONS responses).
app.add_middleware(RequestIdMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*", "X-Request-ID"],
    expose_headers=["X-Request-ID", "X-RateLimit-Remaining", "X-RateLimit-Reset"],
)

app.include_router(auth_router)
app.include_router(drive_router)
app.include_router(generate_router)
app.include_router(images_router)
app.include_router(jobs_router)
app.include_router(keys_router)
app.include_router(products_router)
app.include_router(save_router)
app.include_router(v1_generate_router)


@app.get("/api/health")
async def health():
    return {"status": "ok"}
