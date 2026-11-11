"""
Нічний бот-перекладач Starfield EN->UK через `claude -p` (підписка Claude Code, без API-ключа).

Кроки:
  python translate_bot.py prepare            # розпакувати XLIFF, нарізати неперекладене на порції
  python translate_bot.py run [--until 07:30] [--limit N] [--parallel 2] [--model sonnet]
  python translate_bot.py status             # скільки зроблено
  python translate_bot.py build              # зібрати XLIFF-zip з результатами

Джерела (у D:\\Starfield):
  starfield_uk_ready.zip  - Crowdin XLIFF (людський переклад, база)
  TM+Glossary.zip         - глосарій
  Starfield_UA_0.87_male-*/Data/strings - старий машинний переклад (лише як чернетка-підказка)

Кожна порція зберігається окремим файлом у work/results, тож бота можна зупиняти й запускати знову.
"""
import argparse, threading, datetime as dt, glob, json, os, re, shutil, struct, subprocess, sys, time, zipfile
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BOT = os.path.join(ROOT, "bot")
WORK = os.path.join(BOT, "work")
RES = os.path.join(WORK, "results")
XNS = "urn:oasis:names:tc:xliff:document:1.2"
X = "{%s}" % XNS
CYR = re.compile("[А-Яа-яІіЇїЄєҐґ]")
TAG = re.compile(r"<[^<>]+>|%[sdif]")
CHUNK_ITEMS, CHUNK_CHARS, CONTEXT_LINES = 40, 5000, 8

SCHEMA = json.dumps({
    "type": "object",
    "properties": {"items": {"type": "array", "items": {
        "type": "object",
        "properties": {"id": {"type": "string"}, "uk": {"type": "string"}},
        "required": ["id", "uk"], "additionalProperties": False}}},
    "required": ["items"], "additionalProperties": False})

SYSTEM = """You are a professional Ukrainian video-game localizer finishing the community Ukrainian translation of Starfield (Bethesda sci-fi RPG).
You receive JSON with: "glossary" (mandatory term translations), "context" (neighbouring lines already translated by the human team - match their style, names and terminology; do not output them), and "items" to translate.
Each item has "en" (source) and may have "draft" (an old MACHINE translation: often clumsy, wrong terminology or wrong ти/ви - use only as a hint, fix freely).

Rules:
- Natural, idiomatic spoken Ukrainian for dialogue; concise for UI, item and quest names. Keep the tone (slang, rudeness, humour, formality).
- Glossary terms are mandatory, inflected correctly (e.g. Ship -> Зореліт; UC -> ОК).
- Names of people: Ukrainian transliteration, g -> ґ like the team does (Sarah Morgan -> Сара Морґан). Corporate/brand names the team keeps in Latin (Terrabrew, Stroud-Eklund, Taiyo, Deimos...) stay in Latin unless the glossary or context shows otherwise.
- Preserve exactly every markup token: <Alias=...>, <Global=...>, <...> tags, %d/%s, {...}, line breaks. Do not translate text inside <...>.
- Use the em dash "—" where English uses " - " as a dash.
- The player character is addressed in masculine forms. If the speaker's gender is unclear, follow the draft or prefer neutral wording.
- ти/ви: strangers, clients, officials, staff -> ви; companions, friends, criminals, enemies, kids -> ти; follow the context lines when they show it.
- Translate every item; never leave English unless it is a proper name or code. Return one output per input id."""


def log(*a):
    print(dt.datetime.now().strftime("%H:%M:%S"), *a, flush=True)


# ---------------------------------------------------------------- prepare
def read_bethesda_strings(path, dl):
    b = open(path, "rb").read()
    n, _ = struct.unpack_from("<II", b, 0)
    base, out = 8 + n * 8, {}
    for i in range(n):
        sid, off = struct.unpack_from("<II", b, 8 + i * 8)
        o = base + off
        if dl:
            L = struct.unpack_from("<I", b, o)[0]
            s = b[o + 4:o + 4 + L].rstrip(b"\0")
        else:
            s = b[o:b.index(b"\0", o)]
        try:
            out[sid] = s.decode("utf-8")          # мод змішує кодування: UTF-8 або cp1251
        except UnicodeDecodeError:
            out[sid] = s.decode("cp1251", "replace")
    return out


