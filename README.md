# Starfield — українська локалізація

Неофіційний безкоштовний український переклад Starfield: діалоги, завдання, журнал, предмети, інтерфейс, книги й записки, а також офіційні доповнення та Creations від Bethesda. Озвучення лишається англійським.

**[⬇ Завантажити останню версію](https://github.com/livonianlabs/starfield-ukrainian/releases)** — `Starfield-UA-<версія>-setup.exe` (інсталятор) або `.zip` (вручну).

Посібник у Steam: https://steamcommunity.com/sharedfiles/filedetails/?id=3838134802

> Статус: **бета (0.9)** — увесь текст перекладено, триває вичитка в грі. Помилки — в [Issues](../../issues).

## Особливості

- Понад 2 млн слів тексту гри українською.
- **Герой або героїня** — дві версії тексту: звертання NPC, репліки вашого персонажа й журнал завдань у правильному роді. Інсталятор визначає стать за вашим останнім збереженням (можна змінити вручну).
- Доповнення та Creations від Bethesda, текст з оновлень гри.
- Шрифти з кирилицею, включно з Ґ ґ.
- Встановлення в один клік і повернення до оригіналу; файли самої гри не змінюються.

## Як зроблено переклад

| Джерело | Частка | Обсяг |
|---|---|---|
| Людський переклад української спільноти на Crowdin (2023–2025) | ~37 % | ≈780 тис. слів |
| Допрацьовано ШІ (Claude) з глосарієм (~2 900 термінів) і пам'яттю перекладів спільноти | ~63 % | ≈1,3 млн слів |

Можливі неточності й незграбні фрази — повідомляйте, будемо виправляти.

## Встановлення (Steam)

1. Закрийте гру.
2. Запустіть `Starfield-UA-<версія>-setup.exe`, перевірте вибір «Герой / Героїня» → «Встановити».
3. Запустіть гру.

**Вручну (ZIP):** скопіюйте теку `Data` в `Документи\My Games\Starfield\` (для героїні — потім файли з `Female\Strings` у `Data\Strings` із заміною) і додайте в `Документи\My Games\Starfield\StarfieldCustom.ini`:

```ini
[General]
sLanguage=uk

[Archive]
bInvalidateOlderFiles=1
sResourceDataDirsFinal=
```

**Видалення:** Пуск → «Starfield UA — повернути оригінал (видалити переклад)» або «Програми та компоненти». Відновлюються попередні налаштування мови й файли.

## Інструменти (`tools/`)

Python-скрипти, якими зібрано переклад: читання/запис рядків Bethesda (`.STRINGS/.DLSTRINGS/.ILSTRINGS`) і BA2, переклад залишку через Claude Code (`translate_bot.py`, `dlc_bot.py`, `iface_bot.py` — нові ключі інтерфейсу з поточної версії гри), визначення мовця з ESM для жіночої версії (`esm_speakers.py`, `gender_bot.py`), виправлення артефактів (`fix_junk.py`), збирання гри й інсталятора Inno Setup (`build_game.py`, `build_release.py`, `installer.iss`).

## Подяки

- Українській спільноті перекладачів Starfield на Crowdin — дякуємо всім, хто долучився до перекладу! Людський переклад, глосарій і пам'ять перекладів (2023–2025).
- VladNeko та авторам «Ukrainian localization of Starfield» (Nexus Mods 8307) — шрифти з кирилицею та перша версія перекладу.

## Trademarks

Starfield, Bethesda and related marks are trademarks of Bethesda Softworks LLC / ZeniMax Media Inc., a Microsoft company. This is an unofficial, non-commercial fan translation, not affiliated with or endorsed by them. Game text belongs to its owners; the translation is distributed free of charge.

## License

Code in `tools/` — [MIT](LICENSE) © 2026 Livonian Labs.
