"""Genera assets/rhino2sw.ico (eseguire una volta: python assets/crea_icona.py)."""
import os
from PIL import Image, ImageDraw, ImageFont

S = 512
img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
d = ImageDraw.Draw(img)
d.rounded_rectangle([16, 16, S - 16, S - 16], radius=96, fill=(28, 58, 112))
# cilindro stilizzato: B-spline (tratteggiata) -> cilindro vero (pieno)
d.ellipse([70, 120, 230, 190], outline=(150, 175, 215), width=14)
d.line([70, 155, 70, 340], fill=(150, 175, 215), width=14)
d.line([230, 155, 230, 340], fill=(150, 175, 215), width=14)
d.arc([70, 305, 230, 375], 0, 180, fill=(150, 175, 215), width=14)
d.polygon([(255, 225), (310, 255), (255, 285)], fill=(255, 190, 60))
d.rectangle([240, 245, 262, 265], fill=(255, 190, 60))
d.ellipse([300, 120, 460, 190], fill=(235, 242, 255))
d.rectangle([300, 155, 460, 340], fill=(235, 242, 255))
d.ellipse([300, 305, 460, 375], fill=(235, 242, 255))
d.ellipse([300, 120, 460, 190], outline=(28, 58, 112), width=8)
try:
    f = ImageFont.truetype("DejaVuSans-Bold.ttf", 82)
except OSError:
    f = ImageFont.load_default()
d.text((S / 2, 440), "R→SW", font=f, fill=(255, 255, 255), anchor="mm")
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rhino2sw.ico")
img.save(out, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
img.save(out[:-4] + ".png")
print(out)
