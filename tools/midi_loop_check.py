"""Проверка MIDI-петли без сторонних библиотек (winmm через ctypes).

Шлёт три сообщения в выход «<имя> A» и ждёт их на входе «<имя> B».
  python tools/midi_loop_check.py ["DJ Wheel"]
"""
import ctypes, sys, time
from ctypes import wintypes

name = sys.argv[1] if len(sys.argv) > 1 else 'DJ Wheel'
winmm = ctypes.WinDLL('winmm')


class MIDIINCAPS(ctypes.Structure):
    _fields_ = [('wMid', wintypes.WORD), ('wPid', wintypes.WORD), ('vDriverVersion', wintypes.UINT),
                ('szPname', wintypes.WCHAR * 32), ('dwSupport', wintypes.DWORD)]


class MIDIOUTCAPS(ctypes.Structure):
    _fields_ = [('wMid', wintypes.WORD), ('wPid', wintypes.WORD), ('vDriverVersion', wintypes.UINT),
                ('szPname', wintypes.WCHAR * 32), ('wTechnology', wintypes.WORD), ('wVoices', wintypes.WORD),
                ('wNotes', wintypes.WORD), ('wChannelMask', wintypes.WORD), ('dwSupport', wintypes.DWORD)]


def ins():
    r = {}
    for i in range(winmm.midiInGetNumDevs()):
        c = MIDIINCAPS(); winmm.midiInGetDevCapsW(i, ctypes.byref(c), ctypes.sizeof(c)); r[c.szPname] = i
    return r


def outs():
    r = {}
    for i in range(winmm.midiOutGetNumDevs()):
        c = MIDIOUTCAPS(); winmm.midiOutGetDevCapsW(i, ctypes.byref(c), ctypes.sizeof(c)); r[c.szPname] = i
    return r


i, o = ins(), outs()
print('входы :', list(i)); print('выходы:', list(o))
src, dst = f'{name} B', f'{name} A'
if src not in i or dst not in o:
    sys.exit(f'нет портов «{dst}» / «{src}» — петля не создана')

got = []
CB = ctypes.WINFUNCTYPE(None, wintypes.HANDLE, wintypes.UINT, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)
MIM_DATA = 0x3C3


def on_msg(h, msg, inst, p1, p2):
    if msg == MIM_DATA:
        v = p1 or 0; got.append((v & 0xFF, (v >> 8) & 0xFF, (v >> 16) & 0xFF))


cb = CB(on_msg)
hin, hout = wintypes.HANDLE(), wintypes.HANDLE()
assert winmm.midiInOpen(ctypes.byref(hin), i[src], cb, None, 0x30000) == 0, 'midiInOpen'     # CALLBACK_FUNCTION
assert winmm.midiOutOpen(ctypes.byref(hout), o[dst], None, None, 0) == 0, 'midiOutOpen'
winmm.midiInStart(hin)
sent = [(0xB0, 0x22, 0x41), (0xB0, 0x22, 0x3F), (0x97, 0x00, 0x7F)]      # джог +1, джог −1, пад 1
for s, d1, d2 in sent:
    winmm.midiOutShortMsg(hout, s | (d1 << 8) | (d2 << 16)); time.sleep(0.05)
time.sleep(0.4)
winmm.midiInStop(hin); winmm.midiInClose(hin); winmm.midiOutClose(hout)
print('послано :', [' '.join(f'{b:02X}' for b in m) for m in sent])
print('получено:', [' '.join(f'{b:02X}' for b in m) for m in got])
print('ПЕТЛЯ РАБОТАЕТ' if got == sent else 'НЕ СОШЛОСЬ')
