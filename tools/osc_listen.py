"""Слушает OSC на UDP-портах и печатает пакеты — вместо Resolume/MA для проверки моста.
  python tools/osc_listen.py 7000 8000 [--secs 20]"""
import argparse, select, socket, struct, time


def parse(b):
    def s(i):
        j = b.index(b'\0', i); return b[i:j].decode(errors='replace'), (j + 4) & ~3
    addr, i = s(0); tags, i = s(i); out = []
    for t in tags[1:]:
        if t == 'i': out.append(struct.unpack('>i', b[i:i + 4])[0]); i += 4
        elif t == 'f': out.append(round(struct.unpack('>f', b[i:i + 4])[0], 4)); i += 4
        elif t == 's': v, i = s(i); out.append(v)
        elif t in 'TF': out.append(t == 'T')
    return addr, out


ap = argparse.ArgumentParser(); ap.add_argument('ports', nargs='+', type=int); ap.add_argument('--secs', type=float, default=20); a = ap.parse_args()
socks = []
for p in a.ports:
    sk = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); sk.bind(('127.0.0.1', p)); socks.append(sk)
print('слушаю OSC на', a.ports, f'{a.secs:.0f} с'); t0 = time.time()
while time.time() - t0 < a.secs:
    r, _, _ = select.select(socks, [], [], 0.5)
    for sk in r:
        data, _ = sk.recvfrom(4096); addr, args = parse(data)
        print(f'{time.time() - t0:6.2f}  :{sk.getsockname()[1]}  {addr} {args}', flush=True)
