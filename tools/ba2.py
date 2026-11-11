"""
Мінімальний читач Bethesda BA2 (BTDX, GNRL) для Starfield: список файлів і розпакування.
  python ba2.py list  <archive.ba2> [фільтр]
  python ba2.py extract <archive.ba2> <папка> [фільтр]
"""
import os, struct, sys, zlib


def entries(path):
    f = open(path, "rb")
    magic, ver, typ, n, names_off = struct.unpack("<4sI4sIQ", f.read(24))
    assert magic == b"BTDX" and typ == b"GNRL", (magic, typ)
    if ver >= 2:
        f.read(8)
    if ver == 3:
        f.read(4)   # метод стиснення (0 = zlib, 3 = lz4)
    recs = [struct.unpack("<IIIIQIII", f.read(36)) for _ in range(n)]
    f.seek(names_off)
    names = []
    for _ in range(n):
        L = struct.unpack("<H", f.read(2))[0]
        names.append(f.read(L).decode("utf-8", "replace"))
    for name, r in zip(names, recs):
        yield name, r[4], r[5], r[6]   # offset, packed, unpacked


def read(path, off, packed, size):
    with open(path, "rb") as f:
        f.seek(off)
        data = f.read(packed or size)
    return zlib.decompress(data) if packed else data


if __name__ == "__main__":
    cmd, arc = sys.argv[1], sys.argv[2]
    flt = (sys.argv[4] if cmd == "extract" and len(sys.argv) > 4 else sys.argv[3] if cmd == "list" and len(sys.argv) > 3 else "").lower()
    for name, off, packed, size in entries(arc):
        if flt not in name.lower():
            continue
        if cmd == "list":
            print(name, size)
        else:
            out = os.path.join(sys.argv[3], name.replace("\\", os.sep))
            os.makedirs(os.path.dirname(out), exist_ok=True)
            open(out, "wb").write(read(arc, off, packed, size))
