"""
scripts/add_mobile_menu.py
Гамбургер и полноэкранное меню на все страницы.

Зачем
-----
На узком экране прятались и .nav-links, и .nav-right — в шапке оставался один
логотип. С телефона попасть в раздел было нельзя вообще: только по ссылкам
внутри текста и через подвал. Это дыра в навигации, а не косметика.

Что вставляется
---------------
  * кнопка .nav-burger в <nav> (видна только до 640px);
  * оверлей #navOverlay перед </body>;
  * подключение /static/nav.js.

Ссылки в оверлее ведут туда, что существует на диске. Переключатель языка
берётся из собственного блока .lang страницы: он уже указывает на её пару, и
подставлять вместо него общий /fr/ нельзя — французской главной нет, а
объявлять несуществующие адреса мы только что закончили.

    python scripts/add_mobile_menu.py --dry-run
    python scripts/add_mobile_menu.py
"""

import argparse
import re
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
MARQUEUR = "navOverlay"

# Разделы, у которых есть хаб на обоих языках.
LIENS = [
    ("terroir",            "The Region",  "La Région"),
    ("wine-styles",        "The Wine",    "Le Vin"),
    ("history",            "History",     "Histoire"),
    ("houses",             "Houses",      "Maisons"),
    ("visit",              "Visit",       "Visiter"),
    ("in-the-cellar",      "In the Cellar", "En Cave"),
    ("food-and-champagne", "Food & Champagne", "Accords"),
    ("journal",            "Journal",     "Journal"),
]

# Квиз существует только по-английски: /fr/quiz/ нет. Французские страницы
# ведут туда же — это лучше, чем ссылка в никуда.
QUIZ = "/en/quiz/"

RE_LANG = re.compile(r'<div class="lang">(.*?)</div>', re.S)
RE_NAV_FIN = re.compile(r"(</nav>)")
BURGER = ('  <button class="nav-burger" type="button" aria-label="Menu" '
          'aria-controls="navOverlay" aria-expanded="false">&#9776;</button>\n')


def overlay(langue: str, lang_bloc: str) -> str:
    liens = "\n".join(
        f'    <a href="/{langue}/{slug}/">{en if langue == "en" else fr}</a>'
        for slug, en, fr in LIENS)
    ferme = "Fermer" if langue == "fr" else "Close"
    return (
        f'<div class="nav-overlay" id="navOverlay">\n'
        f'  <button class="nav-overlay-close" type="button" aria-label="{ferme}">&#10005;</button>\n'
        f'  <nav class="nav-overlay-links" aria-label="{"Menu" if langue == "en" else "Menu"}">\n'
        f'{liens}\n'
        f'    <a href="{QUIZ}">Quiz</a>\n'
        f'    <div class="nav-overlay-lang">{lang_bloc}</div>\n'
        f'  </nav>\n'
        f'</div>\n')


def transformer(html: str, langue: str) -> tuple:
    if MARQUEUR in html:
        return html, ""

    m = RE_LANG.search(html)
    if m:
        # Пара берётся у самой страницы: она знает свою вторую версию.
        lang_bloc = m.group(1).strip()
    else:
        lang_bloc = "<b>EN</b>" if langue == "en" else "<b>FR</b>"

    if "</nav>" not in html:
        return html, "нет <nav>"
    html = RE_NAV_FIN.sub(BURGER + r"\1", html, count=1)

    if "</body>" not in html:
        return html, "нет </body>"
    html = html.replace("</body>", overlay(langue, lang_bloc) + "</body>", 1)

    if "static/nav.js" not in html:
        html = html.replace('<script defer src="/static/consent.js"></script>',
                            '<script defer src="/static/nav.js"></script>\n'
                            '<script defer src="/static/consent.js"></script>', 1)
        if "static/nav.js" not in html:      # страницы без consent.js
            html = html.replace("</body>",
                                '<script defer src="/static/nav.js"></script>\n</body>', 1)
    return html, ""


def pages():
    for p in sorted(RACINE.rglob("*.html")):
        if ".wrangler" in p.parts:
            continue
        rel = str(p.relative_to(RACINE)).replace("\\", "/")
        yield p, ("fr" if rel.startswith("fr/") else "en")


def main() -> int:
    ap = argparse.ArgumentParser(description="Мобильное меню на все страницы")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    faites, deja, soucis = 0, 0, []
    for path, langue in pages():
        avant = path.read_text(encoding="utf-8", errors="replace")
        apres, souci = transformer(avant, langue)
        if souci:
            soucis.append((str(path.relative_to(RACINE)), souci)); continue
        if apres == avant:
            deja += 1; continue
        faites += 1
        if not args.dry_run:
            path.write_text(apres, encoding="utf-8")

    print(f"страниц изменено: {faites} | уже были: {deja}")
    if soucis:
        print(f"пропущено: {len(soucis)}")
        for nom, s in soucis:
            print(f"  {nom}: {s}")
    if args.dry_run:
        print("\n--dry-run: ничего не записано.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
