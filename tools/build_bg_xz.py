"""Подложка и детали из фото Pioneer XDJ-XZ (xdj-xz_1.png, 3024x1623). Без нейросети.

Кадр 1920x1080: фото масштабируется по высоте (x0.6654 → 2012 px) и срезается по 46 px с краёв.
Логотипы закрашены, экран пульта закрыт нашим табло. Пишет:
  app/img/bg.png       — кадр
  app/img/wheel.png    — левый джог с альфой (1024), вращается целиком; wheel2.png — правый
  app/layout.js        — доли кадра: jogs (два), display, pads (16: левая дека, правая), leds (4 канала), fader
python tools/build_bg_xz.py
"""
import json
from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
IMG = ROOT / 'app' / 'img'; IMG.mkdir(exist_ok=True)
W, H = 1920, 1080
src = Image.open(ROOT / 'xdj-xz_1.png').convert('RGB'); SW, SH = src.size
S = H / SH; X_CUT = (round(SW * S) - W) // 2
JOGS = [(524, 867, 368), (SW - 524, 867, 368)]          # центр и внешний радиус по подгонке окружности к ободу (tools: профиль яркости)
SCREEN_R = 112                                           # экран в центре джога
DISPLAY = (1238, 136, 1797, 453)                         # экран пульта — сюда встаёт табло игры
PADS_L = [(x, y, x + 90, y + 92) for y in (1348, 1457) for x in (315, 425, 535, 645)]
PADS = PADS_L + sorted([(SW - x1, y0, SW - x0, y1) for x0, y0, x1, y1 in PADS_L], key=lambda b: (b[1], b[0]))   # правая дека — зеркально, порядок слева направо
LED_X = (1230, 1377, 1524, 1671)                         # центр светящегося сегмента (1228…1232 на фото), левее — рамка                         # индикаторы каналов 3 1 2 4
LED_Y = [626, 648, 670, 692, 715, 737, 759, 781, 804, 826, 848]
LED_W, LED_H = 8, 13
CH_X = (1292, 1438, 1585, 1732)                          # фейдеры каналов 3 1 2 4: громкость, низкие, средние, высокие
CH_Y0, CH_Y1, CH_KNOB = 1139, 1289, (64, 30)             # ход «10»…«0» и ручка
TEMPO_X, TEMPO_Y0, TEMPO_Y1, TEMPO_KNOB = (948, 2924), 1165, 1505, (64, 72)   # правая дека — копия левой со сдвигом 1976, не зеркало
FADER = dict(y=1520, x0=1440, x1=1584, knob=(1486, 1478, 1534, 1562))   # ход кроссфейдера и ручка (закрашиваем, рисуем свою)
LOGOS = [(15, 215, 265, 275), (2660, 100, 3010, 145), (1040, 1495, 1215, 1545), (1082, 172, 1178, 218), (2290, 95, 2460, 130), (1370, 2, 1660, 52)]   # Pioneer DJ, rekordbox/serato, XDJ-XZ, rekordbox-кнопка, 1 5V

d = ImageDraw.Draw(src)
def fill_from(box, probe):
    d.rectangle(box, fill=src.getpixel(probe))
