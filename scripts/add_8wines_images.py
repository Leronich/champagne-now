"""
scripts/add_8wines_images.py
Фотография товара над каждой партнёрской ссылкой 8wines.

8wines разрешили использовать свои изображения при условии, что каждое
ведёт обратно на 8wines по партнёрской ссылке. Поэтому картинка кладётся
ВНУТРЬ существующего <a>, а не рядом: отдельная картинка без ссылки условие
нарушала бы, и её пришлось бы снимать.

Какой размер берём
------------------
На странице товара лежат два варианта одного кадра: og:image 700×700 весом
280–430 КБ и выкладочный 240×300 весом 30–38 КБ. Показываем мы его в 180 px,
поэтому берём второй. Разница на странице Dom Pérignon — 1,5 МБ против
137 КБ за четыре бутылки; при том что виден результат одинаково.

Luminous 2015
-------------
Пятая ссылка ведёт на товар, которого у 8wines больше нет: страница отдаёт
404, а её og:image — это логотип магазина, а не бутылка. Поиск по каталогу
Luminous не находит вовсе. Картинку такой ссылке не ставим: подставить
логотип вместо бутылки значило бы показать читателю товар, которого нет, и
увести его на 404. Сама ссылка оставлена как была — удалять её здесь, внутри
задачи про картинки, мы не стали.

    python scripts/add_8wines_images.py --dry-run
    python scripts/add_8wines_images.py
"""

import argparse
import re
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
CDN = ("https://cdn.8wines.com/media/catalog/product/cache/"
       "85afc4327457cecebbcfbf5e81df27a7/c/h/")

# слаг товара -> файл изображения. Только товары, отдающие 200 и имеющие
# собственный кадр; проверено браузером 19.08.2026.
IMAGES = {
    "champagne-dom-perignon-rose-2009":        "champagne-dom-perignon-rose-2009_1.png",
    "champagne-dom-perignon-2013":             "champagne-dom-perignon-2013.png",
    "champagne-dom-perignon-2015":             "champagne-dom-perignon-2015.png",
    "champagne-krug-grande-cuvee-edition-173": "champagne-krug-grande-cuvee-edition-173.png",
}

# <a href="…8wines.com/wines/{слаг}?…" class="aff-link" …>текст</a>
RE_LIEN = re.compile(
    r'<a href="(https://8wines\.com/wines/([a-z0-9-]+)[^"]*)" class="aff-link"'
    r'([^>]*)>(.*?)</a>', re.S)


def alt_de(texte: str) -> str:
    """alt = название товара без стрелки. Стрелка — украшение ссылки, а не
    часть имени бутылки, и в озвучке экранного диктора ей делать нечего."""
    return re.sub(r"\s*&rarr;\s*$", "", texte).strip()


def transformer(html: str) -> tuple:
    faits, sautes = [], []

    def remplacer(m):
        href, slug, attrs, texte = m.groups()
        if "aff-product-img" in m.group(0):
            return m.group(0)                      # уже с картинкой
        fichier = IMAGES.get(slug)
        if not fichier:
            sautes.append(slug)
            return m.group(0)                      # товара нет — ссылку не трогаем
        alt = alt_de(texte)
        faits.append(slug)
        return (f'<a href="{href}"{attrs}>\n'
                f'      <img src="{CDN}{fichier}" alt="{alt}" loading="lazy" class="aff-product-img">\n'
                f'      <span class="aff-link">{texte}</span>\n'
                f'    </a>')

    return RE_LIEN.sub(remplacer, html), faits, sautes


def main() -> int:
    ap = argparse.ArgumentParser(description="Картинки товаров в блоки 8wines")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    total_faits, total_sautes, pages = 0, [], 0
    for p in sorted(RACINE.rglob("*.html")):
        if ".wrangler" in p.parts:
            continue
        avant = p.read_text(encoding="utf-8", errors="replace")
        if "8wines.com/wines/" not in avant:
            continue
        apres, faits, sautes = transformer(avant)
        nom = str(p.relative_to(RACINE)).replace("\\", "/")
        if not faits:
            print(f"  {nom}: без изменений")
            continue
        # Страховка: правка только добавляет разметку, ничего не удаляя.
        if len(apres) < len(avant):
            print(f"ПРОПУЩЕНО {nom}: файл стал короче — проверьте регулярку")
            continue
        pages += 1
        total_faits += len(faits)
        total_sautes += sautes
        print(f"  {nom}: картинок добавлено {len(faits)}"
              + (f", пропущено {len(sautes)}" if sautes else ""))
        for s in faits:
            print(f"       + {s}")
        for s in sautes:
            print(f"       – {s}  (нет кадра: товар недоступен)")
        if not args.dry_run:
            p.write_text(apres, encoding="utf-8")

    print(f"\nстраниц: {pages} | картинок: {total_faits} | без картинки: {len(total_sautes)}")
    if args.dry_run:
        print("--dry-run: ничего не записано.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
