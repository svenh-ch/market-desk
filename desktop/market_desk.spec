# -*- mode: python ; coding: utf-8 -*-
# Bauplan für die Mac-App "Market Desk" (PyInstaller).
# Wird von "App neu bauen.command" verwendet – normalerweise nicht direkt aufrufen.
import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_all, collect_submodules

ROOT = Path(SPECPATH).parent
sys.path.insert(0, str(ROOT / "backend"))

datas = [(str(ROOT / "frontend" / "dist"), "frontend_dist")]
binaries = []
hiddenimports = collect_submodules("app") + collect_submodules("uvicorn")

# Pakete mit Zusatzdateien/Binärteilen vollständig mitnehmen
for pkg in ("yfinance", "curl_cffi", "webview", "peewee", "certifi"):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

a = Analysis(
    [str(ROOT / "desktop" / "market_desk.py")],
    pathex=[str(ROOT / "backend")],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["tkinter", "PyInstaller", "PIL", "pytest", "IPython"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="Market Desk",
    console=False,
    argv_emulation=False,
    icon=str(ROOT / "desktop" / "icon.icns"),
)
coll = COLLECT(exe, a.binaries, a.datas, name="Market Desk")

app = BUNDLE(
    coll,
    name="Market Desk.app",
    icon=str(ROOT / "desktop" / "icon.icns"),
    bundle_identifier="local.marketdesk.app",
    info_plist={
        "CFBundleName": "Market Desk",
        "CFBundleDisplayName": "Market Desk",
        "CFBundleShortVersionString": "3.0.0",
        "NSHighResolutionCapable": True,
        "LSApplicationCategoryType": "public.app-category.finance",
        # Erlaubt dem Fenster, den eigenen lokalen Server (127.0.0.1) zu laden
        "NSAppTransportSecurity": {"NSAllowsLocalNetworking": True},
    },
)
