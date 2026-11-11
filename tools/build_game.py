"""
Збирає ігрові файли українського перекладу Starfield у D:\\Starfield\\dist\\Data:
  Strings/Starfield_uk.STRINGS|DLSTRINGS|ILSTRINGS  - з XLIFF (людський переклад) + результати бота
  Strings/<DLC>_uk.*                                - з моду 0.87 (перекодовано в UTF-8)
  Interface/translate_uk.txt                        - з interface XLIFF
  Interface/fonts_uk.*, fontconfig_uk.txt           - шрифти з кирилицею з моду 0.87
  ..\\Female\\Strings/Starfield_uk.ILSTRINGS|DLSTRINGS  - жіноча версія (результати gender_bot.py)

Пріоритет для кожного рядка: людський переклад -> бот -> стара машинна чернетка (0.87) -> англійська.
  python build_game.py [--no-draft]   (--no-draft: замість чернетки 0.87 лишати англійську)
"""
import argparse, glob, json, os, re, shutil, struct, sys
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from translate_bot import ROOT, WORK, RES, X, CYR, read_bethesda_strings  # noqa: E402
import dlc_bot  # noqa: E402

DIST = os.path.join(ROOT, "dist", "Data")
FEM = os.path.join(ROOT, "dist", "Female", "Strings")
FRES = os.path.join(WORK, "fem_results")
MOD = glob.glob(os.path.join(ROOT, "Starfield_UA_0.87_male-*", "Data"))[0]
KIND = {"STRINGS": ["starfield_en.strings.xliff"],
        "DLSTRINGS": ["starfield_en.dlstrings.xliff"],
        "ILSTRINGS": ["starfield_en_part_1.ilstrings.xliff", "starfield_en_part_2.ilstrings.xliff",
                      "starfield_en_part_3.ilstrings.xliff"]}


def unescape(s):
    return s.replace("\\r", "\r").replace("\\n", "\n")


def write_strings(path, table, dl):
    blob, directory = bytearray(), bytearray()
    for sid in sorted(table):
        enc = table[sid].encode("utf-8")
        directory += struct.pack("<II", sid, len(blob))
        blob += (struct.pack("<I", len(enc) + 1) if dl else b"") + enc + b"\0"
    with open(path, "wb") as f:
        f.write(struct.pack("<II", len(table), len(blob)) + directory + blob)


