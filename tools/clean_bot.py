"""
Чиста версія (для Nexus): переклад рядків, які в звичайній збірці брались з моду 0.87 (8307),
а в --no-draft стали англійськими. Без підказок з 0.87.
  python clean_bot.py prepare   # (dist має бути ЗВИЧАЙНОЮ збіркою) -> знімок, збірка --no-draft, порції
  python clean_bot.py run       # переклад -> work/dlc_results/c*.json (підхоплює build_game через dlc_bot.results)
"""
import argparse, glob, json, os, re, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import translate_bot as tb  # noqa: E402
import dlc_bot  # noqa: E402
from translate_bot import CYR, read_bethesda_strings, is_editor_id  # noqa: E402

OURS = os.path.join(tb.ROOT, "dist", "Data", "Strings")
CHUNKS = os.path.join(tb.WORK, "clean_chunks.jsonl")


def snapshot():
    out = {}
    for f in os.listdir(OURS):
        ext = f.rsplit(".", 1)[1].upper()
        out[f.lower()] = read_bethesda_strings(os.path.join(OURS, f), ext != "STRINGS")
    return out


def prepare(a):
    normal = snapshot()
    subprocess.run([sys.executable, "-I", os.path.join(tb.BOT, "build_game.py"), "--no-draft"], check=True,
                   stdout=subprocess.DEVNULL)
    clean = snapshot()
    done = dlc_bot.results()
    glossary = tb.load_glossary(glob.glob(os.path.join(tb.WORK, "tm", "*.tbx"))[0])
    chunks, n = [], 0
    for plug, ext, p in dlc_bot.game_files():
        key = f"{plug}_uk.{ext}".lower()
        en = read_bethesda_strings(p, ext != "STRINGS")
        nm, cl = normal.get(key, {}), clean.get(key, {})
        have = done.get((plug.lower(), ext), {})
        items = [{"id": f"{sid:08X}", "en": s} for sid, s in sorted(en.items())
                 if CYR.search(nm.get(sid, "")) and not CYR.search(cl.get(sid, ""))
                 and sid not in have and re.search("[A-Za-z]{2}", s) and not is_editor_id(s)]
        ctx = [{"en": en[k], "uk": v} for k, v in list(cl.items())[:4000] if k in en and CYR.search(v)][::500][:tb.CONTEXT_LINES]
        for i in range(0, len(items), tb.CHUNK_ITEMS):
            part = items[i:i + tb.CHUNK_ITEMS]
            text = " ".join(x["en"] for x in part)
            chunks.append({"id": f"c{len(chunks):04d}", "file": f"{plug}_en.{ext.lower()}", "items": part,
                           "context": ctx, "glossary": sorted({l for rx, l in glossary if rx.search(text)})})
            n += len(part)
    with open(CHUNKS, "w", encoding="utf-8") as fh:
        for c in chunks:
            fh.write(json.dumps(c, ensure_ascii=False) + "\n")
    print(f"clean chunks: {len(chunks)}, items: {n}")
    subprocess.run([sys.executable, "-I", os.path.join(tb.BOT, "build_game.py")], check=True, stdout=subprocess.DEVNULL)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["prepare", "run", "status", "retry"])
    for k, v in (("--model", "sonnet"), ("--effort", "low"), ("--file", ""), ("--until", "")):
        ap.add_argument(k, default=v)
    for k, v in (("--parallel", 3), ("--limit", 0), ("--sleep", 20)):
        ap.add_argument(k, type=int, default=v)
    ap.add_argument("--max-session", type=float, default=0.85)
    ap.add_argument("--max-week", type=float, default=0.90)
    a = ap.parse_args()
    tb.RES = dlc_bot.DRES
    tb.load_chunks = lambda: [json.loads(l) for l in open(CHUNKS, encoding="utf-8")]
    {"prepare": prepare, "run": tb.run, "status": tb.status, "retry": tb.retry_failed}[a.cmd](a)


if __name__ == "__main__":
    main()
