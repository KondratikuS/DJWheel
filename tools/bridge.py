"""Мост: события игры → Resolume и grandMA (OSC по сети) и, при желании, MIDI-порт.

  python tools/bridge.py [--config tools/bridge.json] [--verbose]

Страница шлёт события HTTP POST на http://localhost:7777/ev (JSON, без CORS-преамбулы), мост
по конфигу превращает их в OSC-пакеты (UDP) и/или MIDI-сообщения. Только стандартная
библиотека: OSC кодируется руками, MIDI — winmm через ctypes.

Конфиг (tools/bridge.json):
  targets   — куда слать OSC: имя → {host, port}
  midi_out  — имя MIDI-выхода (или null); Resolume/MA видят его как контроллер
  map       — событие → список действий. Действие: {"to": "resolume", "addr": "/…", "args": [...]}
              или {"midi": [status, data1, data2]}. В addr/args работают подстановки
              {n}, {name}, {state}, {q}, {choice}, {idx}, {v} … — все поля события;
              {v127} — число 0..1 переведённое в 0..127. Пустой список = событие не слать.
События от страницы: pad (n 1..16, name), play, cue, start, back, state (state: select|play),
select (idx, col, name — маркер встал на трек), track (idx, col, name, genre — трек запущен),
scratch (on true/false — коснулись/отпустили диск), mix (v 0..1).
"""
import argparse, ctypes, json, socket, struct, sys, threading, time
from ctypes import wintypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


# ── OSC ──
def osc(addr, args):
    def pad(b): return b + b'\0' * (4 - len(b) % 4)
    tags, data = ',', b''
    for a in args:
        if isinstance(a, bool): tags += 'T' if a else 'F'
        elif isinstance(a, int): tags += 'i'; data += struct.pack('>i', a)
        elif isinstance(a, float): tags += 'f'; data += struct.pack('>f', a)
        else: tags += 's'; data += pad(str(a).encode())
    return pad(addr.encode()) + pad(tags.encode()) + data


# ── MIDI out (winmm) ──
class MidiOut:
    def __init__(self, name):
        self.h = None
        if not name or sys.platform != 'win32': return
        w = ctypes.WinDLL('winmm')

        class CAPS(ctypes.Structure):
            _fields_ = [('wMid', wintypes.WORD), ('wPid', wintypes.WORD), ('v', wintypes.UINT), ('szPname', wintypes.WCHAR * 32),
                        ('wTechnology', wintypes.WORD), ('wVoices', wintypes.WORD), ('wNotes', wintypes.WORD), ('wChannelMask', wintypes.WORD), ('dwSupport', wintypes.DWORD)]
        for i in range(w.midiOutGetNumDevs()):
            c = CAPS(); w.midiOutGetDevCapsW(i, ctypes.byref(c), ctypes.sizeof(c))
            if c.szPname == name:
                h = wintypes.HANDLE()
                if w.midiOutOpen(ctypes.byref(h), i, None, None, 0) == 0: self.h, self.w = h, w; print(f'MIDI-выход: {name}')
                return
        print(f'MIDI-выход «{name}» не найден — MIDI не шлём')

    def send(self, st, d1, d2):
        if self.h: self.w.midiOutShortMsg(self.h, (st & 0xFF) | ((d1 & 0x7F) << 8) | ((d2 & 0x7F) << 16))


def fmt(x, ev):
    if isinstance(x, str):
        try: return x.format(**ev)
        except (KeyError, IndexError): return x
    return x


class Bridge:
    def __init__(self, cfg, verbose):
        self.cfg, self.verbose = cfg, verbose
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.midi = MidiOut(cfg.get('midi_out'))
        self.targets = cfg.get('targets', {})

    def handle(self, ev):
        name = ev.get('ev'); acts = self.cfg.get('map', {}).get(name)
        if 'v' in ev and isinstance(ev['v'], (int, float)): ev['v127'] = int(round(max(0, min(1, ev['v'])) * 127))
        if acts is None:
            if self.verbose: print('  нет правила:', ev); return
        for a in acts:
            if 'midi' in a:
                st, d1, d2 = [int(fmt(x, ev)) if isinstance(x, str) else x for x in a['midi']]
                self.midi.send(st, d1, d2); if_off = a.get('off_ms')
                if if_off: threading.Timer(if_off / 1000, self.midi.send, (st & 0xEF if (st & 0xF0) == 0x90 else st, d1, 0)).start()
                if self.verbose: print(f'  midi {st:02X} {d1:02X} {d2:02X}')
            else:
                t = self.targets.get(a['to'])
                if not t: continue
                addr = fmt(a['addr'], ev); args = [fmt(x, ev) for x in a.get('args', [])]
                def num(x):
                    if not isinstance(x, str): return x
                    try: return int(x) if x.lstrip('-').isdigit() else float(x)
                    except ValueError: return x
                args = [num(x) for x in args]
                self.sock.sendto(osc(addr, args), (t['host'], int(t['port'])))
                if self.verbose: print(f'  {a["to"]} {addr} {args}')


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--config', default=str(ROOT / 'tools' / 'bridge.json')); ap.add_argument('--verbose', '-v', action='store_true')
    a = ap.parse_args(); cfg = json.loads(Path(a.config).read_text(encoding='utf-8')); br = Bridge(cfg, a.verbose)

    class H(BaseHTTPRequestHandler):
        def log_message(self, *x): pass
        def _ok(self):
            self.send_response(204); self.send_header('Access-Control-Allow-Origin', '*'); self.end_headers()
        def do_OPTIONS(self): self._ok()
        def _json(self, obj, code=200):
            body = json.dumps(obj, ensure_ascii=False).encode()
            self.send_response(code); self.send_header('Content-Type', 'application/json'); self.send_header('Access-Control-Allow-Origin', '*'); self.end_headers(); self.wfile.write(body)
        def do_GET(self):
            if self.path.startswith('/config'): return self._json(br.cfg)                 # страница настроек читает карту
            self._json({'ok': True, 'targets': br.targets, 'midi': bool(br.midi.h)})
        def do_POST(self):
            n = int(self.headers.get('Content-Length', 0)); raw = self.rfile.read(n)
            if self.path.startswith('/config'):                                             # страница настроек сохраняет карту
                try: new = json.loads(raw.decode('utf-8'))
                except ValueError as e: return self._json({'ok': False, 'error': str(e)}, 400)
                if not isinstance(new.get('map'), dict) or not isinstance(new.get('targets'), dict): return self._json({'ok': False, 'error': 'нужны map и targets'}, 400)
                Path(a.config).write_text(json.dumps(new, ensure_ascii=False, indent=2), encoding='utf-8')
                br.cfg = new; br.targets = new.get('targets', {})
                if new.get('midi_out') != cfg.get('midi_out'): br.midi = MidiOut(new.get('midi_out'))
                cfg.clear(); cfg.update(new); print('карта сохранена'); return self._json({'ok': True})
            self._ok()
            try: ev = json.loads(raw or b'{}')
            except ValueError: return
            if a.verbose: print(time.strftime('%H:%M:%S'), ev)
            try: br.handle(ev)
            except Exception as e: print('ошибка правила:', e, ev)

    port = int(cfg.get('http_port', 7777))
    print(f'мост DJ Wheel: http://localhost:{port}/ev → ' + ', '.join(f'{k} {v["host"]}:{v["port"]}' for k, v in br.targets.items()))
    ThreadingHTTPServer(('127.0.0.1', port), H).serve_forever()


if __name__ == '__main__':
    main()