def load_glossary(path):
    ns = "{urn:iso:std:iso:30042:ed-2}"
    xl = "{http://www.w3.org/XML/1998/namespace}lang"
    out = []
    for ce in ET.parse(path).getroot().iter(ns + "conceptEntry"):
        terms = {}
        for ls in ce.findall(ns + "langSec"):
            terms[ls.get(xl)] = [t.text for t in ls.iter(ns + "term") if t.text]
        en, uk = terms.get("en"), terms.get("uk")
        if not en or not uk:
            continue
        note = ""
        for d in ce.iter(ns + "descrip"):
            if d.get("type") in ("context", "definition") and d.text:
                note = d.text.strip().replace("\n", " ")[:120]
        for e in en:
            if len(e) < 2:
                continue
            rx = re.compile(r"(?<![A-Za-z])" + re.escape(e) + r"(?:s|es|'s)?(?![A-Za-z])", re.I)
            out.append((rx, f"{e} → {' / '.join(uk)}" + (f"  ({note})" if note else "")))
    return out


def is_editor_id(s):
    return " " not in s.strip() and ("_" in s or re.search(r"[a-z][A-Z]", s) is not None)


def prepare(a):
    os.makedirs(RES, exist_ok=True)
    src = os.path.join(WORK, "xliff")
    if not os.path.isdir(src):
        zipfile.ZipFile(os.path.join(ROOT, "starfield_uk_ready.zip")).extractall(src)
    gl_dir = os.path.join(WORK, "tm")
    if not os.path.isdir(gl_dir):
        zipfile.ZipFile(os.path.join(ROOT, "TM+Glossary.zip")).extractall(gl_dir)
    glossary = load_glossary(glob.glob(os.path.join(gl_dir, "*.tbx"))[0])
    log("glossary terms:", len(glossary))
    mod_dir = glob.glob(os.path.join(ROOT, a.draft_dir))[0]
    mod = {k.lower(): read_bethesda_strings(os.path.join(mod_dir, f"Starfield_uk.{k}"), k != "STRINGS")
           for k in ("STRINGS", "DLSTRINGS", "ILSTRINGS")}
    chunks = []
    for f in sorted(glob.glob(os.path.join(src, "**", "*.xliff"), recursive=True)):
        rel = os.path.relpath(f, src)
        kind = "ilstrings" if "ilstrings" in f else "dlstrings" if "dlstrings" in f else "strings"
        recent, cur, cur_chars = [], [], 0

        def flush():
            nonlocal cur, cur_chars
            if cur:
                text = " ".join(i["en"] for i in cur)
                terms = sorted({line for rx, line in glossary if rx.search(text)})
                chunks.append({"id": f"{len(chunks):05d}", "file": rel, "items": cur,
                               "context": list(recent[-CONTEXT_LINES:]), "glossary": terms})
            cur, cur_chars = [], 0

        for u in ET.parse(f).iter(X + "trans-unit"):
            s = "".join(u.find(X + "source").itertext())
            g = u.find(X + "target")
            t = "".join(g.itertext()) if g is not None else ""
            st = g.get("state") if g is not None else None
            if CYR.search(t):
                recent.append({"en": s, "uk": t})
                recent = recent[-CONTEXT_LINES:]
                continue
            todo = (g is None or st == "needs-translation" or not t.strip())
            if not todo or not re.search("[A-Za-z]{2}", s) or is_editor_id(s):
                continue
            item = {"id": u.get("id"), "en": s}
            d = mod.get(kind, {}).get(int(u.get("id"), 16))
            if d and CYR.search(d):
                item["draft"] = d
            cur.append(item)
            cur_chars += len(s)
            if len(cur) >= CHUNK_ITEMS or cur_chars >= CHUNK_CHARS:
                flush()
        flush()
    with open(os.path.join(WORK, "chunks.jsonl"), "w", encoding="utf-8") as fh:
        for c in chunks:
            fh.write(json.dumps(c, ensure_ascii=False) + "\n")
    open(os.path.join(WORK, "system.txt"), "w", encoding="utf-8").write(SYSTEM)
    log(f"chunks: {len(chunks)}, items: {sum(len(c['items']) for c in chunks)}")


