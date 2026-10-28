"""Zeichnet das App-Icon von Market Desk (eigenes Motiv) und erzeugt icon.icns."""
import subprocess
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter

HERE = Path(__file__).resolve().parent
S = 1024 * 4  # vierfach zeichnen, dann verkleinern = glatte Kanten


def draw() -> Image.Image:
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # macOS-typische Fläche: ca. 80 % der Kachel, abgerundet
    m, r = int(S * 0.10), int(S * 0.18)
    box = (m, m, S - m, S - m)
    bg = Image.new("RGBA", (S, S))
    gd = ImageDraw.Draw(bg)
    for y in range(S):  # dunkles Blau, leichter Verlauf
        t = y / S
        gd.line([(0, y), (S, y)], fill=(int(14 + 10 * t), int(22 + 12 * t), int(40 + 22 * t), 255))
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).rounded_rectangle(box, radius=r, fill=255)
    img.paste(bg, (0, 0), mask)

    # Halbtransparentes auf eigener Ebene zeichnen und dann überblenden
    overlay = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    x0, x1 = m + int(S * 0.12), S - m - int(S * 0.12)
    y0, y1 = m + int(S * 0.18), S - m - int(S * 0.16)
    # feine Rasterlinien
    for i in range(1, 4):
        y = y0 + (y1 - y0) * i / 4
        od.line([(x0, y), (x1, y)], fill=(255, 255, 255, 28), width=int(S * 0.004))
    # Säulen (Volumen) in gedämpftem Türkis
    n = 6
    w = (x1 - x0) / (n * 1.6)
    heights = [0.18, 0.28, 0.22, 0.38, 0.32, 0.50]
    for i, h in enumerate(heights):
        cx = x0 + (x1 - x0) * (i + 0.5) / n
        od.rounded_rectangle([cx - w / 2, y1 - (y1 - y0) * h, cx + w / 2, y1], radius=int(w * 0.25), fill=(45, 212, 191, 110))
    img.alpha_composite(overlay)
    # Kurslinie in Bernstein, aufsteigend
    pts = [(0.0, 0.30), (0.2, 0.42), (0.38, 0.36), (0.56, 0.58), (0.74, 0.52), (1.0, 0.86)]
    line = [(x0 + (x1 - x0) * px, y1 - (y1 - y0) * py) for px, py in pts]
    glow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(glow).line(line, fill=(245, 158, 11, 160), width=int(S * 0.05), joint="curve")
    img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(S * 0.02)))
    d.line(line, fill=(251, 191, 36, 255), width=int(S * 0.028), joint="curve")
    ex, ey = line[-1]
    rr = S * 0.035
    d.ellipse([ex - rr, ey - rr, ex + rr, ey + rr], fill=(255, 255, 255, 255))
    return img.resize((1024, 1024), Image.LANCZOS)


def main():
    icon = draw()
    icon.save(HERE / "icon.png")
    (HERE.parent / "frontend" / "public").mkdir(exist_ok=True)
    icon.resize((256, 256), Image.LANCZOS).save(HERE.parent / "frontend" / "public" / "icon.png")
    iconset = HERE / "icon.iconset"
    iconset.mkdir(exist_ok=True)
    for size in (16, 32, 128, 256, 512):
        icon.resize((size, size), Image.LANCZOS).save(iconset / f"icon_{size}x{size}.png")
        icon.resize((size * 2, size * 2), Image.LANCZOS).save(iconset / f"icon_{size}x{size}@2x.png")
    subprocess.run(["iconutil", "-c", "icns", str(iconset), "-o", str(HERE / "icon.icns")], check=True)
    print("Icon erstellt:", HERE / "icon.icns")


if __name__ == "__main__":
    sys.exit(main())
