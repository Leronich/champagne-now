"""
scripts/submit_photo_requests.py
Подаёт заявки на фотографии статей в kohexa-photo-index.

Обходит статьи в en/ и fr/, выводит для каждой subniche из словаря
vocabulaire/champagne.py и складывает заявку в demandes/champagnenow-{дата}.json.

    python scripts/submit_photo_requests.py --dry-run   # разбор без записи
    python scripts/submit_photo_requests.py             # подать заявку

Почему заявка одна на сюжет, а не по одной на язык
--------------------------------------------------
`used` в реестре — атрибут ФОТОГРАФИИ, а не ссылки на страницу. Две заявки на
один сюжет получили бы два разных кадра, и английская статья про Крюг
иллюстрировалась бы не тем же снимком, что французская. Поэтому заявка
подаётся на канонический (английский) slug, а французская страница читает тот
же request_id. Пары берутся из hreflang, а не из угадывания слагов.
Флаг --per-language переключает на поведение «каждому языку своё фото».

Долг по триггерам — до публикации, не после
-------------------------------------------
Подача заявки и выдача кандидатов сети не касаются: `choisir()` работает по
уже собранному фонду. Но лицензия Unsplash требует вызвать download_location
на каждый НОВЫЙ выбор, а обработка заявок этого не делает — она только
переводит фото в состояние reserved. Долг гасится отдельным запуском в
хранилище, и вот он тратит квоту.

Перед выкладкой страниц с фотографиями:

    cd D:\бизнес\домены\kohexa-photo-index
    python retrigger.py --vocab champagne              # посмотреть долг
    python retrigger.py --vocab champagne --run        # погасить

`--vocab champagne` берёт BUDGET_KEY из vocabulaire/champagne.py, то есть
списывает расход на champagnenow. Равнозначные формы — `--projet champagnenow`
или переменная окружения (в cmd: `set PHOTO_SOURCE=champagnenow`, в
PowerShell: `$env:PHOTO_SOURCE="champagnenow"`).

Без любой из них retrigger.py теперь останавливается с ошибкой и ничего не
тратит. До 14.08.2026 он вместо этого молча списывал расход на moncaviste —
таким был дефолт, — и первый прогон champagne.now ушёл на чужой счёт. Симптом
всплыл у mon-caviste как «почему-то не хватает фото»: искать причину пришлось
там, где её не было. Дефолт убран в общем компоненте (kohexa-photo-index,
engine/projet.py), а не только здесь: он повторился бы на каждом следующем
проекте реестра.

subniche — не косметика
-----------------------
Движок кладёт subniche и в page["slug"], и в page["title_hint"]; именно по нему
срабатывают geo_by_fragment и type_from. Поэтому в subniche добавляется ключ
субрегиона: сопоставление идёт подстрокой, и "le mesnil-sur-oger" из словаря
не совпало бы со слагом "le-mesnil-sur-oger" без нормализации.
"""

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from image_builder import (PHOTO_INDEX_ROOT, PROJECT, ROLES,  # noqa: E402
                           build_request, request_id, write_demande)

# Словарь живёт в хранилище — он общий с движком, дублировать его нельзя
sys.path.insert(0, str(PHOTO_INDEX_ROOT))
from vocabulaire.champagne import (CELLAR_TERMS, FOOD_TERMS,  # noqa: E402
                                   GEO_BY_FRAGMENT, GEO_TERMS, MAISONS,
                                   TYPE_FROM, TYPE_MARKERS, VISIT_TERMS,
                                   WINE_STYLES)

# Разделы со статьями. legal/contact/editorial/quiz — не статьи, фото не нужны.
ARTICLE_SECTIONS = (
    "houses", "terroir", "visit", "history",
    "in-the-cellar", "wine-styles", "food-and-champagne",
)

# Словарь терминов, из которого берётся тема раздела
SECTION_TERMS = {
    "terroir":            GEO_TERMS,
    "houses":             MAISONS,
    "wine-styles":        WINE_STYLES,
    "in-the-cellar":      CELLAR_TERMS,
    "history":            CELLAR_TERMS,
    "food-and-champagne": FOOD_TERMS,
    "visit":              VISIT_TERMS,
}

HREFLANG_FR = re.compile(r'hreflang="fr"\s+href="[^"]*?/fr/([^"]+?)/?"')


# ── СЛАГИ ───────────────────────────────────────────────────────────────────

def _norm(text: str) -> str:
    """К единому виду: нижний регистр, подчёркивания и пробелы → дефисы."""
    return re.sub(r"[\s_]+", "-", (text or "").strip().lower())


def region_fragment(text: str) -> str:
    """
    Субрегион, к которому относится текст, или "" если не опознан.

    Сравнение подстрочное, поэтому термины словаря нормализуются так же, как
    слаг: "le mesnil-sur-oger" → "le-mesnil-sur-oger".
    """
    hay = _norm(text)
    for fragment, terms in GEO_BY_FRAGMENT.items():
        if fragment in hay:
            return fragment
        for term in terms:
            normalized = _norm(term)
            if normalized and normalized in hay:
                return fragment
    return ""


