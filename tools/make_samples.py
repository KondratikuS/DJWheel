"""Семплы для падов: ударные — настоящие удары, вырезанные из стемов сгенерированных треков
(кик, хэт, хлопок, малый), остальное (том, тарелка, хорн, лазер) — синтез офлайн на 48 кГц
с нормальной обработкой, не WebAudio-писк. Выход: app/audio/<имя>.ogg.

  python tools/make_samples.py [--kick stems/house] [--hat stems/house] [--clap stems/disco] [--snare stems/dnb]

Папка стемов — та, что сделал demucs (с drums.wav). Удар выбирается самый громкий из одиночных
(до и после — не меньше 250 мс тишины по атакам), класс — по спектру первых 40 мс.
"""
import argparse, subprocess, sys, tempfile
from pathlib import Path
import numpy as np
from scipy.io import wavfile
from scipy.signal import butter, sosfiltfilt, sosfilt

sys.path.insert(0, str(Path(__file__).parent))
from music_fit import load_stereo  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'app' / 'audio'; STEMS = ROOT / 'tools' / 'out' / 'music' / 'stems' / 'htdemucs'
SR = 48000


def band_energy(x, sr, lo, hi):
    sos = butter(4, [lo, min(hi, sr / 2 - 1)], btype='band', fs=sr, output='sos'); y = sosfiltfilt(sos, x); return float(np.mean(y ** 2))


def hits(stem_dir, kind):
    """Одиночные удары нужного класса из drums.wav: список (громкость, фрагмент стерео).
    Атаки ищем в своей полосе: кик — низ, хэт — верх, хлопок/малый — середина; одиночность — свой зазор."""
    st, sr = load_stereo(str(Path(stem_dir) / 'drums.wav')); mono = st.mean(0)
    lo, hi = {'kick': (30, 150), 'hat': (5000, 16000), 'mid': (150, 2500)}[kind]
    gap_need = {'kick': .25, 'hat': .11, 'mid': .18}[kind]
    sos = butter(4, [lo, min(hi, sr / 2 - 1)], btype='band', fs=sr, output='sos'); band = sosfiltfilt(sos, mono)
    env = np.abs(band); env = np.convolve(env, np.ones(int(sr * .005)) / int(sr * .005), 'same')
    d = np.diff(env, prepend=0); thr = np.percentile(d, 99.5)
    on = np.where((d > thr) & (env > env.max() * .3))[0]
    on = on[np.insert(np.diff(on) > int(sr * .04), 0, True)]              # склеить близкие
    # атаки всего стема — чтобы рядом не было чужих ударов
    full = np.abs(mono); full = np.convolve(full, np.ones(int(sr * .005)) / int(sr * .005), 'same'); fd = np.diff(full, prepend=0)
    allon = np.where(fd > np.percentile(fd, 99.3))[0]; allon = allon[np.insert(np.diff(allon) > int(sr * .04), 0, True)]
    if kind == 'kick': allon = on                                           # кику мешают только соседние кики: хэт поверх — норма
    res = []
    for i in on:
        others = allon[(allon != i) & (np.abs(allon - i) > int(sr * .02))]
        if len(others) and np.min(np.abs(others - i)) / sr < gap_need: continue
        seg = mono[i:i + int(sr * .04)]
        e_lo, e_mid, e_hi = band_energy(seg, sr, 30, 150), band_energy(seg, sr, 150, 2500), band_energy(seg, sr, 5000, 16000)
        cls = 'kick' if e_lo > e_mid and e_lo > e_hi * 3 else 'hat' if e_hi > e_mid and e_hi > e_lo * 3 else 'mid'
        if cls != kind: continue
        n = int(sr * (.45 if kind == 'kick' else .16 if kind == 'hat' else .35))
        frag = st[:, max(0, i - int(sr * .002)):i + n].copy()
        spec = np.abs(np.fft.rfft(seg * np.hanning(len(seg)))) + 1e-9
        flat = float(np.exp(np.mean(np.log(spec))) / np.mean(spec))               # плоскость спектра: шум ≈ 1, тон ≈ 0
        res.append((float(np.abs(frag).max()), frag, sr, flat))
    res.sort(key=lambda t: -t[0]); return res


def fade_tail(x, sr, ms=40):
    n = min(x.shape[1], int(sr * ms / 1000)); x[:, -n:] *= np.linspace(1, 0, n, dtype=np.float32); return x


PEAK = {'kick': .9, 'hat': .55, 'clap': .8, 'snare': .85, 'tom': .75, 'crash': .55, 'horn': .6, 'laser': .5}   # баланс громкости падов


def write(name, x, sr):
    x = x / max(1e-6, np.abs(x).max()) * PEAK.get(name, .8)
    tmp = Path(tempfile.mkdtemp()) / 'x.wav'; wavfile.write(tmp, sr, (x.T * 32767).astype(np.int16))
    dst = OUT / f'{name}.ogg'; subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(tmp), '-c:a', 'libvorbis', '-q:a', '6', str(dst)], check=True)
    print(f'{dst.name}: {x.shape[1] / sr:.2f} с')


