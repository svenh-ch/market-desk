"""
Entwicklungsmodus: startet nur den Server (http://127.0.0.1:8000).
Für den Alltag gibt es die Mac-App – siehe README.md.
"""
import uvicorn
from app.config import settings

if __name__ == "__main__":
    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=True, log_level="info")
