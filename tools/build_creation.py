"""
Версія для магазину Creations (Bethesda.net, ПК і Xbox).
Creation не може змінити StarfieldCustom.ini (sLanguage=uk), тому підмінюємо АНГЛІЙСЬКІ файли українськими:
  Strings/*_uk.*        -> strings/*_en.*
  Interface/translate_uk.txt -> interface/translate_en.txt
  fonts_uk.*, fontconfig_uk.txt -> fonts_en.*, fontconfig_en.txt (fontlib "fonts_en")
Результат: dist/creation/{hero,heroine}/Data/... - ці файли додаються в архів Creation через Creation Kit
(разом з порожнім плагіном StarfieldUA.esm, який створює CK).
  python build_creation.py    (після build_game.py)
"""
import os, shutil

BOT = os.path.dirname(os.path.abspath(__file__))
DIST = os.path.join(os.path.dirname(BOT), "dist")
OUT = os.path.join(DIST, "creation")


def en_name(fn):
    base, ext = fn.rsplit(".", 1)
    return base[:-3].lower() + "_en." + ext.lower() if base.lower().endswith("_uk") else None


def build(variant, overlay):
    root = os.path.join(OUT, variant, "Data")
    shutil.rmtree(os.path.join(OUT, variant), ignore_errors=True)
    sdir, idir = os.path.join(root, "strings"), os.path.join(root, "interface")
    os.makedirs(sdir), os.makedirs(idir)
    src = {f: os.path.join(DIST, "Data", "Strings", f) for f in os.listdir(os.path.join(DIST, "Data", "Strings"))}
    if overlay:
        fem = os.path.join(DIST, "Female", "Strings")
        lower = {k.lower(): k for k in src}
        for f in os.listdir(fem):
            src.pop(lower.get(f.lower(), f), None)
            src[f] = os.path.join(fem, f)
    for f, p in src.items():
        n = en_name(f)
        if n:
            shutil.copy(p, os.path.join(sdir, n))
    i = os.path.join(DIST, "Data", "Interface")
    shutil.copy(os.path.join(i, "translate_uk.txt"), os.path.join(idir, "translate_en.txt"))
    for ext in ("gfx", "swf"):
        shutil.copy(os.path.join(i, "fonts_uk." + ext), os.path.join(idir, "fonts_en." + ext))
    fc = open(os.path.join(i, "fontconfig_uk.txt"), encoding="utf-8").read().replace('"fonts_uk"', '"fonts_en"')
    open(os.path.join(idir, "fontconfig_en.txt"), "w", encoding="utf-8", newline="").write(fc)
    n = sum(len(fs) for _, _, fs in os.walk(root))
    print(variant, n, "files ->", root)


if __name__ == "__main__":
    build("hero", False)
    build("heroine", True)
