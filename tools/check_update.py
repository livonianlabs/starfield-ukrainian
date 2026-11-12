"""
Перевірка після оновлення гри або нового DLC: чи все з поточної гри є в нашій збірці (dist/Data).
  python check_update.py           # звіт; код виходу 1, якщо є що перекладати
  python check_update.py --mark    # запам'ятати поточну версію гри як перекладену (після випуску)
Порівнює:
  - buildid гри зі Steam (appmanifest) з останнім позначеним;
  - рядки (*.strings/dlstrings/ilstrings) з англійських архівів гри з нашими *_uk.*;
  - ключі інтерфейсу translate_en.txt з нашим translate_uk.txt.
Що робити, якщо є нове: dlc_bot.py extract/prepare/run (рядки), iface_bot.py prepare/run (інтерфейс),
потім build_release.py.
"""
import json, os, re, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ba2  # noqa: E402
from translate_bot import WORK, ROOT, read_bethesda_strings  # noqa: E402
import iface_bot  # noqa: E402

STEAM = r"D:\Steam\steamapps"
GAME = os.path.join(STEAM, "common", "Starfield", "Data")
DIST = os.path.join(ROOT, "dist", "Data")
STATE = os.path.join(WORK, "last_build.json")
SKIP = re.compile(r"Textures|Voices|Meshes|Shaders|Terrain|Anim|Particles|Planet|Lod|Materials|Face", re.I)


def buildid():
    p = os.path.join(STEAM, "appmanifest_1716740.acf")
    m = re.search(r'"buildid"\s+"(\d+)"', open(p, encoding="utf-8").read()) if os.path.exists(p) else None
    return m.group(1) if m else "?"


def game_strings(tmp):
    """{(plugin, EXT): path} англійських файлів рядків з архівів гри."""
    out = {}
    for p in os.listdir(GAME):
        if not p.lower().endswith(".ba2") or SKIP.search(p):
            continue
        for name, off, packed, size in ba2.entries(os.path.join(GAME, p)):
            n = name.lower()
            if n.startswith("strings/") and "_en." in n:
                dst = os.path.join(tmp, os.path.basename(n))
                open(dst, "wb").write(ba2.read(os.path.join(GAME, p), off, packed, size))
                plug, ext = os.path.basename(n).rsplit("_en.", 1)
                out[(plug, ext.upper())] = dst
    return out


def main():
    bid = buildid()
    last = json.load(open(STATE)) if os.path.exists(STATE) else {}
    if "--mark" in sys.argv:
        json.dump({"buildid": bid}, open(STATE, "w"))
        print("позначено buildid", bid)
        return 0
    print(f"гра buildid {bid}; останній перекладений {last.get('buildid', 'не позначено')}")
    ours = {}
    for f in os.listdir(os.path.join(DIST, "Strings")):
        plug, ext = f.rsplit("_uk.", 1) if "_uk." in f.lower() else (None, None)
        if plug:
            ours[(plug.lower(), ext.upper())] = os.path.join(DIST, "Strings", f)
    todo = 0
    with tempfile.TemporaryDirectory() as tmp:
        for (plug, ext), p in sorted(game_strings(tmp).items()):
            dl = ext != "STRINGS"
            en = {k: v for k, v in read_bethesda_strings(p, dl).items() if v.strip()}
            uk = read_bethesda_strings(ours[(plug, ext)], dl) if (plug, ext) in ours else {}
            miss = [k for k in en if k not in uk]
            if miss:
                todo += len(miss)
                print(f"  {plug}.{ext.lower()}: {len(miss)} нових рядків" + ("" if uk else " (файлу перекладу немає)"))
    # інтерфейс
    with tempfile.TemporaryDirectory() as tmp:
        arc = os.path.join(GAME, "Starfield - Interface.ba2")
        for name, off, packed, size in ba2.entries(arc):
            if name.lower() == "interface/translate_en.txt":
                p = os.path.join(tmp, "translate_en.txt")
                open(p, "wb").write(ba2.read(arc, off, packed, size))
                en = iface_bot.read_txt(p)
        uk = iface_bot.read_txt(os.path.join(DIST, "Interface", "translate_uk.txt"))
        miss = [k for k in en if k not in uk]
        if miss:
            todo += len(miss)
            print(f"  інтерфейс: {len(miss)} нових ключів, напр. {', '.join(miss[:5])}")
    if todo:
        print(f"ПОТРІБНЕ ОНОВЛЕННЯ ПЕРЕКЛАДУ: {todo} рядків/ключів")
        return 1
    print("усе з поточної гри перекладено" + (" (гра оновилась, але нових рядків немає)" if last.get("buildid") not in (None, bid) else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