for box in LOGOS: fill_from(box, (box[0] - 6, box[1] + (box[3] - box[1]) // 2))
# индикаторы на фото гасим: светятся только наши
for x in LED_X: d.rectangle((x - 5, 616, x + 5, 860), fill=(14, 14, 14))
# ручки фейдеров каналов и темпа убираем: на их место копируем кусок дорожки без ручки, ручки рисует игра
for x in CH_X:
    kw, kh = CH_KNOB; y = 1215; y0 = y - kh // 2 - 6; y1 = y + kh // 2 + 8                     # зона ручки с тенью
    patch_src = src.crop((x - kw // 2 - 4, y0 + 60, x + kw // 2 + 4, y1 + 60))                  # четыре деления ниже: риски через 15 px совпадают
    src.paste(patch_src, (x - kw // 2 - 4, y0))
for x in TEMPO_X:
    kw, kh = TEMPO_KNOB; y = 1333; y0 = y - kh // 2 - 8; y1 = y + kh // 2 + 10
    patch_src = src.crop((x - kw // 2 - 4, y0 - (y1 - y0) - 16, x + kw // 2 + 4, y0 - 16))      # кусок дорожки выше ручки
    src.paste(patch_src, (x - kw // 2 - 4, y0))
# ручку кроссфейдера убираем: закрашиваем полосу хода цветом панели, шкала рисуется в игре
d.rectangle((FADER['x0'] - 20, FADER['knob'][1] - 6, FADER['x1'] + 20, FADER['knob'][3] + 6), fill=src.getpixel((1300, 1520)))
LED_COLORS = ['#ff4040'] * 2 + ['#f7ac40'] * 4 + ['#a8ff00'] * 5   # сверху вниз, как на фото

bg = src.resize((round(SW * S), H), Image.LANCZOS).crop((X_CUT, 0, X_CUT + W, H))
bg.save(IMG / 'bg.png')

to_frame = lambda x, y: (x * S - X_CUT, y * S)
layout = {'jogs': []}
for i, (cx, cy, r) in enumerate(JOGS):
    wheel = src.crop((cx - r, cy - r, cx + r, cy + r)).resize((1024, 1024), Image.LANCZOS)
    m = Image.new('L', (1024, 1024), 0); ImageDraw.Draw(m).ellipse((0, 0, 1023, 1023), fill=255)
    sc = round(1024 * SCREEN_R / r); ImageDraw.Draw(wheel).ellipse((512 - sc, 512 - sc, 512 + sc, 512 + sc), fill=(8, 8, 10))   # экран в центре не крутится — там имя трека
    wheel.putalpha(m); wheel.save(IMG / ('wheel.png' if i == 0 else 'wheel2.png'))
    jx, jy = to_frame(cx, cy); layout['jogs'].append({'x': jx / W, 'y': jy / H, 'r': r * S / H})
layout['jog'] = layout['jogs'][0]; layout['screen'] = SCREEN_R / JOGS[0][2]
def vslider(x, y0, y1, knob):
    fx, fy0 = to_frame(x, y0); _, fy1 = to_frame(x, y1); return {'x': fx / W, 'y0': fy0 / H, 'y1': fy1 / H, 'kw': knob[0] * S / W, 'kh': knob[1] * S / H}
layout['chans'] = [vslider(x, CH_Y0, CH_Y1, CH_KNOB) for x in CH_X]
layout['tempo'] = [vslider(x, TEMPO_Y0, TEMPO_Y1, TEMPO_KNOB) for x in TEMPO_X]
x0, y0 = to_frame(DISPLAY[0], DISPLAY[1]); x1, y1 = to_frame(DISPLAY[2], DISPLAY[3])
layout['display'] = {'x': x0 / W, 'y': y0 / H, 'w': (x1 - x0) / W, 'h': (y1 - y0) / H}
layout['pads'] = []
for bx0, by0, bx1, by1 in PADS:
    fx0, fy0 = to_frame(bx0, by0); fx1, fy1 = to_frame(bx1, by1)
    layout['pads'].append({'x': (fx0 + fx1) / 2 / W, 'y': (fy0 + fy1) / 2 / H, 'w': (fx1 - fx0) / W, 'h': (fy1 - fy0) / H})
layout['leds'] = [[[v / s for v, s in zip(to_frame(x, y), (W, H))] for y in LED_Y] for x in LED_X]
layout['led'] = {'w': LED_W * S / W, 'h': LED_H * S / H, 'colors': LED_COLORS}
fx0, fy = to_frame(FADER['x0'], FADER['y']); fx1, _ = to_frame(FADER['x1'], FADER['y']); kx0, ky0 = to_frame(*FADER['knob'][:2]); kx1, ky1 = to_frame(*FADER['knob'][2:])
layout['fader'] = {'x0': fx0 / W, 'x1': fx1 / W, 'y': fy / H, 'kw': (kx1 - kx0) / W, 'kh': (ky1 - ky0) / H}
(ROOT / 'app' / 'layout.js').write_text('const LAYOUT = ' + json.dumps(layout) + ';\n')
print('ok: масштаб', round(S, 4), 'срез по', X_CUT, 'px; джоги', [{k: round(v, 4) for k, v in j.items()} for j in layout['jogs']], 'LED цвета', LED_COLORS)
