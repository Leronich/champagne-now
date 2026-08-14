"""
scripts/add_hero_illustrations.py
Ставит сгенерированные баннеры фоном в шапки статей — только там, где можно.

Баннеры нарисованы Ideogram (scripts/generate_banners.py) и лежат в
static/banners/. Раздают их Cloudflare Pages вместе с сайтом.

Где НЕЛЬЗЯ и почему
-------------------
vocabulaire/champagne.py задаёт для каждого типа страницы, допустима ли
генерация. Для house_profile и visit там стоит `fallback_to_ideogram: False`
и `fallback_strategy: "publish_without_image"` — с комментарием, что здания
реальных домов генерировать нельзя. Правило разумное: нарисованный фасад
Veuve Clicquot на странице Veuve Clicquot читается как фотография этого дома
и говорит неправду о том, как место выглядит. Лучше без картинки.

Поэтому banner-houses.jpg и banner-visit.jpg не используются, хотя и
сгенерированы. Остальные пять — используются, с видимой пометкой
«Illustration», которой требует ILLUSTRATION_LABEL того же словаря.

    python scripts/add_hero_illustrations.py --dry-run
    python scripts/add_hero_illustrations.py
"""

import argparse
import re
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
BANNIERES = RACINE / "static" / "banners"

MARQUEUR = "art-hero--illus"

# раздел -> (файл баннера, метка en, метка fr)
AUTORISES = {
    "terroir":            ("banner-terroir.jpg",            "Illustration", "Illustration"),
    "wine-styles":        ("banner-wine-styles.jpg",        "Illustration", "Illustration"),
    "in-the-cellar":      ("banner-in-the-cellar.jpg",      "Illustration", "Illustration"),
    "history":            ("banner-history.jpg",            "Illustration", "Illustration historique"),
    "food-and-champagne": ("banner-food-and-champagne.jpg", "Illustration", "Illustration"),
}

# Сгенерированы, но не публикуются — см. докстринг.
INTERDITS = {
    "houses": "house_profile: генерация зданий реальных домов запрещена словарём",
    "visit":  "visit: fallback_to_ideogram=False, publish_without_image",
}

# Шапка встречается в двух видах: обычная и с модификатором раздела
# (`art-hero art-hero--terroir fade`). Первая редакция мотива знала только
# первый вид и молча пропускала весь terroir — все 16 страниц. Совпадение по
# закрывающей кавычке, а не по фиксированному набору классов.
RE_HERO = re.compile(r'<header class="(art-hero[^"]*)"')


def transformer(html: str, section: str, langue: str) -> tuple:
    if MARQUEUR in html:
        return html, ""
    fichier, label_en, label_fr = AUTORISES[section]
    if not (BANNIERES / fichier).exists():
        return html, f"нет файла {fichier}"

    label = label_fr if langue == "fr" else label_en
    m = RE_HERO.search(html)
    if not m:
        return html, "не найдена шапка .art-hero"

    ouvrant = (f'<header class="{m.group(1)} {MARQUEUR}" '
               f'style="--illus:url(/static/banners/{fichier})"')
    html = html[:m.start()] + ouvrant + html[m.end():]

    # Пометка ставится последним ребёнком шапки, перед её закрытием.
    fin = html.find("</header>", m.start())
    if fin == -1:
        return html, "не найдено закрытие шапки"
    html = html[:fin] + f'  <span class="illus-mark">{label}</span>\n' + html[fin:]
    return html, ""


def pages():
    for langue in ("en", "fr"):
        for section in AUTORISES:
            for p in sorted((RACINE / langue / section).glob("*/index.html")):
                yield p, section, langue


def main() -> int:
    parser = argparse.ArgumentParser(description="Баннеры в шапки статей")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    faites, deja, soucis = {}, 0, []
    for path, section, langue in pages():
        avant = path.read_text(encoding="utf-8", errors="replace")
        apres, souci = transformer(avant, section, langue)
        if souci:
            soucis.append((str(path.relative_to(RACINE)), souci)); continue
        if apres == avant:
            deja += 1; continue
        faites[section] = faites.get(section, 0) + 1
        if not args.dry_run:
            path.write_text(apres, encoding="utf-8")

    total = sum(faites.values())
    print(f"страниц с иллюстрацией: {total} | уже были: {deja}")
    for section, n in sorted(faites.items()):
        print(f"  {n:>3}  {section}")
    print("\nне публикуются, хотя баннеры сгенерированы:")
    for section, motif in INTERDITS.items():
        print(f"       {section}: {motif}")
    if soucis:
        print(f"\nпропущено с замечанием: {len(soucis)}")
        for nom, souci in soucis[:8]:
            print(f"  {nom}: {souci}")
    if args.dry_run:
        print("\n--dry-run: ничего не записано.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
