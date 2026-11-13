"""
Повний випуск: ігрові файли -> ZIP (Nexus/Vortex/вручну) -> EXE-інсталятор.
  python build_release.py [--no-draft]
Результат у D:\\Starfield\\dist.
"""
import datetime as dt, os, subprocess, sys, zipfile

BOT = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(BOT)
DIST = os.path.join(ROOT, "dist")
ISCC = os.path.expandvars(r"%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe")
VERSION = "0.9." + dt.date.today().strftime("%Y%m%d")

README = """Starfield — українська локалізація, версія {v}

АВТОМАТИЧНО: запустіть Starfield_UA_Setup_{v}.exe.

ВРУЧНУ:
1. Скопіюйте папку Data з цього архіву в  Документи\\My Games\\Starfield\\
   Для ГЕРОЇНІ (жіночий персонаж): потім скопіюйте файли з Female\\Strings у Data\\Strings із заміною.
2. Відкрийте (або створіть) файл  Документи\\My Games\\Starfield\\StarfieldCustom.ini  і додайте:

[General]
sLanguage=uk

[Archive]
bInvalidateOlderFiles=1
sResourceDataDirsFinal=

ВИДАЛЕННЯ: видаліть файли *_uk.* з Data\\Strings і Data\\Interface та рядок sLanguage=uk.

Озвучення лишається англійським.

ПОДЯКИ:
- українській спільноті перекладачів Starfield на Crowdin — дякуємо всім, хто долучився до перекладу!
  (людський переклад ~37% тексту, глосарій і пам'ять перекладів, 2023-2025);
- решту тексту (~63%) і DLC допрацьовано ШІ (Claude) з глосарієм спільноти; можливі неточності;
- VladNeko та авторам «Ukrainian localization of Starfield» (Nexus 8307) — шрифти з кирилицею
  та перша версія перекладу, на основі якої допрацьовано решту тексту.
"""


def main():
    subprocess.run([sys.executable, "-I", os.path.join(BOT, "build_game.py"), *sys.argv[1:]], check=True)
    zpath = os.path.join(DIST, f"Starfield_UA_{VERSION}.zip")
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for base, _, files in os.walk(os.path.join(DIST, "Data")):
            for f in files:
                full = os.path.join(base, f)
                z.write(full, os.path.relpath(full, DIST))
        for base, _, files in os.walk(os.path.join(DIST, "Female")):
            for f in files:
                full = os.path.join(base, f)
                z.write(full, os.path.relpath(full, DIST))
        z.writestr("README_UA.txt", README.format(v=VERSION).replace("\n", "\r\n").encode("utf-8-sig"))
    print("ZIP:", zpath)
    subprocess.run([ISCC, "/Q", f"/DAppVersion={VERSION}", f"/DSrc={os.path.join(DIST, 'Data')}",
                    f"/DOut={DIST}", f"/DFem={os.path.join(DIST, 'Female')}", os.path.join(BOT, "installer.iss")], check=True)
    print("EXE:", os.path.join(DIST, f"Starfield_UA_Setup_{VERSION}.exe"))


if __name__ == "__main__":
    main()
