"""Треки заказчика → игра: общий темп, общая длина, петля. Один OGG на трек, без стемов.

  python tools/prep_tracks.py [tracks/*.wav] [--bpm 124] [--bars N] [--q 5]

Для каждого файла: темп (широкий перебор 80–180) → ffmpeg rubberband к общему темпу (высота не меняется) →
сетка долей, сильная доля по басу → вырез от первой сильной доли длиной --bars тактов (по умолчанию —
самый короткий трек, кратно 4 тактам) → стык петли 20 мс → пик −1 дБ → app/audio/<слаг>.ogg.
В конце печатает строки для DATA.tracks. Растянутые файлы кэшируются в tools/out/tracks/.
"""
import argparse, json, re, subprocess, sys, tempfile
from pathlib import Path
import numpy as np
from scipy.io import wavfile

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, str(Path(__file__).parent))
from music_check import load, onset_env, tempo_and_phase   # noqa: E402
from music_fit import load_stereo, downbeat                # noqa: E402

ROOT = Path(__file__).resolve().parent.parent; OUT = ROOT / 'tools' / 'out' / 'tracks'; AUDIO = ROOT / 'app' / 'audio'
ap = argparse.ArgumentParser(); ap.add_argument('files', nargs='*'); ap.add_argument('--bpm', type=float, default=124)
ap.add_argument('--bars', type=int, default=0); ap.add_argument('--q', type=int, default=5)
a = ap.parse_args(); OUT.mkdir(parents=True, exist_ok=True)
files = [Path(f) for f in a.files] or sorted(p for p in (ROOT / 'tracks').iterdir() if p.suffix.lower() in ('.wav', '.mp3', '.flac', '.aif', '.aiff'))
slug = lambda p: re.sub(r'[^a-z0-9]+', '', re.sub(r'\(.*?\)|demo|dj akee', '', p.stem, flags=re.I).lower())[:12] or 'track'
title = lambda p: re.sub(r'\s*\(.*?\)|\s*-\s*DEMO', '', re.sub(r'^DJ Akee\s*-\s*', '', p.stem, flags=re.I), flags=re.I).strip().upper()


def tempo_wide(mono, sr):
    """80…180 шагом 0.1 (сетка проходит через целые — у треков из DAW темп целый), потом точно вокруг лучшего."""
    env, fps = onset_env(mono, sr); t = np.arange(len(env)) / fps
    def score(bpm):
        period = 60 / bpm; bins = np.minimum(((t % period) / period * 48).astype(int), 47)
        hist = np.bincount(bins, weights=env, minlength=48) / np.maximum(1, np.bincount(bins, minlength=48)); return hist.max() / (hist.mean() + 1e-9)
    grid = np.arange(80, 180.001, .1); best = grid[int(np.argmax([score(b) for b in grid]))]
    bpm, _, sc, _ = tempo_and_phase(env, fps, best, span=.005, step=.01)
    return bpm, sc


bar = 4 * 60 / a.bpm; prepared = []
for src in files:
    tag = slug(src); mono, sr = load(str(src)); bpm, sc = tempo_wide(mono, sr); ratio = a.bpm / bpm
    print(f'\n{src.name}: {len(mono) / sr:.1f} с, темп {bpm:.2f} BPM (контраст {sc:.1f}) -> {a.bpm:g}, растяжение x{ratio:.4f}')
    stretched = OUT / f'{tag}_{a.bpm:g}.wav'
    if not stretched.exists():
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(src), '-af', f'rubberband=tempo={ratio:.6f}:pitch=1:transients=crisp', '-ar', str(sr), '-c:a', 'pcm_s16le', str(stretched)], check=True)
    st, sr = load_stereo(str(stretched)); m = st.mean(0)
    env, fps = onset_env(m, sr); local, phase_ms, c, _ = tempo_and_phase(env, fps, a.bpm, span=.01, step=.005)
    t0 = downbeat(m, sr, a.bpm, phase_ms); n_bars = int((st.shape[1] / sr - t0) / bar)
    print(f'  после растяжения {local:.3f} BPM (контраст {c:.1f}), сильная доля +{t0 * 1000:.0f} мс, полных тактов {n_bars}')
    prepared.append(dict(src=src, tag=tag, st=st, sr=sr, t0=t0, n_bars=n_bars))

bars = a.bars or min(p['n_bars'] for p in prepared) // 4 * 4
print(f'\nобщая длина: {bars} тактов = {bars * bar:.1f} с при {a.bpm:g} BPM')
rows = []
for p in prepared:
    st, sr = p['st'], p['sr']; n = int(round(bars * bar * sr)); i0 = int(round(p['t0'] * sr))
    if i0 + n > st.shape[1]: raise SystemExit(f'{p["src"].name}: короче общей длины')
    clip = st[:, i0:i0 + n].copy()
    xf = int(sr * .02); w = np.linspace(0, 1, xf, dtype=np.float32); tail = st[:, i0 + n:i0 + n + xf]
    if tail.shape[1] == xf: clip[:, :xf] = clip[:, :xf] * w + tail * (1 - w)       # стык петли: хвост за концом вплавляется в начало
    clip *= 10 ** (-1 / 20) / max(1e-6, np.abs(clip).max())
    tmp = Path(tempfile.mkdtemp()); raw = tmp / 'cut.wav'; wavfile.write(raw, sr, (clip.T * 32767).astype(np.int16))
    dst = AUDIO / f'{p["tag"]}.ogg'
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(raw), '-c:a', 'libvorbis', '-q:a', str(a.q), str(dst)], check=True)
    print(f'  {dst.name}  {n / sr:.1f} с  {dst.stat().st_size / 1e6:.1f} МБ')
    rows.append(dict(name=title(p['src']), url=f'audio/{p["tag"]}.ogg'))

print('\nDATA.tracks:')
for r in rows: print('    ' + json.dumps(r, ensure_ascii=False) + ',')
print(f'DATA.bpm = {a.bpm:g}, DATA.bars = {bars}')
