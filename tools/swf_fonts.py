"""Список шрифтів у SWF/GFX (Scaleform): назва, копірайт, кількість гліфів, покриття кирилиці."""
import sys, zlib, struct
def load(p):
    b = open(p, 'rb').read()
    sig = b[:3]
    if sig in (b'CWS', b'CFX'):
        b = b[:8] + zlib.decompress(b[8:])
    elif sig == b'ZWS':
        import lzma
        raise SystemExit('LZMA swf not supported')
    return b
def tags(b):
    nbits = b[8] >> 3
    pos = 8 + (5 + 4 * nbits + 7) // 8 + 4
    while pos < len(b):
        h, = struct.unpack_from('<H', b, pos); pos += 2
        code, ln = h >> 6, h & 0x3f
        if ln == 0x3f:
            ln, = struct.unpack_from('<I', b, pos); pos += 4
        yield code, b[pos:pos + ln]
        pos += ln
        if code == 0: break
def cstr(d, i):
    e = d.index(b'\0', i); return d[i:e].decode('utf-8', 'replace'), e + 1
for p in sys.argv[1:]:
    b = load(p); print('==', p, b[:3])
    names = {}
    for code, d in tags(b):
        if code == 88:  # DefineFontName
            fid, = struct.unpack_from('<H', d, 0); n, i = cstr(d, 2); c, _ = cstr(d, i)
            names[fid] = (n, c)
        if code in (48, 75):  # DefineFont2/3
            fid, flags = struct.unpack_from('<HB', d, 0)
            nl = d[4]; name = d[5:5 + nl].decode('utf-8', 'replace').rstrip('\0'); i = 5 + nl
            ng, = struct.unpack_from('<H', d, i); i += 2
            wide_off, wide_codes = flags & 0x08, flags & 0x04
            ot = i
            if ng:
                ctoff = struct.unpack_from('<I' if wide_off else '<H', d, ot + ng * (4 if wide_off else 2))[0]
                codes = [struct.unpack_from('<H' if wide_codes else '<B', d, ot + ctoff + k * (2 if wide_codes else 1))[0] for k in range(ng)]
            else:
                codes = []
            cyr = [c for c in codes if 0x400 <= c <= 0x4FF]
            uk = set('АБВГҐДЕЄЖЗИІЇЙКЛМНОПРСТУФХЦЧШЩЬЮЯабвгґдеєжзиіїйклмнопрстуфхцчшщьюя’')
            missing = ''.join(sorted(ch for ch in uk if ord(ch) not in codes))
            print(f'font id={fid} "{name}" glyphs={ng} cyrillic={len(cyr)} missing_uk="{missing}"')
    for fid, (n, c) in names.items():
        print(f'  name id={fid}: "{n}" copyright: "{c}"')
