"""Подгонка клипа под точную сетку: растяжение под заданный темп, старт с сильной доли, обрезка
ровно по тактам, бесшовная петля. Выход — OGG Vorbis для игры.

  python tools/music_fit.py вход.flac выход.ogg [--bpm 124] [--bars 16] [--gain -1]

Шаги: замер темпа (music_check) → ffmpeg rubberband (темп меняется, высота нет) → повторный замер
фазы → сильная доля по басовой огибающей (из четырёх кандидатов) → вырез bars×4 долей →
стык петли: конец вкрещивается в начало (20 мс) → нормализация пика → ffmpeg libvorbis q6.
"""
import argparse, subprocess, sys, tempfile
from pathlib import Path
import numpy as np
from scipy.io import wavfile
from scipy.signal import butter, sosfiltfilt

sys.path.insert(0, str(Path(__file__).parent))
from music_check import load, onset_env, tempo_and_phase  # noqa: E402


def load_stereo(path):
    import av
    c = av.open(path); st = c.streams.audio[0]; sr = st.rate; ch = st.codec_context.channels; parts = []
    for f in c.decode(st):
        x = f.to_ndarray(); x = x if f.format.is_planar else x.reshape(-1, ch).T
        parts.append(x.astype(np.float32) / (32768 if x.dtype == np.int16 else 2147483648 if x.dtype == np.int32 else 1))
    x = np.concatenate(parts, axis=1)
    return (x if x.shape[0] == 2 else np.vstack([x[0], x[0]])), sr


def downbeat(mono, sr, bpm, phase_ms):
    """Из четырёх первых долей выбрать сильную: где бас (40–150 Гц) бьёт сильнее всего по сетке тактов."""
    sos = butter(4, [40, 150], btype='band', fs=sr, output='sos')
    low = np.abs(sosfiltfilt(sos, mono)); env = np.convolve(low, np.ones(int(sr * .02)) / int(sr * .02), 'same')
    beat = 60 / bpm; best = None
    for k in range(4):
        t = phase_ms / 1000 + k * beat; score = []
        while t + beat * 4 < len(mono) / sr:
            i = int(t * sr); score.append(env[i:i + int(sr * .05)].max() - env[i + int(beat * sr * 2):i + int(beat * sr * 2) + int(sr * .05)].max())
            t += beat * 4                                              # сильная доля должна быть громче третьей
        s = float(np.mean(score)) if score else 0
        if best is None or s > best[0]: best = (s, k)
    return phase_ms / 1000 + best[1] * beat


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('src'); ap.add_argument('dst')
    ap.add_argument('--bpm', type=float, default=124); ap.add_argument('--bars', type=int, default=16)
    ap.add_argument('--gain', type=float, default=-1, help='пик после нормализации, дБ')
    a = ap.parse_args()
    tmp = Path(tempfile.mkdtemp())

    mono, sr = load(a.src); env, fps = onset_env(mono, sr)
    bpm, _, score, _ = tempo_and_phase(env, fps, a.bpm)
    ratio = a.bpm / bpm
    print(f'темп {bpm:.2f} → {a.bpm:g} BPM: растяжение ×{ratio:.4f}')
    stretched = tmp / 'stretched.wav'
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', a.src, '-af', f'rubberband=tempo={ratio:.6f}:pitch=1:transients=crisp',
                    '-ar', str(sr), str(stretched)], check=True)

    mono, sr = load(str(stretched)); env, fps = onset_env(mono, sr)
    bpm2, phase_ms, _, _ = tempo_and_phase(env, fps, a.bpm, span=.01, step=.005)
    start = downbeat(mono, sr, a.bpm, phase_ms)
    length = a.bars * 4 * 60 / a.bpm
    print(f'после растяжения {bpm2:.2f} BPM, первая доля +{phase_ms:.0f} мс, сильная доля +{start * 1000:.0f} мс, вырез {length:.3f} с')

    st, sr2 = load_stereo(str(stretched)); n = int(round(length * sr2)); i0 = int(round(start * sr2))
    if i0 + n > st.shape[1]:
        raise SystemExit(f'клип короткий: нужно {length + start:.2f} с, есть {st.shape[1] / sr2:.2f} с — генерируй с запасом (--bars больше)')
    clip = st[:, i0:i0 + n].copy()
    xf = int(sr2 * .02); w = np.linspace(0, 1, xf, dtype=np.float32)      # стык петли: хвост за концом вплавляется в начало
    tail = st[:, i0 + n:i0 + n + xf]
    if tail.shape[1] == xf: clip[:, :xf] = clip[:, :xf] * w + tail * (1 - w)
    clip *= 10 ** (a.gain / 20) / max(1e-6, np.abs(clip).max())
    raw = tmp / 'cut.wav'; wavfile.write(raw, sr2, (clip.T * 32767).astype(np.int16))
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(raw), '-c:a', 'libvorbis', '-q:a', '6', a.dst], check=True)
    print(f'{a.dst}  {Path(a.dst).stat().st_size / 1e6:.2f} МБ')


if __name__ == '__main__':
    main()
