"""
Класифікує рядки діалогів Starfield.esm за мовцем (для жіночої версії):
  player     - репліки гравця (теми ESCE у діях сцени "вибір гравця", ANAM=3)
  to_player  - NPC у розмові з гравцем (відповіді ESCS, сцени з вибором гравця, HELO/GBYE/CUST...)
  ambient    - NPC між собою (сцени без вибору гравця)
  journal    - записи журналу завдань (QUST CNAM, від першої особи гравця)
Результат: work/speakers.json (Starfield.esm) або work/speakers_<plugin>.json (DLC)
  {"<hex id>": "player"|"to_player"|"ambient"|"journal"}
  python esm_speakers.py [шлях до .esm]
"""
import json, os, struct, sys, zlib, collections
BOT = os.path.dirname(os.path.abspath(__file__))
F = sys.argv[1] if len(sys.argv) > 1 else r"D:\Steam\SteamApps\common\Starfield\Data\Starfield.esm"
b = open(F, "rb").read()


def subs(data):
    i, big = 0, None
    while i + 6 <= len(data):
        t = data[i:i + 4]; n = struct.unpack_from("<H", data, i + 4)[0]; i += 6
        if t == b"XXXX":
            big = struct.unpack_from("<I", data, i)[0]; i += n; continue
        if big is not None:
            n, big = big, None
        yield t.decode("latin1"), data[i:i + n]; i += n


u32 = lambda v: struct.unpack("<I", v[:4])[0]
info_texts = collections.defaultdict(list)   # dial -> [string ids]
dial_type = {}
player, responses, scene_npc, ambient_npc, journal = set(), set(), set(), set(), set()


def walk(off, end, dial):
    while off < end:
        if b[off:off + 4] == b"GRUP":
            size, label, gtype = struct.unpack_from("<IIi", b, off + 4)
            walk(off + 24, off + size, label if gtype == 7 else dial)
            off += size; continue
        rt = b[off:off + 4]; ds, fl, fid = struct.unpack_from("<III", b, off + 4)
        if rt in (b"INFO", b"SCEN", b"DIAL", b"QUST"):
            data = b[off + 24:off + 24 + ds]
            if fl & 0x40000:
                data = zlib.decompress(data[4:])
            sb = list(subs(data))
            if rt == b"DIAL":
                dial_type[fid] = next((v[:4].decode("latin1") for s, v in sb if s == "SNAM"), "")
            elif rt == b"QUST":
                journal.update(u32(v) for s, v in sb if s == "CNAM" and len(v) == 4)
            elif rt == b"INFO":
                info_texts[dial] += [u32(v) for s, v in sb if s in ("NAM1", "RNAM") and len(v) == 4]
            else:
                has_choice = any(s == "ANAM" and v[:2] == b"\x03\x00" for s, v in sb)
                for s, v in sb:
                    if s == "ESCE" and len(v) == 4: player.add(u32(v))
                    elif s == "ESCS" and len(v) == 4: responses.add(u32(v))
                    elif s == "DATA" and len(v) == 4:
                        (scene_npc if has_choice else ambient_npc).add(u32(v))
        off += 24 + ds


walk(0, len(b), None)
out = {}
for dial, ids in info_texts.items():
    if dial in player: k = "player"
    elif dial in responses or dial in scene_npc: k = "to_player"
    elif dial in ambient_npc: k = "ambient"
    elif dial_type.get(dial) == "SCEN": k = "ambient"
    else: k = "to_player"          # привітання, бої, торгівля тощо - зазвичай до гравця
    for i in ids:
        out[f"{i:08X}"] = k
for i in journal:
    out.setdefault(f"{i:08X}", "journal")
plug = os.path.splitext(os.path.basename(F))[0].lower()
name = "speakers.json" if plug == "starfield" else f"speakers_{plug}.json"
json.dump(out, open(os.path.join(BOT, "work", name), "w"), indent=0)
print(collections.Counter(out.values()))
