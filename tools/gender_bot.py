"""
Жіноча версія: переписує в жіночий рід лише ті форми, що стосуються персонажа гравця.
Працює по готовому (чоловічому) тексту з dist\\Data\\Strings, мовців бере з work\\speakers.json (esm_speakers.py).
  python gender_bot.py prepare           - відібрати рядки-кандидати -> work/fem_chunks.jsonl
  python gender_bot.py prepare --dlc     - дописати кандидатів із DLC (work/speakers_<plugin>.json)
  python gender_bot.py run [--limit N]   - прогнати через Claude (паузи/STOP як у translate_bot)
  python gender_bot.py status
  python gender_bot.py show [--n 40]     - показати зміни (було -> стало)
Результат: work/fem_results/*.json  {"good": {"<hex id>": "текст"}}  (лише змінені рядки)
"""
import argparse, glob, json, os, re, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor
import xml.etree.ElementTree as ET

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import translate_bot as tb  # noqa: E402
from translate_bot import ROOT, WORK, BOT, X, TAG, CYR, log, read_bethesda_strings  # noqa: E402

FRES = os.path.join(WORK, "fem_results")
FCHUNKS = os.path.join(WORK, "fem_chunks.jsonl")
FSYS = os.path.join(WORK, "fem_system.txt")
DIST = os.path.join(ROOT, "dist", "Data", "Strings")

W = r"[а-яіїєґ'’]"
MASC = re.compile(rf"(?<!{W}){W}{{2,}}(в|вся|ний|ий|ен|ин|ним|ного|ному)(?!{W})", re.I)
VOC = re.compile(rf"(?<!{W})(друже|брате|братан|хлопче|хлопець|чоловіче|синку|сину|пане|пана|сер|містере|красеню|приятелю|старий)(?!{W})", re.I)
P1 = re.compile(rf"(?<!{W})(я|мене|мені|мною|сам)(?!{W})", re.I)
P2 = re.compile(rf"(?<!{W})(ти|тебе|тобі|тобою|ви|вас|вам|вами|сам|сами)(?!{W})", re.I)

SYSTEM = """You edit an existing Ukrainian translation of Starfield (Bethesda sci-fi RPG) to make a version for a FEMALE player character.
The current text uses MASCULINE forms for the player. Change ONLY grammatical forms that refer to the player character:
- who="player": a line the player character says, or (kind "journal") the player's own quest journal in first person.
  Change first-person masculine forms: я зробив -> я зробила, я радий -> я рада, сам -> сама, готовий -> готова, певен -> певна, мусив -> мусила.
- who="npc": an NPC speaking TO the player. Change forms addressing the player: ти був -> ти була, ви готовий -> ви готова,
  ти сам -> ти сама, vocatives друже/брате/хлопче -> подруго/сестро/дівчино (keep tone), пане -> пані, сер -> пані, містере -> пані.
  Polite plural "ви" with plural verb (ви були, ви зробили) is already neutral - leave it. Keep the NPC's OWN gender (я почав stays).
  Third-person mentions of the player (він/його) only when English clearly refers to the player ("the Captain", "our new recruit") - otherwise leave.
Never change forms about other people, groups, objects; never rephrase, fix style or translate anything else. If "en" addresses several people, leave it.
Keep every markup token (<...>, %d, line breaks) exactly. Inflect the rest of the sentence to agree.
Return ONLY the items you changed (empty list if none)."""


def final_texts():
    """Чоловічий готовий текст з dist + англійські джерела з XLIFF."""
    uk = {"ILSTRINGS": read_bethesda_strings(os.path.join(DIST, "Starfield_uk.ILSTRINGS"), True),
          "DLSTRINGS": read_bethesda_strings(os.path.join(DIST, "Starfield_uk.DLSTRINGS"), True)}
    en = {}
    for f in glob.glob(os.path.join(WORK, "xliff", "strings", "*.xliff")):
        if "ilstrings" not in f and "dlstrings" not in f:
            continue
        for u in ET.parse(f).iter(X + "trans-unit"):
            en[u.get("id").upper().zfill(8)] = "".join(u.find(X + "source").itertext())
    return uk, en


