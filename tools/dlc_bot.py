"""
Переклад рядків, яких немає в XLIFF: DLC/плагіни (SFBGS003/004/006/007/008/00D/047, BlueprintShips)
і нові рядки основної гри з оновлень. Англійські оригінали береться з архівів гри (ba2.py -> work/game_en).
  python dlc_bot.py extract [папка Data гри]   - витягти *_en.* з BA2
  python dlc_bot.py prepare                    - work/dlc_chunks.jsonl (чернетка: старий 0.87 *_uk, якщо є)
  python dlc_bot.py run [--parallel 3]         - той самий рушій, що й translate_bot (паузи 85%/90%, STOP)
  python dlc_bot.py status
Результат: work/dlc_results/*.json, використовує build_game.py.
"""
import argparse, glob, json, os, re, sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import translate_bot as tb  # noqa: E402
import ba2  # noqa: E402
from translate_bot import ROOT, WORK, CYR, log, read_bethesda_strings, is_editor_id  # noqa: E402

GAME = r"D:\Steam\SteamApps\common\Starfield\Data"
GEN = os.path.join(WORK, "game_en", "strings")
DRES = os.path.join(WORK, "dlc_results")
DCHUNKS = os.path.join(WORK, "dlc_chunks.jsonl")
MOD = glob.glob(os.path.join(ROOT, "Starfield_UA_0.87_male-*", "Data", "strings"))[0]


def game_files():
    """[(plugin, ext, path)] для всіх англійських файлів рядків гри."""
    out = []
    for p in sorted(glob.glob(os.path.join(GEN, "*_en.*"))):
        plug, ext = os.path.basename(p).rsplit("_en.", 1)
        out.append((plug, ext.upper(), p))
    return out


def find_ci(folder, name):
    for q in glob.glob(os.path.join(folder, "*")):
        if os.path.basename(q).lower() == name.lower():
            return q


def extract(a):
    data = a.game or GAME
    for p in glob.glob(os.path.join(data, "*.ba2")):
        if re.search(r"Textures|Voices|Meshes|Shaders|Terrain|Anim|Particles|Planet|Lod|Materials|Face", p):
            continue
        for name, off, packed, size in ba2.entries(p):
            if name.lower().startswith("strings/") and "_en." in name.lower():
                out = os.path.join(WORK, "game_en", name.replace("/", os.sep))
                os.makedirs(os.path.dirname(out), exist_ok=True)
                open(out, "wb").write(ba2.read(p, off, packed, size))
    log("extracted:", len(game_files()), "files")


def prepare(a):
    glossary = tb.load_glossary(glob.glob(os.path.join(WORK, "tm", "*.tbx"))[0])
    ours = os.path.join(ROOT, "dist", "Data", "Strings")
    chunks = []
    for plug, ext, p in game_files():
        dl = ext != "STRINGS"
        en = read_bethesda_strings(p, dl)
        have = {}
        if plug.lower() == "starfield":       # основна гра: лише те, чого немає/англійське у нашій збірці
            q = find_ci(ours, f"starfield_uk.{ext}")
            have = read_bethesda_strings(q, dl) if q else {}
        dq = find_ci(MOD, f"{plug}_uk.{ext}")
        draft = read_bethesda_strings(dq, dl) if dq else {}
        cur, chars, recent = [], 0, []

        def flush():
            nonlocal cur, chars
            if cur:
                text = " ".join(i["en"] for i in cur)
                chunks.append({"id": f"d{len(chunks):04d}", "file": f"{plug}_en.{ext.lower()}", "items": cur,
                               "context": list(recent[-tb.CONTEXT_LINES:]),
                               "glossary": sorted({l for rx, l in glossary if rx.search(text)})})
            cur, chars = [], 0

        for sid in sorted(en):
            s = en[sid]
            if CYR.search(have.get(sid, "")):
                recent = (recent + [{"en": s, "uk": have[sid]}])[-tb.CONTEXT_LINES:]
                continue
            if not re.search("[A-Za-z]{2}", s) or is_editor_id(s):
                continue
            it = {"id": f"{sid:08X}", "en": s}
            if CYR.search(draft.get(sid, "")):
                it["draft"] = draft[sid]
            cur.append(it); chars += len(s)
            if len(cur) >= tb.CHUNK_ITEMS or chars >= tb.CHUNK_CHARS:
                flush()
        flush()
    with open(DCHUNKS, "w", encoding="utf-8") as fh:
        for c in chunks:
            fh.write(json.dumps(c, ensure_ascii=False) + "\n")
    os.makedirs(DRES, exist_ok=True)
    log(f"dlc chunks: {len(chunks)}, items: {sum(len(c['items']) for c in chunks)}")


def use_dlc_paths():
    tb.RES = DRES
    tb.load_chunks = lambda: [json.loads(l) for l in open(DCHUNKS, encoding="utf-8")]


def results():
    """{(plugin_lower, EXT): {int id: text}}"""
    out = {}
    for p in glob.glob(os.path.join(DRES, "*.json")):
        r = json.load(open(p, encoding="utf-8"))
        plug, ext = r["file"].rsplit("_en.", 1)
        out.setdefault((plug.lower(), ext.upper()), {}).update({int(k, 16): v for k, v in r["good"].items()})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["extract", "prepare", "run", "status", "retry"])
    ap.add_argument("game", nargs="?")
    ap.add_argument("--model", default="sonnet")
    ap.add_argument("--effort", default="low")
    ap.add_argument("--parallel", type=int, default=3)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--file", default="")
    ap.add_argument("--until", default="")
    ap.add_argument("--sleep", type=int, default=20)
    ap.add_argument("--max-session", type=float, default=0.85)
    ap.add_argument("--max-week", type=float, default=0.90)
    a = ap.parse_args()
    use_dlc_paths()
    {"extract": extract, "prepare": prepare, "run": tb.run, "status": tb.status, "retry": tb.retry_failed}[a.cmd](a)


if __name__ == "__main__":
    main()