# Слаги статей длиннее ключей словаря: ключ "brut" против слага
# "brut-champagne", "rose" против "rose-champagne". Отрезаем служебные части,
# иначе половина статей ушла бы с общим "champagne" при живой записи в словаре.
SLUG_AFFIXES = ("-champagne", "champagne-", "-zero-dosage", "-history",
                "-tour", "-guide", "-season")


def _slug_variants(slug: str) -> list:
    """Формы слага для поиска в словаре, от точной к урезанной."""
    variants = [slug, slug.replace("-", "_")]
    trimmed = slug
    for affix in SLUG_AFFIXES:
        if affix.startswith("-") and trimmed.endswith(affix):
            trimmed = trimmed[: -len(affix)]
        elif affix.endswith("-") and trimmed.startswith(affix):
            trimmed = trimmed[len(affix):]
    if trimmed != slug:
        variants += [trimmed, trimmed.replace("-", "_")]
    return variants


def vocab_entry(section: str, slug: str) -> list:
    """Термины словаря для слага статьи, если он там описан."""
    terms = SECTION_TERMS.get(section, {})
    for variant in _slug_variants(slug):
        if variant in terms:
            return terms[variant]
    return []


def detect_wine_type(slug: str) -> str:
    """
    Стиль по подсказкам TYPE_FROM — тем же способом, каким его определяет
    detecter_type() движка: ровно одно совпадение, иначе ничего.

    Неоднозначность здесь опаснее пустоты: type_force с чужим значением
    отправляет в бан маркеры ВСЕХ остальных типов и обнуляет вивьер.
    """
    hay = _norm(slug)
    found = [t for t, hints in TYPE_FROM.items()
             if any(_norm(h) in hay for h in hints)]
    if len(found) != 1:
        return None
    return found[0] if found[0] in TYPE_MARKERS else None


def derive(section: str, slug: str) -> dict:
    """
    subniche и wine_type для статьи.

    Возвращает также `note` — чем именно определилось, чтобы --dry-run
    показывал не только результат, но и на чём он основан.
    """
    entry = vocab_entry(section, slug)
    in_vocab = bool(entry)

    # Регион ищем сперва в самом слаге, затем в терминах словаря: для домов
    # место стоит в поисковой строке ("Bollinger Ay", "Ruinart Reims").
    fragment = region_fragment(slug) or region_fragment(" ".join(entry))

    subniche = slug
    if fragment and fragment not in slug:
        subniche = f"{slug} {fragment}"
    elif fragment:
        subniche = slug

    wine_type = detect_wine_type(slug)

    if fragment:
        note = f"регион: {fragment}"
    elif in_vocab:
        note = "тема из словаря, регион не назван"
    else:
        note = "НЕТ В СЛОВАРЕ — общий champagne"

    return {
        "subniche":  subniche,
        "wine_type": wine_type,
        "fragment":  fragment,
        "in_vocab":  in_vocab,
        "note":      note,
    }


# ── ОБХОД СТАТЕЙ ────────────────────────────────────────────────────────────

def collect_articles() -> tuple:
    """
    Английские статьи + их французские пары.

    Возвращает (articles, orphans_fr, broken_hreflang): статьи, французские
    страницы без английского оригинала и en-страницы, чей hreflang указывает
    на несуществующий файл.
    """
    articles = []
    paired_fr = set()
    broken = []

    for section in ARTICLE_SECTIONS:
        for path in sorted((REPO_ROOT / "en" / section).glob("*/index.html")):
            slug = path.parent.name
            html = path.read_text(encoding="utf-8", errors="replace")

            match = HREFLANG_FR.search(html)
            declared = match.group(1).strip("/") if match else ""

            # hreflang проверяется по диску, а не принимается на веру: на части
            # страниц он собран механически как "{слаг}-fr", тогда как реальный
            # французский слаг переведён. Доверие к нему дало бы неверную карту.
            fr_path = ""
            if declared:
                if (REPO_ROOT / "fr" / declared / "index.html").exists():
                    fr_path = declared
                    paired_fr.add(declared)
                else:
                    broken.append((f"en/{section}/{slug}", declared))

            articles.append({
                "section": section,
                "slug":    slug,
                "en":      f"en/{section}/{slug}",
                "fr":      fr_path,
                **derive(section, slug),
            })

    orphans = []
    for section in ARTICLE_SECTIONS:
        fr_dir = REPO_ROOT / "fr" / section
        if not fr_dir.exists():
            continue
        for path in sorted(fr_dir.glob("*/index.html")):
            rel = f"{section}/{path.parent.name}"
            if rel not in paired_fr:
                orphans.append(rel)

    return articles, orphans, broken