def dlc_sources():
    """[(speakers dict, {EXT: uk texts}, {hex id: en}, file prefix)] для DLC."""
    import dlc_bot
    out = []
    for sp_path in glob.glob(os.path.join(WORK, "speakers_*.json")):
        plug = os.path.basename(sp_path)[9:-5]
        uk, en = {}, {}
        for ext in ("ILSTRINGS", "DLSTRINGS"):
            q = dlc_bot.find_ci(DIST, f"{plug}_uk.{ext}")
            g = dlc_bot.find_ci(dlc_bot.GEN, f"{plug}_en.{ext}")
            uk[ext] = read_bethesda_strings(q, True) if q else {}
            if g:
                en.update({f"{k:08X}": v for k, v in read_bethesda_strings(g, True).items()})
        out.append((json.load(open(sp_path)), uk, en, plug))
    return out


def prepare(a):
    if a.dlc:
        old = load()
        n0 = len(old)
        new = []
        for sp, uk, en, plug in dlc_sources():
            new += collect(sp, uk, en, plug)
        chunks = make_chunks(new, start=n0, prefix="g")
        with open(FCHUNKS, "a", encoding="utf-8") as fh:
            for c in chunks:
                fh.write(json.dumps(c, ensure_ascii=False) + "\n")
        log(f"fem dlc chunks: {len(chunks)}, items: {len(new)}")
        return
    sp = json.load(open(os.path.join(WORK, "speakers.json")))
    uk, en = final_texts()
    items = collect(sp, uk, en, "Starfield")
    chunks = make_chunks(items)
    with open(FCHUNKS, "w", encoding="utf-8") as fh:
        for c in chunks:
            fh.write(json.dumps(c, ensure_ascii=False) + "\n")
    open(FSYS, "w", encoding="utf-8").write(SYSTEM)
    os.makedirs(FRES, exist_ok=True)
    log(f"fem chunks: {len(chunks)}, items: {len(items)}")


def collect(sp, uk, en, plug):
    items = []
    for sid, kind in sp.items():
        ext = "DLSTRINGS" if kind == "journal" else "ILSTRINGS"
        s = uk[ext].get(int(sid, 16))
        if not s or not CYR.search(s):
            continue
        if kind in ("player", "journal"):
            ok = P1.search(s) and MASC.search(s)
            who = "player"
        elif kind == "to_player":
            ok = (P2.search(s) and MASC.search(s)) or VOC.search(s)
            who = "npc"
        else:
            continue
        if ok:
            it = {"id": sid, "who": who, "en": en.get(sid, ""), "uk": s}
            if kind == "journal":
                it["kind"] = "journal"
            items.append((f"{plug}_uk.{ext}", it))
    items.sort(key=lambda x: (x[0], x[1]["id"]))
    return items


def make_chunks(items, start=0, prefix="f"):
    chunks, cur, chars = [], [], 0
    for fn, it in items:
        if cur and (cur[0][0] != fn or len(cur) >= 40 or chars >= 6000):
            chunks.append(cur); cur, chars = [], 0
        cur.append((fn, it)); chars += len(it["uk"]) + len(it["en"])
    if cur:
        chunks.append(cur)
    return [{"id": f"{prefix}{start + n:04d}", "file": c[0][0], "ext": c[0][0].rsplit(".", 1)[1],
             "items": [i for _, i in c]} for n, c in enumerate(chunks)]


def load():
    return [json.loads(l) for l in open(FCHUNKS, encoding="utf-8")]


def valid(orig, new):
    return (bool(new.strip()) and CYR.search(new) is not None
            and sorted(TAG.findall(orig)) == sorted(TAG.findall(new))
            and orig.count("\n") == new.count("\n") and orig.count("\\n") == new.count("\\n")
            and 0.8 <= len(new) / max(len(orig), 1) <= 1.25)


