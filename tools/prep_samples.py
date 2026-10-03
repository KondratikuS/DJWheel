"""Готовые семплы (Pixabay и т. п.) → пады: обрезка тишины, выравнивание громкости, OGG.

  python tools/prep_samples.py kick=файл.mp3 hat=файл.mp3 … [--rms -12] [--peak -1] [--max 2.5]

Громкость выравнивается по самому громкому окну 100 мс (RMS → --rms дБFS), пик не выше --peak;
начало режется по порогу −45 дБ, хвост — по −60 дБ с плавным спадом, длина не больше --max с.
"""
import argparse, subprocess, sys, tempfile
from pathlib import Path
import numpy as np
from scipy.io import wavfile

sys.path.insert(0, str(Path(__file__).parent))
from music_fit import load_stereo  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / 'app' / 'audio'
ap = argparse.ArgumentParser(); ap.add_argument('pairs', nargs='+'); ap.add_argument('--rms', type=float, default=-12)
ap.add_argument('--peak', type=float, default=-1); ap.add_argument('--max', type=float, default=2.5); a = ap.parse_args()
tmp = Path(tempfile.mkdtemp())
for pair in a.pairs:
    name, src = pair.split('=', 1); x, sr = load_stereo(src); mono = np.abs(x).max(0)
    i0 = int(np.argmax(mono > 10 ** (-45 / 20))); i0 = max(0, i0 - int(sr * .003))
    above = np.where(mono > 10 ** (-60 / 20))[0]; i1 = min(int(above[-1]) + int(sr * .05), i0 + int(sr * a.max)) if len(above) else len(mono)
    y = x[:, i0:i1].copy(); n = min(y.shape[1], int(sr * .03)); y[:, -n:] *= np.linspace(1, 0, n, dtype=np.float32)
    w = int(sr * .1); e = np.convolve(y.mean(0) ** 2, np.ones(w) / w, 'valid'); loud = np.sqrt(e.max()) if len(e) else np.sqrt(np.mean(y ** 2))
    g = 10 ** (a.rms / 20) / max(1e-6, loud); g = min(g, 10 ** (a.peak / 20) / max(1e-6, np.abs(y).max()))
    y *= g
    raw = tmp / f'{name}.wav'; wavfile.write(raw, sr, (y.T * 32767).astype(np.int16)); dst = OUT / f'{name}.ogg'
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(raw), '-c:a', 'libvorbis', '-q:a', '6', str(dst)], check=True)
    print(f'{name:6} {Path(src).name[:44]:44} {y.shape[1] / sr:5.2f} с  громк. {20 * np.log10(loud * g):6.1f} дБ  пик {20 * np.log10(np.abs(y).max()):6.1f} дБ')
