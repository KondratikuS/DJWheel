"""Пара A/B из стемов одного трека: A = ударные + бас, B = остальное (мелодия, вокал).
Сумма A + B = исходный трек, поэтому фейдер на середине даёт полный микс, а края — чистый ритм
или чистую мелодию. Оба режутся по одной сетке из одного места — совпадают по построению.

  python tools/music_pair.py tools/out/music/stems/htdemucs/suno_1 app/audio/suno1 [--bpm 124] [--bars 16] [--start-bar N]

Темп и сильную долю меряем по сумме стемов; окно в bars тактов берём самое громкое, если
--start-bar не задан (кратно 4 тактам от первой сильной доли). Выход: <префикс>_a.ogg, _b.ogg.
"""
import argparse, subprocess, sys, tempfile
from pathlib import Path
import numpy as np
from scipy.io import wavfile

sys.path.insert(0, str(Path(__file__).parent))
from music_check import onset_env, tempo_and_phase  # noqa: E402
from music_fit import load_stereo, downbeat          # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument('stems'); ap.add_argument('prefix')
ap.add_argument('--bpm', type=float, default=124); ap.add_argument('--bars', type=int, default=16)
ap.add_argument('--start-bar', type=int, default=None); ap.add_argument('--gain', type=float, default=-1)
a = ap.parse_args()
S = Path(a.stems); tmp = Path(tempfile.mkdtemp())
names = ['drums', 'bass', 'other', 'vocals']

# 1. темп по ударным (чистые атаки), одно растяжение на все стемы
st = {n: load_stereo(str(S / f'{n}.wav')) for n in names}; sr = st['drums'][1]
env, fps = onset_env(st['drums'][0].mean(0), sr); bpm, _, score, _ = tempo_and_phase(env, fps, a.bpm)
ratio = a.bpm / bpm
print(f'темп по всему треку {bpm:.2f} BPM (контраст {score:.1f})')


def stretch(ratio):
    out = {}
    for n in names:
        dst = tmp / f'{n}.wav'
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(S / f'{n}.wav'), '-af', f'rubberband=tempo={ratio:.6f}:pitch=1:transients=crisp', '-ar', str(sr), str(dst)], check=True)
        out[n] = load_stereo(str(dst))[0]
    L = min(x.shape[1] for x in out.values()); return {n: x[:, :L] for n, x in out.items()}, L


def window(out, L):
    """сетка по ударным, окно — самое громкое по полному миксу (кратно 4 тактам) или заданное"""
    drums = out['drums'].mean(0); mix = sum(out.values()).mean(0)
    env, fps = onset_env(drums, sr); _, phase_ms, _, _ = tempo_and_phase(env, fps, a.bpm, span=.01, step=.005)
    t_down = downbeat(mix, sr, a.bpm, phase_ms)
    bar = 4 * 60 / a.bpm; n_bars = int((L / sr - t_down) / bar)
    rms = lambda i0, i1: float(np.sqrt(np.mean(mix[i0:i1] ** 2)))
    sb = a.start_bar
    if sb is None:
        cands = [(rms(int((t_down + b * bar) * sr), int((t_down + (b + a.bars) * bar) * sr)), b) for b in range(0, n_bars - a.bars + 1, 4)]
        sb = max(cands)[1] if cands else 0
    t0 = t_down + sb * bar; n = int(round(a.bars * bar * sr)); i0 = int(round(t0 * sr))
    if i0 + n > L: raise SystemExit('трек короче окна')
    return i0, n, sb, t0, bar


# 2. растяжение с уточнением: темп меряем уже внутри выбранного окна по ударным — у трека он может плавать
for it in range(4):
    out, L = stretch(ratio); i0, n, sb, t0, bar = window(out, L)
    env, fps = onset_env(out['drums'].mean(0)[i0:i0 + n], sr)
    local, _, c, _ = tempo_and_phase(env, fps, a.bpm, span=.03, step=.005)
    print(f'  ×{ratio:.4f}: окно такты {sb}…{sb + a.bars} ({t0:.1f}–{t0 + a.bars * bar:.1f} с), темп в окне {local:.2f} BPM (контраст {c:.1f})')
    if abs(local / a.bpm - 1) < .0015: break
    ratio *= a.bpm / local

# 3. A и B, общий стык петли и общая нормализация (сумма остаётся исходным балансом)
def cut(x):
    c = x[:, i0:i0 + n].copy(); xf = int(sr * .02); w = np.linspace(0, 1, xf, dtype=np.float32); tail = x[:, i0 + n:i0 + n + xf]
    if tail.shape[1] == xf: c[:, :xf] = c[:, :xf] * w + tail * (1 - w)
    return c
A = cut(out['drums']) + cut(out['bass']); B = cut(out['other']) + cut(out['vocals'])
g = 10 ** (a.gain / 20) / max(1e-6, np.abs(A + B).max())
for tag, x in (('a', A), ('b', B)):
    raw = tmp / f'{tag}.wav'; wavfile.write(raw, sr, ((x * g).T * 32767).astype(np.int16))
    dst = f'{a.prefix}_{tag}.ogg'
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(raw), '-c:a', 'libvorbis', '-q:a', '6', dst], check=True)
    print(f'{dst}  {Path(dst).stat().st_size / 1e6:.2f} МБ')
