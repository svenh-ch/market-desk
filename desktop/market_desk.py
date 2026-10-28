"""
Market Desk – Startpunkt der Mac-App.

Ablauf:
  1. Freien Port auf 127.0.0.1 belegen (nur dieser Mac, nie im WLAN).
  2. Backend (FastAPI/uvicorn) im selben Prozess in einem Hintergrund-Thread starten.
  3. Natives Fenster (pywebview / WebKit) mit der Oberfläche öffnen.
  4. Fenster zu → Server stoppen → Prozess vollständig beenden.
     Weil alles in EINEM Prozess läuft, bleibt nichts im Hintergrund zurück.

Entwicklung ohne App-Bau:  backend/.venv/bin/python desktop/market_desk.py
"""
import logging
import os
import socket
import sys
import threading
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path

# Beim Start aus dem Quellcode: Backend-Ordner importierbar machen
if not getattr(sys, "frozen", False):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.config import APP_NAME, LOG_DIR  # noqa: E402

LOG_FILE = LOG_DIR / "market-desk.log"


def _setup_logging() -> None:
    handler = RotatingFileHandler(LOG_FILE, maxBytes=2_000_000, backupCount=2, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(handler)
    # In der App gibt es keine Konsole. Ausgaben (z. B. von yfinance) ins Log umleiten,
    # damit "print" nicht ins Leere schreibt und abstürzt.
    if sys.stdout is None or getattr(sys, "frozen", False):
        log_stream = open(LOG_FILE, "a", buffering=1, encoding="utf-8")
        sys.stdout = log_stream
        sys.stderr = log_stream


def _bind_free_port() -> socket.socket:
    """Port 0 = das System wählt einen freien Port. So gibt es nie 'Port belegt'."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("127.0.0.1", 0))
    return sock


def main() -> None:
    _setup_logging()
    log = logging.getLogger("desktop")

    import uvicorn
    import webview
    from app.main import app

    sock = _bind_free_port()
    port = sock.getsockname()[1]
    url = f"http://127.0.0.1:{port}/"
    log.info("Starte %s auf %s", APP_NAME, url)

    server = uvicorn.Server(uvicorn.Config(app, log_config=None, access_log=False))
    thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, name="server", daemon=True)
    thread.start()

    # Warten, bis der Server bereit ist (höchstens 20 Sekunden)
    deadline = time.time() + 20
    while not server.started and thread.is_alive() and time.time() < deadline:
        time.sleep(0.05)
    if not server.started:
        log.error("Server konnte nicht gestartet werden – siehe Log oben.")
        os._exit(1)

    webview.settings["OPEN_EXTERNAL_LINKS_IN_BROWSER"] = True  # News-Links im normalen Browser öffnen
    webview.create_window(
        APP_NAME, url,
        width=1440, height=900, min_size=(1000, 650),
        background_color="#080c14",
    )
    webview.start()  # blockiert, bis das letzte Fenster geschlossen ist

    log.info("Fenster geschlossen – beende Server.")
    server.should_exit = True
    thread.join(timeout=5)
    log.info("Beendet.")
    # Sofort und vollständig beenden (auch falls noch eine Yahoo-Abfrage läuft)
    os._exit(0)


if __name__ == "__main__":
    main()
