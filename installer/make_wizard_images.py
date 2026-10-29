"""Genera las imágenes del asistente de instalación con la marca de Anyelo Style.
Uso (desde la raíz del proyecto):  python installer/make_wizard_images.py"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "anyelo_qr" / "assets"
OUT = Path(__file__).resolve().parent
INK, BONE, GOLD, MUTED, LINE = "#070707", "#EBE5CE", "#D4AF37", "#8F877B", "#2A2A2A"


def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(ASSETS / "fonts" / f"BricolageGrotesque-{name}.ttf"), size)


def centered(d, y, text, fnt, fill, width, spacing=0):
    w = d.textlength(text, font=fnt) + spacing * (len(text) - 1)
    x = (width - w) / 2
    if not spacing:
        d.text((x, y), text, font=fnt, fill=fill)
        return
    for ch in text:
        d.text((x, y), ch, font=fnt, fill=fill)
        x += d.textlength(ch, font=fnt) + spacing


def large():
    W, H, S = 164, 314, 4          # se dibuja 4 veces más grande y se reduce, para bordes suaves
    img = Image.new("RGB", (W * S, H * S), INK)
    d = ImageDraw.Draw(img)
    logo = Image.open(ASSETS / "logo.png").convert("RGBA").resize((84 * S, 84 * S), Image.LANCZOS)
    img.paste(logo, ((W * S - 84 * S) // 2, 44 * S), logo)
    centered(d, 150 * S, "Anyelo", font("ExtraBold", 26 * S), BONE, W * S)
    centered(d, 178 * S, "Style", font("Regular", 26 * S), GOLD, W * S)
    centered(d, 222 * S, "QR  ·  SIN INTERNET", font("SemiBold", 8 * S), GOLD, W * S, spacing=int(1.4 * S))
    d.rectangle((W * S // 2 - 14 * S, 244 * S, W * S // 2 + 14 * S, 245 * S), fill=GOLD)
    centered(d, 286 * S, "anyelo.style", font("SemiBold", 8 * S), MUTED, W * S, spacing=int(0.8 * S))
    img.resize((W, H), Image.LANCZOS).save(OUT / "wizard_large.bmp")


def small():
    W = 55
    S = 4
    img = Image.new("RGB", (W * S, W * S), INK)
    logo = Image.open(ASSETS / "logo.png").convert("RGBA").resize((40 * S, 40 * S), Image.LANCZOS)
    img.paste(logo, (7 * S, 7 * S), logo)
    img.resize((W, W), Image.LANCZOS).save(OUT / "wizard_small.bmp")


if __name__ == "__main__":
    large()
    small()
    print("listo")
