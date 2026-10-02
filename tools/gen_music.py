"""Музыка через локальный ComfyUI + ACE-Step 1.5 (turbo, всё в одном файле).

  python tools/gen_music.py NAME "теги" [--bpm 124] [--key "A minor"] [--bars 16] [--seed 1] [--lyrics "[instrumental]"]

Длительность считается из темпа и числа тактов (размер 4/4). Результат — tools/out/music/NAME_<seed>.flac.
Сервер должен быть запущен: "D:/!Claude/Image Generation/comfy.sh".
Модель: C:/AI/ComfyUI-models/checkpoints/ace_step_1.5_turbo_aio.safetensors (Comfy-Org/ace_step_1.5_ComfyUI_files).
"""
import argparse, json, time, urllib.request, urllib.parse
from pathlib import Path

API = 'http://127.0.0.1:8188'
OUT = Path(__file__).resolve().parent / 'out' / 'music'
CKPT = 'ace_step_1.5_turbo_aio.safetensors'


def workflow(tags, lyrics, bpm, key, seconds, seed, prefix):
    return {
        '1': {'class_type': 'CheckpointLoaderSimple', 'inputs': {'ckpt_name': CKPT}},
        '2': {'class_type': 'ModelSamplingAuraFlow', 'inputs': {'model': ['1', 0], 'shift': 3}},
        '3': {'class_type': 'TextEncodeAceStepAudio1.5', 'inputs': {
            'clip': ['1', 1], 'tags': tags, 'lyrics': lyrics, 'seed': seed, 'bpm': bpm, 'duration': seconds,
            'timesignature': '4', 'language': 'en', 'keyscale': key, 'generate_audio_codes': True,
            'cfg_scale': 2.0, 'temperature': 0.85, 'top_p': 0.9, 'top_k': 0, 'min_p': 0.0}},
        '4': {'class_type': 'ConditioningZeroOut', 'inputs': {'conditioning': ['3', 0]}},
        '5': {'class_type': 'EmptyAceStep1.5LatentAudio', 'inputs': {'seconds': seconds, 'batch_size': 1}},
        '6': {'class_type': 'KSampler', 'inputs': {'model': ['2', 0], 'positive': ['3', 0], 'negative': ['4', 0], 'latent_image': ['5', 0],
                                                   'seed': seed, 'steps': 8, 'cfg': 1.0, 'sampler_name': 'euler', 'scheduler': 'simple', 'denoise': 1.0}},
        '7': {'class_type': 'VAEDecodeAudio', 'inputs': {'samples': ['6', 0], 'vae': ['1', 2]}},
        '8': {'class_type': 'SaveAudio', 'inputs': {'audio': ['7', 0], 'filename_prefix': prefix}},
    }


def run(wf, timeout=900):
    req = urllib.request.Request(API + '/prompt', data=json.dumps({'prompt': wf}).encode(), headers={'Content-Type': 'application/json'})
    try:
        pid = json.loads(urllib.request.urlopen(req).read())['prompt_id']
    except urllib.error.HTTPError as e:
        raise SystemExit('ComfyUI отклонил задание: ' + e.read().decode('utf-8', 'replace')[:1500])
    t0 = time.time()
    while time.time() - t0 < timeout:
        h = json.loads(urllib.request.urlopen(f'{API}/history/{pid}').read())
        if pid in h:
            st = h[pid].get('status', {})
            if st.get('status_str') == 'error':
                raise SystemExit('ошибка в ComfyUI: ' + json.dumps(st.get('messages', [])[-1:], ensure_ascii=False)[:1500])
            for out in h[pid].get('outputs', {}).values():
                for a in out.get('audio', []):
                    return urllib.request.urlopen(f'{API}/view?' + urllib.parse.urlencode(a)).read(), a['filename']
        time.sleep(1)
    raise SystemExit('не дождался результата')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('name'); ap.add_argument('tags')
    ap.add_argument('--bpm', type=int, default=124); ap.add_argument('--key', default='A minor')
    ap.add_argument('--bars', type=int, default=16); ap.add_argument('--seed', type=int, default=1)
    ap.add_argument('--lyrics', default='[instrumental]')
    a = ap.parse_args()
    seconds = round(a.bars * 4 * 60 / a.bpm, 2)
    OUT.mkdir(parents=True, exist_ok=True)
    t = time.time()
    data, fn = run(workflow(a.tags, a.lyrics, a.bpm, a.key, seconds, a.seed, f'djw_{a.name}'))
    p = OUT / f'{a.name}_{a.seed}{Path(fn).suffix}'
    p.write_bytes(data)
    print(f'{p}  {seconds} с ({a.bars} тактов при {a.bpm} BPM, {a.key})  за {time.time() - t:.0f} с')


if __name__ == '__main__':
    main()
