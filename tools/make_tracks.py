"""Четыре трека под четыре профиля, локально: ACE-Step 1.5 → выбор лучшего сида по чёткости
ритма → Demucs на стемы → пара A/B (ударные+бас / остальное) по общей сетке → app/audio.

  python tools/make_tracks.py [--seeds 3] [--only house,techno] [--skip-gen]

Нужны запущенный ComfyUI и venv ComfyUI (demucs, torch). Результат: app/audio/<жанр>_a.ogg, _b.ogg.
"""
import argparse, json, re, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable; T = ROOT / 'tools'; OUT = T / 'out' / 'music'
# жанр → профиль: 0 THE SELECTOR, 1 THE TECHNICIAN, 2 THE CROWD READER, 3 THE EXPERIMENTER
GENRES = {
    'house':  dict(bpm=124, key='A minor', bars=16, profile=0, tags='deep house, warm piano chords, filtered disco sample, groovy bassline, four-on-the-floor kick, crisp hi-hats, club mix, instrumental, no vocals'),
    'techno': dict(bpm=130, key='F minor', bars=16, profile=1, tags='driving techno, rumbling kick, hypnotic synth sequence, industrial percussion, dark, relentless, club mix, instrumental, no vocals'),
    'disco':  dict(bpm=122, key='D minor', bars=16, profile=2, tags='funky disco house, brass stabs, slap bass, rhythm guitar, big room energy, hands in the air, club mix, instrumental, no vocals'),
    'dnb':    dict(bpm=174, key='E minor', bars=24, profile=3, tags='liquid drum and bass, fast breakbeat, deep reese bass, atmospheric pads, rolling, energetic, instrumental, no vocals'),
}


def run(*cmd, capture=False):
    r = subprocess.run([str(c) for c in cmd], text=True, capture_output=capture, encoding='utf-8', errors='replace')
    if r.returncode: raise SystemExit(f'ошибка: {" ".join(map(str, cmd))}\n{r.stderr if capture else ""}')
    return r.stdout if capture else ''


def contrast(path, bpm):
    out = run(PY, T / 'music_check.py', path, '--bpm', bpm, capture=True)
    m = re.search(r'контраст ([\d.]+)', out); return float(m.group(1)) if m else 0


ap = argparse.ArgumentParser(); ap.add_argument('--seeds', type=int, default=3); ap.add_argument('--only', default=''); ap.add_argument('--skip-gen', action='store_true')
a = ap.parse_args()
chosen = {}
for name, g in GENRES.items():
    if a.only and name not in a.only.split(','): continue
    best = None
    for seed in range(1, a.seeds + 1):
        f = OUT / f'{name}_{seed}.flac'
        if not a.skip_gen or not f.exists():
            run(PY, T / 'gen_music.py', name, g['tags'], '--bpm', g['bpm'], '--key', g['key'], '--bars', g['bars'] + 8, '--seed', seed)
        c = contrast(f, g['bpm']); print(f'  {name} сид {seed}: чёткость ритма {c:.1f}')
        if best is None or c > best[0]: best = (c, f)
    src = best[1]; print(f'{name}: берём {src.name}')
    run(PY, '-m', 'demucs', '-n', 'htdemucs', '-d', 'cuda', '-o', OUT / 'stems', src)
    run(PY, T / 'music_pair.py', OUT / 'stems' / 'htdemucs' / src.stem, ROOT / 'app' / 'audio' / name, '--bpm', g['bpm'], '--bars', g['bars'], '--bleed', '0.2')
    chosen[name] = dict(seed=int(src.stem.split('_')[-1]), **{k: v for k, v in g.items() if k != 'tags'})
json.dump(chosen, open(OUT / 'chosen.json', 'w'), indent=1)
print('готово:', chosen)
