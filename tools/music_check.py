"""Замер темпа и сдвига ритмической сетки у аудиофайлов (torchaudio + numpy, без librosa).

  python tools/music_check.py файл1 [файл2 …] [--bpm 124]

Для каждого файла: длительность, найденный темп (поиск вокруг --bpm ±6 %, шаг 0.01), сдвиг первой
доли от начала файла в мс и уверенность (контраст пика). Для пары файлов — разница сдвигов:
это то, насколько их доли разойдутся при одновременном старте.
"""
import argparse, sys
import numpy as np
import torch


def load(path):
    """Моно float и частота. Через PyAV: у torchaudio в этой сборке нет декодера."""
    import av
    c = av.open(path); st = c.streams.audio[0]; sr = st.rate; ch = st.codec_context.channels; parts = []
    for f in c.decode(st):
        x = f.to_ndarray()
        x = x if f.format.is_planar else x.reshape(-1, ch).T          # упакованный формат: каналы идут вперемежку
        parts.append(x.astype(np.float32) / (32768 if x.dtype == np.int16 else 2147483648 if x.dtype == np.int32 else 1))
    return np.concatenate(parts, axis=1).mean(0), sr


def onset_env(x, sr, hop=256, n_fft=1024):
    """Огибающая атак: положительный прирост спектра по полосам (spectral flux)."""
    spec = torch.stft(torch.from_numpy(x), n_fft, hop, window=torch.hann_window(n_fft), return_complex=True).abs().numpy()
    flux = np.maximum(0, np.diff(np.log1p(20 * spec), axis=1)).sum(0)
    flux = flux - np.convolve(flux, np.ones(64) / 64, 'same')            # убрать медленный дрейф
    return np.maximum(0, flux), sr / hop


def tempo_and_phase(env, fps, bpm0, span=0.06, step=0.01):
    """Перебор темпа: кладём гребёнку из долей на огибающую, ищем темп и фазу с максимальной суммой."""
    t = np.arange(len(env)) / fps; best = None; scores = []
    for bpm in np.arange(bpm0 * (1 - span), bpm0 * (1 + span) + step, step):
        period = 60 / bpm
        ph = (t % period) / period                                       # фаза каждого кадра внутри доли
        bins = np.minimum((ph * 48).astype(int), 47)
        hist = np.bincount(bins, weights=env, minlength=48) / np.maximum(1, np.bincount(bins, minlength=48))
        k = hist.argmax(); score = hist[k] / (hist.mean() + 1e-9)
        scores.append(score)
        if best is None or score > best[0]: best = (score, bpm, (k + .5) / 48 * period)
    return best[1], best[2] * 1000, best[0], float(np.median(scores))


ap = argparse.ArgumentParser(); ap.add_argument('files', nargs='+'); ap.add_argument('--bpm', type=float, default=124)
a = ap.parse_args()
rows = []
for f in a.files:
    x, sr = load(f); env, fps = onset_env(x, sr)
    bpm, off, score, med = tempo_and_phase(env, fps, a.bpm)
    beats = len(x) / sr / (60 / bpm)
    rows.append((f, bpm, off))
    print(f'{f}\n   длина {len(x) / sr:6.2f} с = {beats:6.2f} долей   темп {bpm:7.2f} BPM (задан {a.bpm:g}, отклонение {100 * (bpm / a.bpm - 1):+.2f} %)'
          f'   первая доля +{off:5.1f} мс   контраст {score:.2f} (фон {med:.2f})')
if len(rows) == 2:
    period = 60000 / a.bpm; d = (rows[0][2] - rows[1][2] + period / 2) % period - period / 2
    drift = abs(rows[0][1] - rows[1][1]) / a.bpm * 30000
    print(f'разница сдвига первой доли: {d:+.1f} мс;  расхождение из-за разницы темпов за 30 с: {drift:.0f} мс')