# ---------------------------------------------------------------- run
def load_chunks():
    with open(os.path.join(WORK, "chunks.jsonl"), encoding="utf-8") as fh:
        return [json.loads(l) for l in fh]


def validate(chunk, items):
    by_id = {i["id"]: i["uk"] for i in items}
    good, bad = {}, []
    for it in chunk["items"]:
        uk = by_id.get(it["id"], "")
        ok = bool(uk.strip())
        ok = ok and sorted(TAG.findall(it["en"])) == sorted(TAG.findall(uk))
        ok = ok and it["en"].count("\n") == uk.count("\n")
        ok = ok and it["en"].count("\\n") == uk.count("\\n")  # літеральні \r\n у записках
        kept_name = uk.strip() == it["en"].strip() and len(it["en"]) <= 40  # назви/ID лишили латиницею
        if ok and not kept_name and len(re.findall("[A-Za-z]{3,}", it["en"])) >= 2 and not CYR.search(uk):
            ok = False
        (good.__setitem__(it["id"], uk) if ok else bad.append(it["id"]))
    return good, bad


USAGE_LOCK = threading.Lock()
LIMITS = {}  # "five_hour"/"seven_day" -> (utilization 0..1, resetsAt unix time), з rate_limit_event


def wait_for_limits(a):
    """Пауза, якщо сесія >= --max-session; False, якщо тиждень >= --max-week (тоді зупиняємось)."""
    while True:
        with USAGE_LOCK:
            five = LIMITS.get("five_hour", (0.0, 0))
            week = LIMITS.get("seven_day", (0.0, 0))
        if week[0] >= a.max_week:
            log(f"week usage {week[0]:.0%} >= {a.max_week:.0%} - stopping")
            open(os.path.join(BOT, "STOP"), "w").write("week limit")
            return False
        if five[0] < a.max_session:
            return True
        resume = five[1] + 120
        log(f"session usage {five[0]:.0%} >= {a.max_session:.0%} - pause until "
            f"{dt.datetime.fromtimestamp(resume):%H:%M}")
        while time.time() < resume:
            if os.path.exists(os.path.join(BOT, "STOP")):
                return False
            time.sleep(30)
        with USAGE_LOCK:
            if LIMITS.get("five_hour", (0, 0))[1] == five[1]:
                LIMITS["five_hour"] = (0.0, 0)   # вікно скинулось; нове значення прийде з наступним викликом


class LimitHit(Exception):
    pass


def call_claude(chunk, items, a, prompt=None, system=None):
    if prompt is None:
        payload = {"glossary": chunk["glossary"], "context": chunk["context"],
                   "items": [{k: v for k, v in i.items()} for i in items]}
        prompt = "Translate the items. Input JSON:\n" + json.dumps(payload, ensure_ascii=False)
    cmd = [shutil.which("claude") or "claude", "-p", "--model", a.model, "--effort", a.effort,
           "--tools", "", "--strict-mcp-config", "--disable-slash-commands", "--no-session-persistence", "--output-format", "stream-json", "--verbose",
           "--system-prompt-file", system or os.path.join(WORK, "system.txt"), "--json-schema", SCHEMA]
    p = subprocess.run(cmd, input=prompt, capture_output=True, text=True, encoding="utf-8",
                       timeout=900, cwd=WORK)
    out = (p.stdout or "").strip()
    r = None
    for line in out.splitlines():
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        if ev.get("type") == "rate_limit_event":
            w = (ev.get("rate_limit_info") or {}).get("unifiedWindows") or {}
            with USAGE_LOCK:
                for k in ("five_hour", "seven_day"):
                    if k in w:
                        LIMITS[k] = (w[k].get("utilization", 0.0), w[k].get("resetsAt", 0))
        elif ev.get("type") == "result":
            r = ev
    if r is None:
        r = {"is_error": True, "result": out[-500:] + (p.stderr or "")}
    if r.get("is_error") or r.get("subtype") != "success":
        msg = str(r.get("result", "")) + " " + str(r.get("api_error_status", ""))
        if re.search(r"limit|429|overloaded|529", msg, re.I):
            raise LimitHit(msg[:300])
        raise RuntimeError(msg[:300])
    u = r.get("usage") or {}
    with USAGE_LOCK, open(os.path.join(WORK, "usage.jsonl"), "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"t": dt.datetime.now().isoformat(timespec="seconds"), "chunk": chunk["id"],
                             "n": len(items), "in": u.get("input_tokens", 0),
                             "cache_w": u.get("cache_creation_input_tokens", 0),
                             "cache_r": u.get("cache_read_input_tokens", 0),
                             "out": u.get("output_tokens", 0), "usd": r.get("total_cost_usd", 0)}) + "\n")
    return (r.get("structured_output") or {}).get("items", [])


