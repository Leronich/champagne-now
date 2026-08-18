"""
scripts/sync_lang_switch.py
Приводит переключатель языка в мобильном меню к тому, что стоит в шапке.

Зачем
-----
Переключателей на странице два: .lang в шапке и .nav-overlay-lang в
полноэкранном меню. Первый чинит fix_hreflang.py, второй не чинил никто, и
18.08.2026 они разошлись на 22 страницах:

  * 4 юридические страницы (fr/legal/*) — в меню «EN · FR» лежит простым
    текстом без ссылки. С телефона уйти на английскую версию нельзя вообще:
    шапка на узком экране скрыта, а меню предлагает надпись, а не ссылку;
  * 16 хабов — build_hubs.py подставлял в оверлей весь блок вместе с
    обёрткой <div class="lang">, отчего получалось div внутри div. Стили
    .nav-overlay-lang до содержимого достают, так что видно правильно, но
    лишняя обёртка в разметке — след ошибки, а не замысел;
  * 2 новые статьи — написаны до того, как появилась языковая пара.

Правило простое: меню повторяет шапку. Шапка знает свою пару — её ведёт
fix_hreflang.py по таблице соответствий, а не по догадке о слаге.

    python scripts/sync_lang_switch.py --dry-run
    python scripts/sync_lang_switch.py
"""

import argparse
import re
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent

RE_LANG = re.compile(r'<div class="lang">(.*?)</div>\s*(?:\n|$)', re.S)
RE_OVERLAY = re.compile(r'(<div class="nav-overlay-lang">)(.*?)(</div>)', re.S)
# Обёртка, случайно попавшая внутрь оверлея на хабах.
RE_IMBRIQUE = re.compile(r'^\s*<div class="lang">(.*)</div>\s*$', re.S)


def contenu_shapka(html: str) -> str | None:
    m = RE_LANG.search(html)
    return m.group(1).strip() if m else None


def transformer(html: str) -> tuple:
    """Возвращает (новый html, что изменилось или '')."""
    voulu = contenu_shapka(html)
    if voulu is None:
        return html, ""                      # шапки нет — нечего копировать
    m = RE_OVERLAY.search(html)
    if not m:
        return html, ""                      # меню нет — нечего чинить

    actuel = m.group(2).strip()
    imbrique = RE_IMBRIQUE.match(actuel)
    if imbrique:
        actuel = imbrique.group(1).strip()   # снимаем лишнюю обёртку
    if actuel == voulu:
        return html, ""

    html = html[:m.start()] + m.group(1) + voulu + m.group(3) + html[m.end():]
    return html, f"{actuel or '(пусто)'} -> {voulu}"


def pages():
    for p in sorted(RACINE.rglob("*.html")):
        if ".wrangler" not in p.parts:
            yield p


def main() -> int:
    ap = argparse.ArgumentParser(description="Синхронизация переключателя языка")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    faites = []
    for path in pages():
        avant = path.read_text(encoding="utf-8", errors="replace")
        apres, quoi = transformer(avant)
        if not quoi:
            continue
        # Страховка: правка точечная, объём файла меняться почти не должен.
        if abs(len(apres) - len(avant)) > 200:
            print(f"ПРОПУЩЕНО {path.relative_to(RACINE)}: правка слишком большая")
            continue
        faites.append((str(path.relative_to(RACINE)).replace("\\", "/"), quoi))
        if not args.dry_run:
            path.write_text(apres, encoding="utf-8")

    print(f"страниц синхронизировано: {len(faites)}")
    for nom, quoi in faites:
        print(f"  {nom}\n     {quoi}")
    if args.dry_run:
        print("\n--dry-run: ничего не записано.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
