"""Слушает все MIDI-входы N секунд и печатает, что пришло (winmm через ctypes, без библиотек).

  python tools/midi_listen.py [секунд=15]
Вывод: сводка по каждому сообщению «порт · статус data1» — сколько раз и какие значения.
"""
import ctypes, sys, time
from ctypes import wintypes
from collections import OrderedDict

secs = float(sys.argv[1]) if len(sys.argv) > 1 else 15
winmm = ctypes.WinDLL('winmm')


class MIDIINCAPS(ctypes.Structure):
    _fields_ = [('wMid', wintypes.WORD), ('wPid', wintypes.WORD), ('vDriverVersion', wintypes.UINT),
                ('szPname', wintypes.WCHAR * 32), ('dwSupport', wintypes.DWORD)]


names = []
for i in range(winmm.midiInGetNumDevs()):
    c = MIDIINCAPS(); winmm.midiInGetDevCapsW(i, ctypes.byref(c), ctypes.sizeof(c)); names.append(c.szPname)
print('входы:', names or 'нет')

seen = OrderedDict(); total = [0]; order = []
CB = ctypes.WINFUNCTYPE(None, wintypes.HANDLE, wintypes.UINT, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)


def on_msg(h, msg, inst, p1, p2):
    if msg != 0x3C3: return                      # MIM_DATA
    v = p1 or 0; st, d1, d2 = v & 0xFF, (v >> 8) & 0xFF, (v >> 16) & 0xFF
    if st >= 0xF8: return                        # тактовые и active sensing не интересны
    key = (inst or 0, st, d1); total[0] += 1
    e = seen.setdefault(key, {'n': 0, 'vals': []}); e['n'] += 1
    if len(e['vals']) < 12: e['vals'].append(d2)
    if len(order) < 400: order.append((round(time.time() - t0, 2), inst or 0, st, d1, d2))


cb = CB(on_msg); handles = []
for i in range(len(names)):
    h = wintypes.HANDLE()
    r = winmm.midiInOpen(ctypes.byref(h), i, cb, i, 0x30000)
    if r: print(f'  не открылся «{names[i]}» (код {r})'); continue
    winmm.midiInStart(h); handles.append(h)
t0 = time.time()
print(f'слушаю {secs:.0f} с…'); sys.stdout.flush()
time.sleep(secs)
for h in handles: winmm.midiInStop(h); winmm.midiInClose(h)

print(f'всего сообщений: {total[0]}')
for (port, st, d1), e in seen.items():
    kind = {0x80: 'NoteOff', 0x90: 'Note', 0xB0: 'CC', 0xE0: 'Pitch'}.get(st & 0xF0, hex(st & 0xF0))
    print(f'  {names[port]:<12} {st:02X} {d1:02X}  {kind:<7} канал {(st & 0x0F) + 1:<2} ×{e["n"]:<5} значения: {" ".join(f"{v:02X}" for v in e["vals"])}')
if '--order' in sys.argv:
    for t, port, st, d1, d2 in order: print(f'  {t:6.2f}  {names[port]}  {st:02X} {d1:02X} {d2:02X}')