# ── ЗАЯВКА ──────────────────────────────────────────────────────────────────

def build_all(articles: list, batch: str, per_language: bool) -> list:
    requests = []
    for article in articles:
        targets = [article["slug"]]
        if per_language and article["fr"]:
            targets.append(article["fr"].split("/")[-1])

        for slug in targets:
            for role in ROLES:
                requests.append(build_request(
                    slug=slug,
                    role=role,
                    subniche=article["subniche"],
                    section=article["section"],
                    wine_type=article["wine_type"],
                    priority_batch=batch,
                ))
    return requests


def slug_map(articles: list) -> dict:
    """fr-путь → канонический slug, чтобы французские страницы нашли фото."""
    return {a["fr"]: a["slug"] for a in articles if a["fr"]}


# ── ВЫВОД ───────────────────────────────────────────────────────────────────

def report(articles: list, orphans: list, broken: list, requests: list) -> None:
    by_section = {}
    for article in articles:
        by_section.setdefault(article["section"], []).append(article)

    slug_w = max(len(a["slug"]) for a in articles)
    sub_w = max(len(a["subniche"]) for a in articles)

    for section in ARTICLE_SECTIONS:
        rows = by_section.get(section, [])
        if not rows:
            continue
        print(f"\n{section}  ({len(rows)})")
        for article in rows:
            wine = article["wine_type"] or "—"
            print(f"  {article['slug']:<{slug_w}}  {article['subniche']:<{sub_w}}  "
                  f"{wine:<16}  {article['note']}")

    # Предупреждаем только о статьях, у которых нет НИ записи в словаре,
    # НИ распознанного региона: с регионом отбор уже осмысленный.
    no_vocab = [a for a in articles if not a["in_vocab"] and not a["fragment"]]
    no_region = [a for a in articles if not a["fragment"]]
    no_fr = [a for a in articles if not a["fr"]]

    print("\n" + "=" * 78)
    print(f"статей: {len(articles)} | запросов: {len(requests)} "
          f"({len(ROLES)} роли на статью)")
    print(f"без региона: {len(no_region)} | без словаря и региона: {len(no_vocab)} | "
          f"без пары fr: {len(no_fr)}")
    print(f"битый hreflang: {len(broken)} | fr-страниц без пары: {len(orphans)}")

    if no_vocab:
        print("\nНет в словаре champagne.py — уйдут с общим 'champagne':")
        for article in no_vocab:
            print(f"  {article['section']}/{article['slug']}")
    if orphans:
        print("\nfr-страницы без английского оригинала:")
        for rel in orphans:
            print(f"  fr/{rel}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Заявки на фото статей в kohexa-photo-index")
    parser.add_argument("--dry-run", action="store_true",
                        help="разобрать и показать, ничего не записывая")
    parser.add_argument("--per-language", action="store_true",
                        help="отдельная заявка на каждый язык (разные кадры)")
    parser.add_argument("--batch", default="",
                        help="priority_batch, по умолчанию queue-{дата}")
    parser.add_argument("--date", default=date.today().isoformat(),
                        help="дата в имени файла заявки")
    args = parser.parse_args()

    if not PHOTO_INDEX_ROOT.exists():
        print(f"ОШИБКА: не найдено хранилище {PHOTO_INDEX_ROOT}", file=sys.stderr)
        return 1

    articles, orphans, broken = collect_articles()
    if not articles:
        print("ОШИБКА: не найдено ни одной статьи", file=sys.stderr)
        return 1

    batch = args.batch or f"queue-{args.date}"
    requests = build_all(articles, batch, args.per_language)
    report(articles, orphans, broken, requests)

    ids = [r["request_id"] for r in requests]
    if len(ids) != len(set(ids)):
        dupes = {i for i in ids if ids.count(i) > 1}
        print(f"\nОШИБКА: request_id не уникальны: {sorted(dupes)[:5]}", file=sys.stderr)
        return 1

    if args.dry_run:
        print("\n--dry-run: заявка не записана.")
        print(f"Записала бы: {PHOTO_INDEX_ROOT / 'demandes' / f'{PROJECT}-{args.date}.json'}")
        print("\nПример запроса:")
        print(json.dumps(requests[0], ensure_ascii=False, indent=2))
        return 0

    path = write_demande(requests, args.date)
    map_path = REPO_ROOT / "scripts" / "photo_slug_map.json"
    map_path.write_text(
        json.dumps(slug_map(articles), ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8")

    print(f"\nЗаявка записана: {path}")
    print(f"Карта fr→en:     {map_path}")
    print("\nПеред публикацией страниц погасите долг по триггерам Unsplash:")
    print(f"  cd {PHOTO_INDEX_ROOT}")
    print("  python retrigger.py --vocab champagne --run")
    print("  (без --vocab/--projet расход спишется на moncaviste)")
    print(f"Ответы появятся в catalogue.json по ключам {request_id('{slug}', '{role}')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
