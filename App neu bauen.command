#!/bin/bash
# Doppelklick genügt: baut Market Desk neu und installiert die App im Programme-Ordner.
set -e
cd "$(dirname "$0")"
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"

echo "=== Market Desk wird neu gebaut ==="

echo "[1/4] Oberfläche bauen …"
( cd frontend && npm ci --silent --no-fund --no-audit && npm run build --silent )

echo "[2/4] Python-Umgebung prüfen …"
[ -d backend/.venv ] || uv venv -q --python 3.12 backend/.venv
uv pip install -q --python backend/.venv/bin/python -r backend/requirements-build.txt

echo "[3/4] App zusammenstellen (dauert 1–2 Minuten) …"
[ -f desktop/icon.icns ] || backend/.venv/bin/python desktop/make_icon.py
backend/.venv/bin/pyinstaller --noconfirm --log-level WARN \
  --distpath build/dist --workpath build/work desktop/market_desk.spec

# API-Keys (falls vorhanden) für die App bereitstellen – bleiben lokal auf diesem Mac
mkdir -p "$HOME/Library/Application Support/Market Desk"
[ -f backend/.env ] && cp backend/.env "$HOME/Library/Application Support/Market Desk/.env" && chmod 600 "$HOME/Library/Application Support/Market Desk/.env"

echo "[4/4] In den Programme-Ordner kopieren …"
osascript -e 'quit app "Market Desk"' >/dev/null 2>&1 || true
sleep 1
rm -rf "/Applications/Market Desk.app"
cp -R "build/dist/Market Desk.app" /Applications/

echo ""
echo "Fertig! Market Desk liegt jetzt in /Applications (Programme)."
read -n 1 -s -r -p "Beliebige Taste drücken, um dieses Fenster zu schliessen …"
