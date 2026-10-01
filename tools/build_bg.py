"""Подложка и детали из фото DDJ-FLX6 (ref/ddj-flx6.webp). Без нейросети.

Кадр 1920x1080: слева копия микшерной панели (фото x 722..1150), дальше левый дек
с микшером (26..1150) — вместе ровно 1920 по ширине, по высоте пульт чуть больше кадра
(срез 10 px сверху, остальное снизу). Логотипы закрашены, всё притемнено под второй реф.
Пишет:
  app/img/bg.png       — кадр
  app/img/wheel.png    — джог с альфой (1024), вращается его чёрный диск
  app/layout.js        — доли кадра: джог, пады дека, светодиодные столбики каналов
python tools/build_bg.py
"""
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageEnhance

ROOT = Path(__file__).resolve().parent.parent
IMG = ROOT / 'app' / 'img'; IMG.mkdir(exist_ok=True)
W, H = 1920, 1080
CROP = (26, 510, 1150, 1432)      # дек + микшер без белых полей, до мастер-секции
MIX = (722, 1150)                 # микшерная панель по x на фото: от разделителя до мастер-секции
S = W / ((MIX[1] - CROP[0]) + (MIX[1] - MIX[0]))   # копия панели + дек с панелью = ширина кадра
TOP_CUT = 10                      # сколько срезать сверху (остальное уходит снизу)
JOG = (376, 933, 312)             # центр и внешний радиус джога (по профилю яркости)
PLATTER_R = 312                   # вращается весь джог вместе с ребристым кольцом (заказчик так попросил)
LOGOS = ((733, 536, 842, 606), (866, 1348, 1030, 1394))   # DDJ-FLX6 / PERFORMANCE DJ CONTROLLER, Pioneer DJ
PADS = [(230, 1317, 292, 1370), (309, 1317, 370, 1370), (388, 1317, 449, 1370), (466, 1317, 527, 1370)]  # верхний ряд по синей рамке
LED_X = (748, 853, 958, 1062)     # столбики индикаторов каналов
LED_Y = (778, 802, 827, 852, 877, 902)          # сверху вниз (нижний на фото тёмный)
LED_COLORS = ['#e64246', '#f8b227', '#f8b227', '#c1f723', '#c1f723', '#c1f723']   # сверху вниз
LED_W, LED_H = 6, 17
DARK = 0.62

src = Image.open(ROOT / 'ref' / 'ddj-flx6.webp').convert('RGB')
d = ImageDraw.Draw(src)
panel = src.getpixel((760, 1395))
for box in LOGOS: d.rectangle(box, fill=panel)

# кадр в масштабе фото: [копия панели][дек + панель]
MW = MIX[1] - MIX[0]
sheet = Image.new('RGB', (MW + (CROP[2] - CROP[0]), CROP[3] - CROP[1]), panel)
sheet.paste(src.crop((MIX[0], CROP[1], MIX[1], CROP[3])), (0, 0))
sheet.paste(src.crop(CROP), (MW, 0))
sheet = sheet.resize((W, round(sheet.height * S)), Image.LANCZOS)
bg = sheet.crop((0, TOP_CUT, W, TOP_CUT + H))
bg = ImageEnhance.Contrast(ImageEnhance.Brightness(bg).enhance(DARK)).enhance(1.08)
bg.save(IMG / 'bg.png')


def to_frame(x, y):               # координаты фото (дек + микшер) → кадр
    return (MW + x - CROP[0]) * S, (y - CROP[1]) * S - TOP_CUT


def to_frame_copy(x, y):          # координаты фото микшера → его копия слева
    return (x - MIX[0]) * S, (y - CROP[1]) * S - TOP_CUT


# джог — с фото, тем же затемнением
dark = ImageEnhance.Contrast(ImageEnhance.Brightness(src).enhance(DARK)).enhance(1.08)
cx, cy, r = JOG
wheel = dark.crop((cx - r, cy - r, cx + r, cy + r)).resize((1024, 1024), Image.LANCZOS)
m = Image.new('L', (1024, 1024), 0); ImageDraw.Draw(m).ellipse((0, 0, 1023, 1023), fill=255)
wheel.putalpha(m); wheel.save(IMG / 'wheel.png')

layout = {}
jx, jy = to_frame(cx, cy)
layout['jog'] = {'x': jx / W, 'y': jy / H, 'r': r * S / H, 'platter': PLATTER_R / r}
layout['pads'] = []
for x0, y0, x1, y1 in PADS:
    fx0, fy0 = to_frame(x0, y0); fx1, fy1 = to_frame(x1, y1)
    layout['pads'].append({'x': (fx0 + fx1) / 2 / W, 'y': (fy0 + fy1) / 2 / H, 'w': (fx1 - fx0) / W, 'h': (fy1 - fy0) / H})
# светодиоды: 8 столбиков (копия слева + оригинал), в каждом 6 LED сверху вниз
layout['leds'] = []
for conv in (to_frame_copy, to_frame):
    for x in LED_X:
        layout['leds'].append([[v / s for v, s in zip(conv(x, y), (W, H))] for y in LED_Y])
layout['led'] = {'w': LED_W * S / W, 'h': LED_H * S / H, 'colors': LED_COLORS}
(ROOT / 'app' / 'layout.js').write_text('const LAYOUT = ' + json.dumps(layout) + ';\n')
print('ok scale', round(S, 4), 'jog', {k: round(v, 4) for k, v in layout['jog'].items()})
