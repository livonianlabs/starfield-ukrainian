"""
Інтерфейс (Interface/translate_uk.txt): ключі з поточної гри, яких немає в перекладі спільноти
(додані патчами після 2024) або без перекладу -> Claude.
  python iface_bot.py prepare      # work/game_en/interface/translate_en.txt (ba2.py extract) -> work/iface_chunks.jsonl
  python iface_bot.py run          # -> work/iface_results.json {key: uk}
"""
import argparse, glob, json, os, re, sys, xml.etree.ElementTree as ET
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import translate_bot as tb  # noqa: E402

EN_TXT = os.path.join(tb.WORK, "game_en", "interface", "translate_en.txt")
XLF = os.path.join(tb.WORK, "xliff", "interface", "translate_en.xliff")
CHUNKS = os.path.join(tb.WORK, "iface_chunks.jsonl")
OUT = os.path.join(tb.WORK, "iface_results.json")
SYSTEM = os.path.join(tb.WORK, "iface_system.txt")

SYS_TEXT = tb.SYSTEM + """

This batch is USER INTERFACE text (menus, settings, key bindings, HUD, Creations store). Each item id is the
interface key - use it as a hint for meaning (e.g. *_KBM = keyboard/mouse binding label, *_Desc = tooltip,
Settings_* = options menu). Keep labels short: they must fit narrow menu cells. Follow the capitalisation of
the English (ALL CAPS stays ALL CAPS). Keep %s, %d, {0}, $tokens, \\t and \\n exactly. Product/tech names
(FSR3, DLSS, XeSS, NVIDIA Reflex, Creations, Xbox, PlayStation, Bethesda.net) stay in Latin."""


def read_txt(path):
    b = open(path, "rb").read()
    t = b.decode("utf-16" if b[:2] in (b"\xff\xfe", b"\xfe\xff") else "utf-8-sig")
    d = {}
    for line in t.splitlines():
        if line.startswith("$") and "\t" in line:
            k, v = line.split("\t", 1)
            d[k] = v
    return d


def community():
    """{key: (en, uk)} з XLIFF спільноти; uk='' якщо без перекладу."""
    d = {}
    for u in ET.parse(XLF).iter(tb.X + "trans-unit"):
        g = u.find(tb.X + "target")
        d[u.get("id")] = ("".join(u.find(tb.X + "source").itertext()), "".join(g.itertext()) if g is not None else "")
    return d


def todo():
    en, com = read_txt(EN_TXT), community()
    need = {}
    for k, v in en.items():
        uk = com.get(k, ("", ""))[1]
        if not uk and re.search("[A-Za-z]{2,}", v):
            need[k] = v
    return en, com, need


def prepare(a):
    en, com, need = todo()
    glossary = tb.load_glossary(glob.glob(os.path.join(tb.WORK, "tm", "*.tbx"))[0])
    done = [(k, v[0], v[1]) for k, v in com.items() if v[1]]
    by_tok = {}
    for k, e, u in done:
        for t in re.split(r"[_ ]", k.strip("$").lower())[:1]:
            by_tok.setdefault(t, []).append(f"{k} | {e} => {u}")
    items = [{"id": k, "en": v} for k, v in need.items()]
    with open(CHUNKS, "w", encoding="utf-8") as fh:
        for n, i in enumerate(range(0, len(items), 60)):
            part = items[i:i + 60]
            text = "\n".join(x["en"] for x in part)
            ctx = []
            for x in part:
                t = re.split(r"[_ ]", x["id"].strip("$").lower())[0]
                ctx += by_tok.get(t, [])[:3]
            ctx = list(dict.fromkeys(ctx))[:40] or [f"{k} | {e} => {u}" for k, e, u in done[:30]]
            fh.write(json.dumps({"id": f"iface_{n:03d}", "items": part, "context": ctx,
                                 "glossary": sorted({l for rx, l in glossary if rx.search(text)})},
                                ensure_ascii=False) + "\n")
    open(SYSTEM, "w", encoding="utf-8").write(SYS_TEXT)
    print("keys to translate:", len(items), "chunks:", (len(items) + 59) // 60)


def results():
    return json.load(open(OUT, encoding="utf-8")) if os.path.exists(OUT) else {}


def run(a):
    res = results()
    for line in open(CHUNKS, encoding="utf-8"):
        ch = json.loads(line)
        pend = [i for i in ch["items"] if i["id"] not in res]
        for attempt in range(3):
            if not pend:
                break
            try:
                got = tb.call_claude(ch, pend, a, system=SYSTEM)
            except Exception as e:  # noqa: BLE001
                print(ch["id"], "error:", str(e)[:200]); continue
            good, bad = tb.validate({"items": pend}, got)
            res.update(good)
            pend = [i for i in pend if i["id"] in bad]
            json.dump(res, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
        print(ch["id"], "ok", len(ch["items"]) - len(pend), "/", len(ch["items"]), flush=True)
    print("total:", len(res))


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    sp.add_parser("prepare")
    p = sp.add_parser("run")
    p.add_argument("--model", default="sonnet")
    p.add_argument("--effort", default="low")
    a = ap.parse_args()
    {"prepare": prepare, "run": run}[a.cmd](a)


if __name__ == "__main__":
    main()