def do_chunk(c, a):
    prompt = "Edit the items. Input JSON:\n" + json.dumps(
        {"items": [{k: v for k, v in i.items()} for i in c["items"]]}, ensure_ascii=False)
    last = ""
    for attempt in range(3):
        try:
            got = tb.call_claude(c, c["items"], a, prompt=prompt, system=FSYS)
        except RuntimeError as e:
            last = str(e); log(f"[{c['id']}] error: {e}"); continue
        orig = {i["id"]: i["uk"] for i in c["items"]}
        good, bad = {}, []
        for g in got:
            o = orig.get(g.get("id", ""))
            if o is None or g["uk"] == o:
                continue
            (good.__setitem__(g["id"], g["uk"]) if valid(o, g["uk"]) else bad.append(g["id"]))
        json.dump({"ext": c["ext"], "file": c.get("file", "Starfield_uk." + c["ext"]), "good": good, "rejected": bad},
                  open(os.path.join(FRES, c["id"] + ".json"), "w", encoding="utf-8"), ensure_ascii=False, indent=0)
        log(f"[{c['id']}] changed {len(good)}/{len(c['items'])}" + (f", rejected {len(bad)}" if bad else ""))
        return
    raise tb.LimitHit("all attempts failed: " + last)


def run(a):
    a._stop = None
    todo = [c for c in load() if not os.path.exists(os.path.join(FRES, c["id"] + ".json"))]
    if a.limit:
        todo = todo[:a.limit]
    log(f"fem to do: {len(todo)} chunks")

    def worker(c):
        while not os.path.exists(os.path.join(BOT, "STOP")):
            if not tb.wait_for_limits(a):
                return
            try:
                return do_chunk(c, a)
            except tb.LimitHit as e:
                log(f"limit/overload, sleeping {a.sleep} min: {str(e)[:120]}")
                time.sleep(a.sleep * 60)
            except subprocess.TimeoutExpired:
                log(f"[{c['id']}] timeout, retry")

    with ThreadPoolExecutor(a.parallel) as ex:
        list(ex.map(worker, todo))
    log("fem stopped" if os.path.exists(os.path.join(BOT, "STOP")) else "fem finished")


def results():
    """{file name lower: {int id: text}}"""
    out = {}
    for p in glob.glob(os.path.join(FRES, "*.json")):
        r = json.load(open(p, encoding="utf-8"))
        fn = r.get("file", "Starfield_uk." + r["ext"]).lower()
        out.setdefault(fn, {}).update({int(k, 16): v for k, v in r["good"].items()})
    return out


def status(a):
    chunks = load()
    done = glob.glob(os.path.join(FRES, "*.json"))
    ch = sum(len(v) for v in results().values())
    print(f"fem chunks {len(done)}/{len(chunks)}  lines {sum(len(c['items']) for c in chunks)}  changed {ch}")


def show(a):
    items = {i["id"]: i for c in load() for i in c["items"]}
    n = 0
    for ext, d in results().items():
        for sid, new in d.items():
            it = items[f"{sid:08X}"]
            print(f"[{it['who']}{'/journal' if it.get('kind') else ''}] {it['en'][:140]}\n  M: {it['uk'][:160]}\n  F: {new[:160]}\n")
            n += 1
            if n >= a.n:
                return


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["prepare", "run", "status", "show"])
    ap.add_argument("--model", default="sonnet")
    ap.add_argument("--effort", default="low")
    ap.add_argument("--parallel", type=int, default=3)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--sleep", type=int, default=20)
    ap.add_argument("--max-session", type=float, default=0.85)
    ap.add_argument("--max-week", type=float, default=0.90)
    ap.add_argument("--n", type=int, default=40)
    ap.add_argument("--dlc", action="store_true")
    a = ap.parse_args()
    {"prepare": prepare, "run": run, "status": status, "show": show}[a.cmd](a)


if __name__ == "__main__":
    main()
