"""Generate ministaut.ico (stadium-green badge with an M). Needs Pillow."""
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

out = Path(sys.argv[1])
size = 256
img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
d = ImageDraw.Draw(img)
d.rounded_rectangle((8, 8, size - 8, size - 8), radius=56, fill=(9, 22, 15, 255), outline=(121, 232, 162, 255), width=12)
d.rectangle((40, 176, size - 40, 192), fill=(121, 232, 162, 255))
try:
    font = ImageFont.truetype('segoeuib.ttf', 150)
except OSError:
    font = ImageFont.load_default()
d.text((size / 2, 112), 'M', font=font, fill=(234, 248, 236, 255), anchor='mm')
img.save(out, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
print('Ikon:', out)