def bot_results():
    res = {}
    for p in glob.glob(os.path.join(RES, "*.json")):
        r = json.load(open(p, encoding="utf-8"))
        res.update({(os.path.basename(r["file"]), k): v for k, v in r["good"].items()})
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-draft", action="store_true")
    a = ap.parse_args()
    for old in glob.glob(os.path.join(DIST, "**", "*"), recursive=True) + glob.glob(os.path.join(FEM, "*")):
        if os.path.isfile(old):
            os.remove(old)
    sdir, idir = os.path.join(DIST, "Strings"), os.path.join(DIST, "Interface")
    os.makedirs(sdir, exist_ok=True), os.makedirs(idir, exist_ok=True)
    bot = bot_results()
    fem = {}     # gender_bot: {ім'я файлу lower: {id: текст}}
    for p in glob.glob(os.path.join(FRES, "*.json")):
        r = json.load(open(p, encoding="utf-8"))
        fn = r.get("file", "Starfield_uk." + r["ext"]).lower()
        fem.setdefault(fn, {}).update({int(k, 16): v for k, v in r["good"].items()})
    dlc = dlc_bot.results()
    fixes = {}   # fix_junk.py: "m|f:EXT:ID" -> виправлений текст
    fp = os.path.join(WORK, "fix_results.json")
    if os.path.exists(fp):
        for key, v in json.load(open(fp, encoding="utf-8")).items():
            ver, e, i = key.split(":")
            fixes.setdefault((ver, e), {})[int(i, 16)] = v
    xdir = os.path.join(WORK, "xliff", "strings")

    for ext, files in KIND.items():
        dl = ext != "STRINGS"
        draft = read_bethesda_strings(os.path.join(MOD, "strings", f"Starfield_uk.{ext}"), dl)
        table, stat = {}, {"human": 0, "bot": 0, "draft": 0, "english": 0}
        for fn in files:
            for u in ET.parse(os.path.join(xdir, fn)).iter(X + "trans-unit"):
                sid = int(u.get("id"), 16)
                src = "".join(u.find(X + "source").itertext())
                g = u.find(X + "target")
                tgt = "".join(g.itertext()) if g is not None else ""
                st = g.get("state") if g is not None else None
                if tgt.strip() and (st != "needs-translation" or CYR.search(tgt)):
                    table[sid], k = tgt, "human"
                elif (fn, u.get("id")) in bot:
                    table[sid], k = bot[(fn, u.get("id"))], "bot"
                elif not a.no_draft and CYR.search(draft.get(sid, "")):
                    table[sid], k = draft[sid], "draft"
                else:
                    table[sid], k = src, "english"
                table[sid] = unescape(table[sid]) if k != "draft" else table[sid]
                stat[k] += 1
        extra = {sid: s for sid, s in draft.items() if sid not in table}   # ID, яких немає в XLIFF
        table.update(extra)
        # нові рядки з оновлень гри (немає в XLIFF) і залишки англійською -> dlc_bot, інакше англійський оригінал
        gen = os.path.join(dlc_bot.GEN, f"starfield_en.{ext.lower()}")
        new = 0
        if os.path.exists(gen):
            dres = dlc.get(("starfield", ext), {})
            for sid, s in read_bethesda_strings(gen, dl).items():
                if sid in dres and not CYR.search(table.get(sid, "")):
                    table[sid] = dres[sid]; new += 1
                elif sid not in table:
                    table[sid] = s
        stat["dlc_bot"] = new
        fem_ext = {k: v for k, v in fem.get(f"starfield_uk.{ext}".lower(), {}).items() if k in table}
        ft = {**table, **fem_ext}
        table.update(fixes.get(("m", ext), {}))
        write_strings(os.path.join(sdir, f"Starfield_uk.{ext}"), table, dl)
        print(f"Starfield_uk.{ext}: {len(table)} strings {stat} +{len(extra)} only-in-0.87")
        if fem_ext:
            os.makedirs(FEM, exist_ok=True)
            ft.update(fixes.get(("f", ext), {}))
            write_strings(os.path.join(FEM, f"Starfield_uk.{ext}"), ft, dl)
            print(f"  female: {len(fem_ext)} lines changed")

    # DLC / інші плагіни: англійський оригінал гри <- чернетка 0.87 <- dlc_bot
    done = set()
    for plug, ext, gp in dlc_bot.game_files():
        if plug.lower() == "starfield":
            continue
        dl = ext != "STRINGS"
        t = read_bethesda_strings(gp, dl)
        dq = dlc_bot.find_ci(os.path.join(MOD, "strings"), f"{plug}_uk.{ext}")
        if dq:
            t.update({k: v for k, v in read_bethesda_strings(dq, dl).items() if k in t and CYR.search(v)})
        res = dlc.get((plug.lower(), ext), {})
        t.update({k: v for k, v in res.items() if k in t})
        write_strings(os.path.join(sdir, f"{plug}_uk.{ext.lower()}"), t, dl)
        fr = {k: v for k, v in fem.get(f"{plug}_uk.{ext}".lower(), {}).items() if k in t}
        if fr:
            os.makedirs(FEM, exist_ok=True)
            write_strings(os.path.join(FEM, f"{plug}_uk.{ext.lower()}"), {**t, **fr}, dl)
            print(f"  female: {len(fr)} lines changed")
        done.add(f"{plug}_uk.{ext}".lower())
        print(f"{plug}_uk.{ext.lower()}: {len(t)} strings, bot {len(res)}")
    for p in glob.glob(os.path.join(MOD, "strings", "*")):   # плагіни, яких немає в архівах гри - як у 0.87
        name = os.path.basename(p)
        if name.lower().startswith("starfield_uk.") or name.lower() in done:
            continue
        ext = name.rsplit(".", 1)[1].upper()
        write_strings(os.path.join(sdir, name), read_bethesda_strings(p, ext != "STRINGS"), ext != "STRINGS")

    # інтерфейс
    lines = []
    for u in ET.parse(os.path.join(WORK, "xliff", "interface", "translate_en.xliff")).iter(X + "trans-unit"):
        g = u.find(X + "target")
        tgt = "".join(g.itertext()) if g is not None else ""
        lines.append(u.get("id") + "\t" + (tgt or "".join(u.find(X + "source").itertext())))
    with open(os.path.join(idir, "translate_uk.txt"), "w", encoding="utf-16", newline="\r\n") as f:
        f.write("\n".join(lines) + "\n")
    for fn in ("fonts_uk.gfx", "fonts_uk.swf"):
        shutil.copy(os.path.join(MOD, "interface", fn), idir)
    fc = open(os.path.join(MOD, "interface", "fontconfig_uk.txt"), "rb").read().decode("utf-8")
    fc = fc.replace("Яя\"", "ЯяҐґ\"")   # дозволити Ґґ в іменах і книгах
    open(os.path.join(idir, "fontconfig_uk.txt"), "wb").write(fc.encode("utf-8"))
    print("interface:", len(lines), "keys ->", DIST)


if __name__ == "__main__":
    main()
