"""Подложка из фото DDJ-FLX6: левый дек + микшер 1:1, слева/справа стол — дорисовать Flux Fill.
Пишет ref/parts/canvas.png (кадр с серыми полями) и ref/parts/mask_out.png (белое = дорисовать),
mask_caps.png (белое = стереть ручки фейдеров). Координаты фото → кадр: x + OX, y - CY + OY."""
from PIL import Image, ImageDraw
import json
W, H = 1920, 1088
CROP = (0, 480, 1230, 1445)          # пульт с краями
OX, OY = 586, 60                     # куда кладём (джог x=374 фото → 960 кадра)
im = Image.open('ref/ddj-flx6.webp').convert('RGB').crop(CROP)
canvas = Image.new('RGB', (W, H), (40, 40, 40)); canvas.paste(im, (OX, OY))
mask = Image.new('L', (W, H), 255); d = ImageDraw.Draw(mask)
d.rectangle((OX + 14, OY + 14, OX + im.width - 14, OY + im.height - 14), fill=0)   # фото не трогать, 14 px нахлёст
canvas.save('ref/parts/canvas.png'); mask.save('ref/parts/mask_out.png')
# ручки фейдеров (фото): 4 канала + темп
caps = [(733, 1190, 799, 1234), (833, 1190, 899, 1234), (933, 1190, 999, 1234), (1033, 1190, 1099, 1234), (620, 1265, 686, 1305)]
m2 = Image.new('L', (W, H), 0); d2 = ImageDraw.Draw(m2)
for x0, y0, x1, y1 in caps: d2.rectangle((x0 + OX - 6, y0 - 480 + OY - 8, x1 + OX + 6, y1 - 480 + OY + 8), fill=255)
m2.save('ref/parts/mask_caps.png')
json.dump({'OX': OX, 'OY': OY, 'CY': 480, 'caps': caps}, open('ref/parts/layout.json', 'w'))
print('ok')
