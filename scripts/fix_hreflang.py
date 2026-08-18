"""
scripts/fix_hreflang.py
Приводит hreflang и переключатель языка к тому, что реально лежит на диске.

Что было сломано
----------------
hreflang собирался механически как «{английский-слаг}-fr», тогда как реальные
французские слаги переведены: /en/visit/harvest-season/ объявлял
/fr/visit/harvest-season-fr/, а страница называется
/fr/visit/vendange-champagne-fr/. Из 54 английских статей 24 указывали в
пустоту, из 54 французских — 18.

Цена оказалась не в hreflang. Cloudflare Pages отдаёт на неизвестный путь
главную страницу с кодом 200, а не 404. Значит каждый несуществующий адрес,
объявленный сайтом, становился ещё одной копией главной. Google нашёл 33 такие
копии и завёл на них отчёт «Страница является копией, канонический вариант не
выбран пользователем» — канонического у главной действительно нет.

Как восстановлены пары
----------------------
36 пар взяты обратным ходом: французские страницы в большинстве своём ссылались
на английские верно, и эту связь достаточно перевернуть.

Оставшиеся 18 сопоставлены по смыслу и перечислены ниже явно. Каждая
однозначна — в своём разделе ровно один кандидат с каждой стороны, и перевод
читается прямо: fromage/cheese, poulet-frit/fried-chicken, vendange/harvest,
hebergement/stay, recoltants-maisons/growers-vs-houses. Списком, а не эвристикой:
угадывание здесь один раз уже обошлось в 42 фантомных адреса.

    python scripts/fix_hreflang.py --dry-run
    python scripts/fix_hreflang.py
"""

import argparse
import re
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
BASE = "https://champagne.now"

# Пары, не восстановимые автоматически. en-слаг -> fr-слаг, внутри раздела.
MANUELLES = {
    "food-and-champagne": {
        "champagne-breakfast":     "champagne-brunch-fr",
        "champagne-cheese":        "champagne-fromage-fr",
        "champagne-fried-chicken": "champagne-poulet-frit-fr",
    },
    "history": {
        "champagne-wwii":          "champagne-guerre-fr",
        "dom-perignon-history":    "dom-perignon-histoire-fr",
        "growers-vs-houses":       "recoltants-maisons-fr",
        "veuve-clicquot-history":  "veuve-clicquot-histoire-fr",
    },
    "in-the-cellar": {
        "second-fermentation":     "deuxieme-fermentation-fr",
    },
    "terroir": {
        "aube-les-riceys":         "aube-champagne-fr",
        "grand-cru-villages":      "grands-crus-fr",
        "le-mesnil-sur-oger":      "mesnil-sur-oger-fr",
    },
    "visit": {
        "champagne-cellar-tours":  "visite-caves-champagne-fr",
        "champagne-stay":          "hebergement-champagne-fr",
        "day-trip-paris":          "excursion-paris-fr",
        "harvest-season":          "vendange-champagne-fr",
        "moet-cave-tour":          "visite-moet-fr",
        "veuve-clicquot-tour":     "visite-veuve-clicquot-fr",
    },
    "wine-styles": {
        "demi-sec-champagne":      "demi-sec-fr",
        "extra-brut-zero-dosage":  "extra-brut-fr",
    },
}

RE_ALT = re.compile(r'[ \t]*<link rel="alternate" hreflang="[a-z]{2}" href="[^"]*"\s*/>\n?')
RE_LANG = re.compile(r'<div class="lang">.*?</div>', re.S)


def url(p: Path) -> str:
    return "/" + str(p.parent.relative_to(RACINE)).replace("\\", "/") + "/"


def existe() -> set:
    return {url(p) for p in RACINE.rglob("index.html") if ".wrangler" not in p.parts}


def construire_paires() -> tuple:
    """{en_url: fr_url}. Сперва обратным ходом, затем явным списком."""
    sur_disque = existe()
    paires, sources = {}, {}

    def cible(p, lg):
        h = p.read_text(encoding="utf-8", errors="replace")
        m = re.search(rf'hreflang="{lg}" href="{re.escape(BASE)}([^"]+)"', h)
        return m.group(1) if m else None

    for p in RACINE.glob("fr/*/*/index.html"):
        c = cible(p, "en")
        if c and c in sur_disque:
            paires[c] = url(p); sources[c] = "обратный ход"
    for p in RACINE.glob("en/*/*/index.html"):
        c = cible(p, "fr")
        u = url(p)
        if u not in paires and c and c in sur_disque:
            paires[u] = c; sources[u] = "прямая ссылка"

    for section, table in MANUELLES.items():
        for en_slug, fr_slug in table.items():
            en_u, fr_u = f"/en/{section}/{en_slug}/", f"/fr/{section}/{fr_slug}/"
            if en_u not in sur_disque or fr_u not in sur_disque:
                print(f"  ВНИМАНИЕ пара из списка не найдена: {en_u} ↔ {fr_u}", file=sys.stderr)
                continue
            paires[en_u] = fr_u; sources[en_u] = "список"
    return paires, sources


def bloc(en_u: str, fr_u: str) -> str:
    return (f'<link rel="alternate" hreflang="en" href="{BASE}{en_u}" />\n'
            f'<link rel="alternate" hreflang="fr" href="{BASE}{fr_u}" />\n')


def reecrire(path: Path, en_u: str, fr_u: str) -> tuple:
    html = path.read_text(encoding="utf-8", errors="replace")
    avant = html
    est_en = url(path) == en_u

    # Полный набор из двух записей — hreflang описывает группу, а не страницу.
    # Прежний файл ставил одну запись, указывающую на саму себя.
    html, n = RE_ALT.subn("", html)
    html = html.replace('<link rel="canonical"', bloc(en_u, fr_u) + '<link rel="canonical"', 1) \
        if '<link rel="canonical"' in html else html
    if '<link rel="alternate"' not in html:      # страницы без canonical
        html = html.replace("</head>", bloc(en_u, fr_u) + "</head>", 1)

    # Переключатель языка в шапке ведёт на ту же цель.
    autre = fr_u if est_en else en_u
    remplacement = (f'<div class="lang"><b>EN</b> · <a href="{fr_u}">FR</a></div>'
                    if est_en else
                    f'<div class="lang"><a href="{en_u}">EN</a> · <b>FR</b></div>')
    html = RE_LANG.sub(remplacement, html, count=1)
    return html, html != avant


def main() -> int:
    ap = argparse.ArgumentParser(description="Починка hreflang и переключателя языка")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    paires, sources = construire_paires()
    print(f"пар: {len(paires)}")
    for quoi in ("обратный ход", "прямая ссылка", "список"):
        print(f"  {sum(1 for s in sources.values() if s == quoi):>3}  {quoi}")

    sur_disque = existe()
    orphelins = [u for u in sur_disque
                 if re.match(r"^/(en|fr)/[a-z-]+/[a-z0-9-]+/$", u)
                 and u not in paires and u not in set(paires.values())]

    touchees = 0
    for en_u, fr_u in sorted(paires.items()):
        for u in (en_u, fr_u):
            p = RACINE / u.strip("/") / "index.html"
            html, change = reecrire(p, en_u, fr_u)
            if change:
                touchees += 1
                if not args.dry_run:
                    p.write_text(html, encoding="utf-8")

    print(f"\nстраниц изменено: {touchees}")
    if orphelins:
        print(f"без пары ({len(orphelins)}) — hreflang не ставится:")
        for u in sorted(orphelins): print("   ", u)
    if args.dry_run:
        print("\n--dry-run: ничего не записано.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
