"""
Виправлення сміття в готовому тексті: латинські літери всередині українських слів, змішані римські цифри,
обрізки англійських слів ("оберabove", "naябедничати").
  python fix_junk.py find    - знайти, виправити гомогліфи локально, решту -> Claude; результат work/fix_results.json
  python fix_junk.py show
build_game.py застосовує work/fix_results.json поверх усього (і в чоловічій, і в жіночій версії).
"""
import argparse, glob, json, os, re, sys
import xml.etree.ElementTree as ET

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import translate_bot as tb  # noqa: E402
from translate_bot import ROOT, WORK, X, CYR, TAG, log, read_bethesda_strings  # noqa: E402

OUT = os.path.join(WORK, "fix_results.json")
FSYS = os.path.join(WORK, "fix_system.txt")
DIST = os.path.join(ROOT, "dist")
EXTS = ["STRINGS", "DLSTRINGS", "ILSTRINGS"]
MIX = re.compile(r"(?=\w*[a-zA-Z])(?=\w*[а-яА-ЯіїєґІЇЄҐ])\w+")
SKIP = re.compile(r"<[^<>]*>|\[[^\]]*\]|\{[^}]*\}")
LAT2CYR = str.maketrans("aceiopxyACEHIKMOPTXB", "асеіорхуАСЕНІКМОРТХВ")
ROMAN = re.compile(r"^[IVXІХ]+$")
CYR2LAT_ROMAN = str.maketrans("ІХ", "IX")

SYSTEM = """You fix corrupted fragments in an existing Ukrainian translation of Starfield (sci-fi RPG).
Some words contain stray Latin letters or leftover English pieces (e.g. "оберabove" -> "обереш", "naябедничати" -> "наябедничати",
"abordували" -> "взяли на абордаж", "perdona" -> keep only if the English source also has it as a foreign word).
Fix ONLY those corrupted words, using the English source "en" for meaning. Do not rephrase or restyle anything else.
Keep proper names/brands/codes that are Latin in the source. Keep markup (<...>, [...], {...}, %d, line breaks) exactly.
If the line is intentionally garbled (glitched data in the source too) or nothing is wrong, do not return it.
Return only the items you changed."""


def homoglyph_fix(s):
    def fix(m):
        w = m.group(0)
        if ROMAN.match(w):
            return w.translate(CYR2LAT_ROMAN)
        cyr = len(re.findall("[а-яА-ЯіїєґІЇЄҐ]", w))
        if cyr >= len(w) / 2 and re.fullmatch(r"[\wа-яА-ЯіїєґІЇЄҐ]+", w):
            t = w.translate(LAT2CYR)
            if not re.search("[a-zA-Z]", t):
                return t
        return w
    out, last = [], 0
    for m in SKIP.finditer(s):          # не чіпаємо розмітку
        out.append(MIX.sub(fix, s[last:m.start()])); out.append(m.group(0)); last = m.end()
    out.append(MIX.sub(fix, s[last:]))
    return "".join(out)


def is_junk(s, src):
    body = SKIP.sub(" ", s)
    lat = [w for w in re.findall(r"(?<![\w-])[a-z]{3,}(?![\w-])", body) if w not in src.lower()]
    return bool(MIX.search(body)) or bool(lat)


def find(a):
    en = {}
    for f in glob.glob(os.path.join(WORK, "xliff", "strings", "*.xliff")):
        for u in ET.parse(f).iter(X + "trans-unit"):
            en[int(u.get("id"), 16)] = "".join(u.find(X + "source").itertext())
    res, todo = {}, []
    for ver, base in (("m", os.path.join(DIST, "Data", "Strings")), ("f", os.path.join(DIST, "Female", "Strings"))):
        for ext in EXTS:
            p = os.path.join(base, f"Starfield_uk.{ext}")
            if not os.path.exists(p):
                continue
            for k, s in read_bethesda_strings(p, ext != "STRINGS").items():
                if not CYR.search(s) or not is_junk(s, en.get(k, "")):
                    continue
                key = f"{ver}:{ext}:{k:08X}"
                t = homoglyph_fix(s)
                if t != s:
                    res[key] = t
                if is_junk(t, en.get(k, "")):
                    todo.append({"id": key, "en": en.get(k, ""), "uk": t})
    log(f"homoglyph fixes: {len(res)}, to Claude: {len(todo)}")
    open(FSYS, "w", encoding="utf-8").write(SYSTEM)
    for i in range(0, len(todo), 30):
        part = todo[i:i + 30]
        prompt = "Fix the items. Input JSON:\n" + json.dumps({"items": part}, ensure_ascii=False)
        got = tb.call_claude({"id": f"fix{i // 30:03d}"}, part, a, prompt=prompt, system=FSYS)
        orig = {x["id"]: x["uk"] for x in part}
        n = 0
        for g in got:
            o = orig.get(g.get("id"))
            if o and g["uk"] != o and CYR.search(g["uk"]) and sorted(TAG.findall(o)) == sorted(TAG.findall(g["uk"])) \
                    and o.count("\n") == g["uk"].count("\n") and 0.7 <= len(g["uk"]) / len(o) <= 1.4:
                res[g["id"]] = g["uk"]; n += 1
        log(f"[fix{i // 30:03d}] fixed {n}/{len(part)}")
    json.dump(res, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    log(f"total fixes: {len(res)} -> {OUT}")


def show(a):
    res = json.load(open(OUT, encoding="utf-8"))
    base = {v: os.path.join(DIST, d, "Strings") for v, d in (("m", "Data"), ("f", "Female"))}
    cache = {}
    for n, (key, new) in enumerate(res.items()):
        if n >= a.n:
            break
        v, ext, k = key.split(":")
        if (v, ext) not in cache:
            cache[(v, ext)] = read_bethesda_strings(os.path.join(base[v], f"Starfield_uk.{ext}"), ext != "STRINGS")
        print(f"{key}\n  - {cache[(v, ext)][int(k, 16)][:150]}\n  + {new[:150]}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["find", "show"])
    ap.add_argument("--model", default="sonnet")
    ap.add_argument("--effort", default="low")
    ap.add_argument("--n", type=int, default=60)
    a = ap.parse_args()
    {"find": find, "show": show}[a.cmd](a)


if __name__ == "__main__":
    main()
