"""
Zentrale Einstellungen für Market Desk.

- Der Server lauscht nur auf 127.0.0.1 (nur dieser Mac, nicht im WLAN).
- Daten (Datenbank, Logs, .env für die App) liegen in
  ~/Library/Application Support/Market Desk
- API-Keys werden aus einer .env-Datei gelesen (nie im Code, nie in Git):
  zuerst aus dem Application-Support-Ordner, sonst aus backend/.env.
"""
from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings

APP_NAME = "Market Desk"
DATA_DIR = Path.home() / "Library" / "Application Support" / APP_NAME
DATA_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR = Path.home() / "Library" / "Logs" / APP_NAME
LOG_DIR.mkdir(parents=True, exist_ok=True)

BACKEND_DIR = Path(__file__).resolve().parent.parent

# Die erste gefundene .env gewinnt (load_dotenv überschreibt nichts Bestehendes)
for env_file in (DATA_DIR / ".env", BACKEND_DIR / ".env"):
    if env_file.exists():
        load_dotenv(env_file, override=False)


class Settings(BaseSettings):
    # Nur lokal erreichbar. Bitte nicht auf 0.0.0.0 ändern.
    HOST: str = "127.0.0.1"
    PORT: int = 8000  # nur für den Entwicklungsmodus; die App wählt selbst einen freien Port
    DEBUG: bool = False
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"

    # Optionale Keys (leer lassen, wenn nicht vorhanden)
    ANTHROPIC_API_KEY: str = ""

    # Cache-Dauer in Sekunden
    QUOTE_CACHE_SECONDS: int = 60          # Kurse: höchstens 1 Minute
    HISTORY_CACHE_SECONDS: int = 15 * 60   # Kursverlauf (Tagesdaten)
    INFO_CACHE_SECONDS: int = 24 * 3600    # Firmenangaben/Kennzahlen
    NEWS_CACHE_SECONDS: int = 10 * 60

    @property
    def cors_origins_list(self):
        return [o.strip() for o in self.CORS_ORIGINS.split(",")]

    class Config:
        case_sensitive = True
        extra = "ignore"


settings = Settings()

# Sicherheitsnetz: niemals auf allen Netzwerkschnittstellen lauschen
if settings.HOST not in ("127.0.0.1", "localhost", "::1"):
    settings.HOST = "127.0.0.1"
