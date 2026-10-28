import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import APP_NAME, BACKEND_DIR, settings
from app.database.seed import seed as seed_db
from app.routers import alerts, assets, companies, market, news, portfolio, relationships, score, watchlist

log = logging.getLogger(__name__)


def _frontend_dir() -> Path:
    """Fertig gebaute Oberfläche: in der Mac-App eingepackt, sonst frontend/dist."""
    bundled = getattr(sys, "_MEIPASS", None)
    if bundled:
        return Path(bundled) / "frontend_dist"
    return BACKEND_DIR.parent / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    seed_db()
    yield


app = FastAPI(title=APP_NAME, version="3.0.0", lifespan=lifespan)

# Nur für den Entwicklungsmodus (npm run dev auf Port 5173) nötig
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_methods=["*"],
    allow_headers=["*"],
)

for r in (market, assets, news, portfolio, alerts, companies, relationships, score, watchlist):
    app.include_router(r.router)


@app.get("/api/health")
def health():
    return {"status": "ok", "app": APP_NAME}


# ── Oberfläche ausliefern (falls gebaut) ──────────────────────────────────────
FRONTEND = _frontend_dir()
if (FRONTEND / "index.html").exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str):
        # Echte Dateien (z. B. Icon) direkt, alles andere → index.html (React-Router)
        candidate = (FRONTEND / full_path).resolve()
        if full_path and candidate.is_file() and FRONTEND.resolve() in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(FRONTEND / "index.html")
else:
    log.info("Kein gebautes Frontend gefunden (%s) – nur API aktiv.", FRONTEND)