def do_chunk(chunk, a):
    path = os.path.join(RES, chunk["id"] + ".json")
    good, pending, calls_ok, last_err = {}, list(chunk["items"]), 0, ""
    for attempt in range(3):
        try:
            got = call_claude(chunk, pending, a)
            calls_ok += 1
        except RuntimeError as e:
            last_err = str(e)
            log(f"[{chunk['id']}] error: {e}")
            continue
        g, bad = validate({"items": pending}, got)
        good.update(g)
        pending = [i for i in pending if i["id"] in bad]
        if not pending:
            break
    if calls_ok == 0:  # жодного вдалого виклику: ймовірно ліміт/збій - нічого не записуємо, чекаємо
        raise LimitHit("all attempts failed: " + last_err)
    json.dump({"file": chunk["file"], "good": good, "failed": [i["id"] for i in pending]},
              open(path + ".tmp", "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    os.replace(path + ".tmp", path)
    log(f"[{chunk['id']}] ok {len(good)}/{len(chunk['items'])}")


def retry_failed(a):
    """Повторно перекласти лише рядки, що не пройшли перевірку."""
    chunks = {c["id"]: c for c in load_chunks()}
    for p in sorted(glob.glob(os.path.join(RES, "*.json"))):
        r = json.load(open(p, encoding="utf-8"))
        if not r["failed"]:
            continue
        c = dict(chunks[os.path.basename(p)[:-5]])
        c["items"] = [i for i in c["items"] if i["id"] in r["failed"]]
        try:
            got = call_claude(c, c["items"], a)
        except (RuntimeError, LimitHit) as e:
            log(f"[{c['id']}] error: {e}")
            continue
        good, bad = validate(c, got)
        r["good"].update(good)
        r["failed"] = bad
        json.dump(r, open(p + ".tmp", "w", encoding="utf-8"), ensure_ascii=False, indent=0)
        os.replace(p + ".tmp", p)
        log(f"[{c['id']}] retry: fixed {len(good)}, still failed {len(bad)}")
        for i in c["items"]:
            if i["id"] in bad:
                g = next((x["uk"] for x in got if x["id"] == i["id"]), "")
                log(f"    EN: {i['en'][:150]!r}\n    UK: {g[:150]!r}")


def past_until(a):
    if os.path.exists(os.path.join(BOT, "STOP")):
        return True
    return a._stop is not None and dt.datetime.now() >= a._stop


def run(a):
    a._stop = None
    if a.until:
        hh, mm = map(int, a.until.split(":"))
        now = dt.datetime.now()
        a._stop = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
        if a._stop <= now:
            a._stop += dt.timedelta(days=1)
    todo = [c for c in load_chunks() if not os.path.exists(os.path.join(RES, c["id"] + ".json"))]
    if a.file:
        todo = [c for c in todo if a.file in c["file"]]
    if a.limit:
        todo = todo[:a.limit]
    log(f"to do: {len(todo)} chunks, model={a.model}, parallel={a.parallel}, until={a.until}")

    def worker(c):
        while not past_until(a):
            if not wait_for_limits(a):
                return
            try:
                do_chunk(c, a)
                return
            except LimitHit as e:
                log(f"limit/overload, sleeping {a.sleep} min: {str(e)[:120]}")
                time.sleep(a.sleep * 60)
            except subprocess.TimeoutExpired:
                log(f"[{c['id']}] timeout, retry")

    with ThreadPoolExecutor(a.parallel) as ex:
        for _ in ex.map(worker, todo):
            pass
    log("stopped" if past_until(a) else "finished")


# ---------------------------------------------------------------- status / build
def status(a):
    chunks = load_chunks()
    total = sum(len(c["items"]) for c in chunks)
    done = failed = n = 0
    for p in glob.glob(os.path.join(RES, "*.json")):
        r = json.load(open(p, encoding="utf-8"))
        done += len(r["good"]); failed += len(r["failed"]); n += 1
    up = os.path.join(WORK, "usage.jsonl")
    if os.path.exists(up):
        us = []
        for l in open(up, encoding="utf-8"):
            for part in re.findall(r"\{[^{}]*\}", l):
                try:
                    us.append(json.loads(part))
                except json.JSONDecodeError:
                    pass
        s = lambda k: sum(x[k] for x in us)
        print(f"calls {len(us)}  tokens in {s('in')+s('cache_w')+s('cache_r')} (cache read {s('cache_r')})  out {s('out')}  "
              f"API-equivalent ${s('usd'):.2f}")
    print(f"chunks {n}/{len(chunks)}  lines ok {done}/{total} ({100*done/max(total,1):.1f}%)  failed {failed}")


def build(a):
    res = {}
    for p in glob.glob(os.path.join(RES, "*.json")):
        r = json.load(open(p, encoding="utf-8"))
        res.setdefault(r["file"], {}).update(r["good"])
    ET.register_namespace("", XNS)
    src = os.path.join(WORK, "xliff")
    out_zip = os.path.join(ROOT, f"starfield_uk_bot_{dt.date.today():%Y%m%d}.zip")
    with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(glob.glob(os.path.join(src, "**", "*.xliff"), recursive=True)):
            rel = os.path.relpath(f, src)
            tr = res.get(rel, {})
            tree = ET.parse(f)
            n = 0
            for u in tree.iter(X + "trans-unit"):
                uk = tr.get(u.get("id"))
                if uk is None:
                    continue
                g = u.find(X + "target")
                if g is None:
                    g = ET.SubElement(u, X + "target")
                g.clear()
                g.text = uk
                g.set("state", a.state)
                n += 1
            tmp = os.path.join(WORK, "build.tmp")
            tree.write(tmp, encoding="UTF-8", xml_declaration=True)
            z.write(tmp, rel.replace("\\", "/"))
            log(f"{rel}: {n} new translations")
    log("written", out_zip)


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("prepare"); p.add_argument("--draft-dir", default="Starfield_UA_0.87_male-*/Data/strings")
    p = sp.add_parser("run")
    p.add_argument("--model", default="sonnet")
    p.add_argument("--effort", default="low")
    p.add_argument("--parallel", type=int, default=2)
    p.add_argument("--file", default="", help="лише порції з файлу, що містить цей текст (напр. part_2)")
    p.add_argument("--limit", type=int, default=0, help="лише N порцій (для тесту)")
    p.add_argument("--until", default="", help="HH:MM - не брати нових порцій після цього часу")
    p.add_argument("--sleep", type=int, default=20, help="хвилин чекати при вичерпаному ліміті")
    p.add_argument("--max-session", type=float, default=0.85, help="пауза до скидання, коли 5-год сесія >= цього")
    p.add_argument("--max-week", type=float, default=0.90, help="повна зупинка, коли тиждень >= цього")
    p = sp.add_parser("retry")
    p.add_argument("--model", default="sonnet")
    p.add_argument("--effort", default="low")
    sp.add_parser("status")
    p = sp.add_parser("build"); p.add_argument("--state", default="needs-review-translation")
    a = ap.parse_args()
    {"prepare": prepare, "run": run, "retry": retry_failed, "status": status, "build": build}[a.cmd](a)


if __name__ == "__main__":
    main()
