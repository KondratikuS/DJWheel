"""Обрезает сгенерированную картинку по кругу объекта (диск, пад) в квадрат и сохраняет PNG.
  python tools/crop_circle.py in.png out.png [--thr 22] [--pad 0.01]"""
import sys, argparse
from PIL import Image
import numpy as np
ap = argparse.ArgumentParser(); ap.add_argument('src'); ap.add_argument('dst'); ap.add_argument('--thr', type=int, default=22); ap.add_argument('--pad', type=float, default=0.01); ap.add_argument('--size', type=int, default=1024)
a = ap.parse_args()
im = Image.open(a.src).convert('RGB'); g = np.asarray(im.convert('L'))
ys, xs = np.where(g > a.thr)
cx, cy = (xs.min() + xs.max()) / 2, (ys.min() + ys.max()) / 2
r = max(xs.max() - xs.min(), ys.max() - ys.min()) / 2 * (1 + a.pad)
box = (int(cx - r), int(cy - r), int(cx + r), int(cy + r))
out = im.crop(box).resize((a.size, a.size), Image.LANCZOS)
# альфа по кругу, чтобы углы были прозрачными
m = np.zeros((a.size, a.size), np.uint8); yy, xx = np.ogrid[:a.size, :a.size]
m[(xx - a.size / 2) ** 2 + (yy - a.size / 2) ** 2 <= (a.size / 2) ** 2] = 255
out.putalpha(Image.fromarray(m)); out.save(a.dst); print(a.dst, box)
