import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Export API keys to os.environ BEFORE importing engine-dependent modules.
# The engine reads os.environ at module-import time, so this must come first.
from app.config import settings

for _key in ("anthropic_api_key", "gemini_api_key", "minimax_api_key"):
    _value = getattr(settings, _key, "")
    if _value:
        os.environ.setdefault(_key.upper(), _value)

# Set PROJECT_ROOT so the engine can find config files from venv installs
from pathlib import Path as _Path

os.environ.setdefault("PROJECT_ROOT", str(_Path(__file__).resolve().parent.parent.parent))

from app.api.auth import router as auth_router  # noqa: E402
from app.api.drive import router as drive_router  # noqa: E402
from app.api.generate import router as generate_router  # noqa: E402
from app.api.images import router as images_router  # noqa: E402
from app.api.products import router as products_router  # noqa: E402
from app.api.save import router as save_router  # noqa: E402
from app.database import init_db  # noqa: E402


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Etsy Listing Agent API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(drive_router)
app.include_router(generate_router)
app.include_router(images_router)
app.include_router(products_router)
app.include_router(save_router)


@app.get("/api/health")
async def health():
    return {"status": "ok"}
