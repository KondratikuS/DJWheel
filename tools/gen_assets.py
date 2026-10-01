"""Картинки для DJ Wheel через локальный ComfyUI + Flux (воркспейс Image Generation).

  python tools/gen_assets.py [bg|wheel|pad] [--seeds N]

Кладёт варианты в tools/out/<name>_<seed>.png, выбранный переименовать в app/img/<name>.png.
Сервер должен быть запущен: "D:/!Claude/Image Generation/comfy.sh".
"""
import argparse, sys, random
from pathlib import Path

sys.path.insert(0, r'D:\!Claude\Image Generation\tools')
from gen import run  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'tools' / 'out'
CKPT = 'flux1-dev-fp8.safetensors'

ASSETS = {
    'bg': dict(width=1920, height=1088, prompt=(
        'top-down photograph of a professional DJ controller surface, dark brushed black metal and matte plastic, '
        'rows of small rubber knobs, faders and rectangular pads along the left and right edges, '
        'the wide centre of the panel is a plain empty dark surface with nothing on it, '
        'subtle grain, cinematic low key studio lighting, slight vignette, product photography, ultra detailed, 8k')),
    'wheel': dict(width=1024, height=1024, prompt=(
        'top-down photograph of a single large round DJ jog wheel, black aluminium platter with fine concentric machined grooves, '
        'brushed steel outer rim with a bevel, small dark centre cap, perfectly centred, filling the frame, '
        'on a pure black background, cinematic low key studio lighting with a soft highlight on the rim, '
        'product photography, ultra detailed, 8k')),
    'pad': dict(width=512, height=512, prompt=(
        'top-down photograph of a single round black rubber drum pad button from a DJ controller, '
        'soft matte rubber, slight dome, thin metal bezel, perfectly centred, filling the frame, '
        'on a pure black background, low key studio lighting, product photography, ultra detailed')),
}


def workflow(a, seed, prefix):
    return {
        '1': {'class_type': 'CheckpointLoaderSimple', 'inputs': {'ckpt_name': CKPT}},
        '2': {'class_type': 'CLIPTextEncode', 'inputs': {'clip': ['1', 1], 'text': a['prompt']}},
        '3': {'class_type': 'FluxGuidance', 'inputs': {'conditioning': ['2', 0], 'guidance': 3.5}},
        '4': {'class_type': 'ConditioningZeroOut', 'inputs': {'conditioning': ['2', 0]}},
        '5': {'class_type': 'EmptySD3LatentImage', 'inputs': {'width': a['width'], 'height': a['height'], 'batch_size': 1}},
        '6': {'class_type': 'KSampler', 'inputs': {'model': ['1', 0], 'positive': ['3', 0], 'negative': ['4', 0], 'latent_image': ['5', 0],
                                                   'seed': seed, 'steps': 24, 'cfg': 1.0, 'sampler_name': 'euler', 'scheduler': 'simple', 'denoise': 1.0}},
        '7': {'class_type': 'VAEDecode', 'inputs': {'samples': ['6', 0], 'vae': ['1', 2]}},
        '8': {'class_type': 'SaveImage', 'inputs': {'images': ['7', 0], 'filename_prefix': prefix}},
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('names', nargs='*', default=list(ASSETS))
    ap.add_argument('--seeds', type=int, default=3)
    ap.add_argument('--seed', type=int, default=None)
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    for name in args.names:
        a = ASSETS[name]
        seeds = [args.seed] if args.seed is not None else [random.randrange(1 << 31) for _ in range(args.seeds)]
        for seed in seeds:
            png = run(workflow(a, seed, f'djw_{name}'))
            p = OUT / f'{name}_{seed}.png'
            p.write_bytes(png)
            print(p)


if __name__ == '__main__':
    main()
