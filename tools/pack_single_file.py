"""Собирает app/index.html и все картинки/звуки из app/ в один файл dist/DJWheel.html (base64 внутри)."""
import base64, re, mimetypes, json
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
APP, DIST = ROOT / 'app', ROOT / 'dist'
html = (APP / 'index.html').read_text(encoding='utf-8')

def data_uri(rel):
    p = APP / rel
    if not p.is_file(): return None
    mime = mimetypes.guess_type(p.name)[0] or 'application/octet-stream'
    return f'data:{mime};base64,' + base64.b64encode(p.read_bytes()).decode()

missing = []
def repl(m):
    rel = m.group(2); uri = data_uri(rel)
    if uri is None: missing.append(rel); return m.group(0)
    return m.group(1) + uri + m.group(3)
# src="img/..." / xlink:href="img/..." / url(img/...) / 'img/...' в JS
html = re.sub(r'((?:src|href)=")(img/[^"]+)(")', repl, html)
html = re.sub(r'(url\()(img/[^)]+)(\))', repl, html)
html = re.sub(r"(= ')(img/[^']+)(')", repl, html)
# layout.js — внутрь страницы; картинки, которые страница подставляет сама (ручки фейдеров) — в IMG
for js in ('layout.js', 'midi.js'):
    html = html.replace(f'<script src="{js}"></script>', '<script>\n' + (APP / js).read_text(encoding='utf-8') + '</script>')
imgs = {p.name: data_uri('img/' + p.name) for p in sorted((APP / 'img').glob('*.png'))}
html = html.replace('const IMG = {};', 'const IMG = ' + json.dumps(imgs) + ';')
DIST.mkdir(exist_ok=True)
out = DIST / 'DJWheel.html'; out.write_text(html, encoding='utf-8')
print(out, f'{out.stat().st_size/1e6:.1f} MB', 'missing:', missing or 'none')