# ── синтез ──
def t_(sec): return np.arange(int(SR * sec)) / SR
def env_exp(sec, tau): t = t_(sec); return np.exp(-t / tau)
def lp(x, f, order=2): return sosfilt(butter(order, f, fs=SR, output='sos'), x)
def hp(x, f, order=2): return sosfilt(butter(order, f, btype='high', fs=SR, output='sos'), x)
def bp(x, lo, hi, order=2): return sosfilt(butter(order, [lo, hi], btype='band', fs=SR, output='sos'), x)
def stereo(x, width=0.0):
    x = x.astype(np.float32); r = np.roll(x, int(SR * width * .002)) if width else x; return np.vstack([x, r])


def tom():
    t = t_(.6); f = 95 + (230 - 95) * np.exp(-t * 14)
    body = np.sin(2 * np.pi * np.cumsum(f) / SR) * env_exp(.6, .17)
    click = hp(np.random.randn(len(t)), 2000) * env_exp(.6, .004) * .3
    ring = np.sin(2 * np.pi * np.cumsum(f * 1.5) / SR) * env_exp(.6, .06) * .25
    return stereo(lp(body + click + ring, 4000))


def crash():
    sec = 1.8; t = t_(sec); n = np.random.randn(len(t))
    noise = hp(bp(n, 3000, 14000), 2500) * env_exp(sec, .55)
    partials = sum(np.sin(2 * np.pi * f * t + p) * env_exp(sec, .4 + .1 * i) for i, (f, p) in enumerate([(2317, .3), (3177, 1.1), (4019, 2), (5311, .7), (6833, 1.5), (8071, 2.6)])) / 6
    x = noise * .8 + partials * .35; x *= 1 - np.exp(-t / .003)
    return stereo(x, width=1.0)


def horn():
    sec = .9; t = t_(sec); x = np.zeros(len(t))
    for f, g in [(233.1, 1), (311.1, .9), (349.2, .8), (466.2, .35)]:
        vib = 1 + .004 * np.sin(2 * np.pi * 5.5 * t); ph = 2 * np.pi * np.cumsum(f * vib) / SR
        x += g * (2 * ((ph / (2 * np.pi)) % 1) - 1)                          # пила
    x = bp(x, 400, 3200) + bp(x, 800, 1200) * .8 + bp(x, 1700, 2400) * .5     # форманты рупора
    a = np.minimum(1, t / .025); r = np.where(t > sec - .08, (sec - t) / .08, 1)
    return stereo(np.tanh(x * .9) * a * r, width=.6)


def laser():
    sec = .4; t = t_(sec); f = 3600 * np.exp(-t * 9) + 120
    ph = 2 * np.pi * np.cumsum(f) / SR; x = np.sin(ph + .6 * np.sin(2 * np.pi * 50 * t)) + .3 * np.sign(np.sin(ph * 2))
    return stereo(lp(x, 9000) * env_exp(sec, .12) * (1 - np.exp(-t / .002)))


ap = argparse.ArgumentParser()
for k, d in [('kick', 'house'), ('hat', 'house'), ('clap', 'disco'), ('snare', 'dnb')]: ap.add_argument('--' + k, default=d)
ap.add_argument('--stems', default=str(STEMS), help='папка htdemucs со стемами')
a = ap.parse_args(); OUT.mkdir(exist_ok=True); STEMS = Path(a.stems)
for name, src, kind in [('kick', a.kick, 'kick'), ('hat', a.hat, 'hat'), ('clap', a.clap, 'mid'), ('snare', a.snare, 'mid')]:
    stem = next(STEMS.glob(src + '_*'), None) or (STEMS / src)
    found = hits(stem, kind); used = stem.name
    if not found:                                                            # в этом треке нет — ищем по всем стемам
        for alt in sorted(STEMS.iterdir()):
            found = hits(alt, kind)
            if found: used = alt.name; break
    if not found: print(f'{name}: одиночных ударов класса {kind} нет ни в одном треке'); continue
    top = found[:10]                                                        # среди громких: хлопок — самый шумный, малый — самый «телесный»
    pick = max(top, key=lambda t: t[3]) if name == 'clap' else min(top, key=lambda t: t[3]) if name == 'snare' else top[0]
    vol, frag, sr, flat = pick; print(f'{name}: из {used}, {len(found)} кандидатов, плоскость {flat:.2f}'); write(name, fade_tail(frag, sr, 25 if kind == 'hat' else 40), sr)
for name, fn in [('tom', tom), ('crash', crash), ('horn', horn), ('laser', laser)]:
    np.random.seed(7); write(name, fn(), SR)
