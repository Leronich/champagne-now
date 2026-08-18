"""
scripts/fix_lang_switcher.py
Переключатель EN/FR: ссылка ведёт на существующую пару или её нет вовсе.

Что было сломано
----------------
На главной и на /en/contact/ переключатель выглядел так:

    <div class="lang"><b>EN</b> · FR</div>

«FR» — простой текст, не ссылка. Клик не делал ничего. Именно это и было
видно пользователю: главная — самая посещаемая страница сайта, и именно на
ней переключатель не работал. Остальные 64 английские страницы ссылку имели
и имеют верную; их этот скрипт не трогает.

Почему НЕ «тот же путь + /fr/»
------------------------------
Напрашивающееся правило «en/X/ → fr/X/, иначе /fr/» на этом сайте ломает
больше, чем чинит. Французские слаги переведены, а не скопированы:

    en/terroir/montagne-de-reims/   ->  fr/terroir/montagne-de-reims-fr/
    en/visit/champagne-cellar-tours/ -> fr/visit/visite-caves-champagne-fr/
    en/food-and-champagne/champagne-cheese/ -> fr/.../champagne-fromage-fr/

Совпадение пути есть только у 11 адресов из 67 — это хабы и служебные
страницы. Остальные 56 правило отправило бы на /fr/, а /fr/ отдаёт 404:
французской главной не существует. То есть больше половины английского
сайта уводило бы с рабочей ссылки на страницу «не найдено».

Поэтому пара берётся из того, что проверяемо:
  1. hreflang самой страницы — его ведёт fix_hreflang.py по таблице
     соответствий, и он уже сверен с диском;
  2. если hreflang нет — совпадение пути, но ТОЛЬКО когда файл существует
     (так чинится /en/contact/ ↔ /fr/contact/);
  3. если пары нет — ссылки нет. Страница показывает <b>EN</b> без «FR».
     Обещать перевод, которого нет, хуже, чем не обещать: 14.08.2026
     несуществующие адреса, объявленные сайтом, уже стоили отчёта GSC
     «копия, канонический вариант не выбран» на 33 URL.

Оба переключателя — в шапке (.lang) и в мобильном меню (.nav-overlay-lang) —
приводятся к одному значению.

    python scripts/fix_lang_switcher.py --dry-run
    python scripts/fix_lang_switcher.py
"""

import argparse
import re
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
BASE = "https://champagne.now"

# Главная и 404 — не переводы друг друга, а служебные страницы, и пары в
# смысле hreflang у них нет. Французской главной не существует: /fr/ отдаёт
# 404. Поэтому переключатель здесь ведёт не на «перевод», а на французскую
# точку входа — тот же адрес, что уже стоял в 404.html. Заменить на другой
# раздел можно здесь, одной строкой; настоящее решение — сделать /fr/.
ENTREE_FR = "/fr/journal/"
UTILITAIRES = {"index.html", "404.html"}

RE_CANONICAL = re.compile(r'<link rel="canonical" href="([^"]+)"')
RE_ALT = re.compile(r'<link rel="alternate" hreflang="([a-z]{2})" href="([^"]+)"')
RE_LANG = re.compile(r'(<div class="lang">)(.*?)(</div>)', re.S)
RE_OVERLAY = re.compile(r'(<div class="nav-overlay-lang">)(.*?)(</div>)', re.S)


def chemin_de(url: str) -> str:
    """https://champagne.now/en/visit/x/ -> /en/visit/x/"""
    return url[len(BASE):] if url.startswith(BASE) else url


def existe(chemin: str) -> bool:
    return (RACINE / chemin.strip("/") / "index.html").exists()


def paire(path: Path, html: str, langue: str) -> str | None:
    """Адрес страницы на другом языке, или None если её нет."""
    autre = "fr" if langue == "en" else "en"

    nom = str(path.relative_to(RACINE)).replace("\\", "/")
    if nom in UTILITAIRES:
        return ENTREE_FR if existe(ENTREE_FR) else None

    # 1. hreflang — уже выверенная таблица соответствий.
    for lg, href in RE_ALT.findall(html):
        if lg == autre:
            c = chemin_de(href)
            if existe(c):
                return c

    # 2. Совпадение пути — только если файл действительно лежит.
    m = RE_CANONICAL.search(html)
    if m:
        c = chemin_de(m.group(1))
        if c.startswith(f"/{langue}/"):
            miroir = f"/{autre}/" + c[len(langue) + 2:]
            if existe(miroir):
                return miroir
    return None


def bloc(langue: str, cible: str | None) -> str:
    """Содержимое переключателя: активный язык жирным, другой — ссылкой."""
    if langue == "en":
        return f'<b>EN</b> · <a href="{cible}">FR</a>' if cible else "<b>EN</b>"
    return f'<a href="{cible}">EN</a> · <b>FR</b>' if cible else "<b>FR</b>"


def transformer(path: Path, html: str, langue: str) -> tuple:
    voulu = bloc(langue, paire(path, html, langue))
    change = []
    for regex, nom in ((RE_LANG, "шапка"), (RE_OVERLAY, "меню")):
        m = regex.search(html)
        if not m:
            continue
        if m.group(2).strip() == voulu:
            continue
        html = html[:m.start()] + m.group(1) + voulu + m.group(3) + html[m.end():]
        change.append(f"{nom}: {m.group(2).strip()} -> {voulu}")
    return html, change


def pages():
    """Страницы обоих языков плюс корневые (главная, 404) — на них
    переключатель тоже есть, и именно там он и не работал."""
    for p in sorted(RACINE.rglob("*.html")):
        if ".wrangler" in p.parts:
            continue
        rel = str(p.relative_to(RACINE)).replace("\\", "/")
        if rel.startswith("fr/"):
            yield p, "fr"
        else:
            yield p, "en"


def main() -> int:
    ap = argparse.ArgumentParser(description="Переключатель EN/FR по реальным парам")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    faites, sans_paire = [], []
    for path, langue in pages():
        avant = path.read_text(encoding="utf-8", errors="replace")
        if '<div class="lang">' not in avant:
            continue
        apres, change = transformer(path, avant, langue)
        nom = str(path.relative_to(RACINE)).replace("\\", "/")
        if paire(path, avant, langue) is None:
            sans_paire.append(nom)
        if not change:
            continue
        if abs(len(apres) - len(avant)) > 300:
            print(f"ПРОПУЩЕНО {nom}: правка неожиданно большая")
            continue
        faites.append((nom, change))
        if not args.dry_run:
            path.write_text(apres, encoding="utf-8")

    print(f"страниц исправлено: {len(faites)}")
    for nom, change in faites:
        print(f"  {nom}")
        for c in change:
            print(f"     {c}")
    print(f"\nбез пары на другом языке (ссылка не ставится): {len(sans_paire)}")
    for nom in sans_paire:
        print(f"  {nom}")
    if args.dry_run:
        print("\n--dry-run: ничего не записано.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
