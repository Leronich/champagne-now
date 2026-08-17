"""
scripts/build_sitemap.py
Собирает sitemap.xml так, чтобы lastmod можно было верить.

Правило одно: lastmod двигается тогда и только тогда, когда изменился ТЕКСТ,
который видит читатель. Не дата файла, не факт коммита — хеш извлечённого
содержимого.

Почему именно так
-----------------
14.08.2026 инжектор согласия переписал <head> всех 109 страниц. Ни одного
слова в тексте не поменялось. Любая схема на основе даты файла или «файл
попал в коммит» объявила бы 109 изменений — и это тот самый способ сделать
lastmod бесполезным: если он не бьётся с реальностью, поисковик перестаёт его
учитывать и уходит на собственное расписание обхода. Инструмент, которым
можно было бы попросить переобход пяти нужных страниц, ломается об заявку
«изменились все».

Обратная крайность у нас уже была: sitemap.xml пролежал статикой с 07.06.2026,
пока содержимое менялось 284 раза. Замерший lastmod так же неинформативен, как
и скачущий, только просит он при этом ничего.

Состояние живёт в data/sitemap-state.json: URL -> {hash, lastmod}.

    python scripts/build_sitemap.py --seed-from-git   # первый прогон
    python scripts/build_sitemap.py --dry-run
    python scripts/build_sitemap.py
"""

import argparse
import hashlib
import json
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "scripts"))

from check_numbers import html_text                      # noqa: E402

ETAT = RACINE / "data" / "sitemap-state.json"
SORTIE = RACINE / "sitemap.xml"
BASE = "https://champagne.now"

# Разделы, у которых приоритет отличается от статейного.
PRIORITE = {"": "1.0", "en/legal": "0.3", "fr/legal": "0.3",
            "en/contact": "0.3", "en/quiz": "0.6",
            "en/editorial": "0.5", "fr/editorial": "0.5"}
PRIORITE_DEFAUT = "0.8"
CHANGEFREQ = "monthly"

RE_CANONICAL = re.compile(r'<link rel="canonical" href="([^"]+)"')
RE_NOINDEX = re.compile(r'<meta[^>]+name="robots"[^>]+noindex', re.I)
RE_HREFLANG = re.compile(r'<link rel="alternate" hreflang="([a-z]{2})" href="([^"]+)"')


# Обвязка страницы: одинакова на всех и меняется разом на всех. Меню, подвал,
# хлебные крошки, баннер согласия.
# Оверлей идёт первым: внутри него лежит свой <nav>, и если сначала сработает
# альтернатива «<nav>…</nav>», от оверлея останется обёртка с крестиком &#10005;
# — один символ, из-за которого 115 страниц объявили бы себя изменившимися.
RE_CHROME = re.compile(
    r'(?is)<div class="nav-overlay".*?</nav>\s*</div>'
    r"|<nav\b.*?</nav>"
    r"|<footer\b.*?</footer>"
    r'|<div class="breadcrumb-bar".*?</div>\s*</div>')


def empreinte(html: str) -> str:
    """Хеш ВИДИМОГО текста СТАТЬИ, а не файла и не всей страницы.

    Разметка, схема и подключения скриптов не входят намеренно: читателю они не
    видны. Обвязка исключается по другой причине — она общая. 18.08.2026
    добавление гамбургер-меню изменило видимый текст всех 132 страниц разом, и
    sitemap объявил бы 131 изменение из-за одной кнопки. Это ровно то «всё
    изменилось сегодня», ради предотвращения которого файл и переписан:
    lastmod должен двигаться, когда изменилась СТАТЬЯ.
    """
    corps = RE_CHROME.sub(" ", html)
    texte = re.sub(r"\s+", " ", html_text(corps)).strip()
    return hashlib.sha256(texte.encode("utf-8")).hexdigest()[:16]


def pages() -> list:
    return sorted(p for p in RACINE.rglob("index.html")
                  if ".wrangler" not in p.parts)


def url_de(path: Path, html: str) -> str:
    """Canonical — источник истины; путь на диске только запасной вариант."""
    m = RE_CANONICAL.search(html)
    if m:
        return m.group(1)
    rel = str(path.parent.relative_to(RACINE)).replace("\\", "/")
    return f"{BASE}/" if rel == "." else f"{BASE}/{rel}/"


def priorite(path: Path) -> str:
    rel = str(path.parent.relative_to(RACINE)).replace("\\", "/")
    if rel == ".":
        return PRIORITE[""]
    for prefixe, valeur in PRIORITE.items():
        if prefixe and rel.startswith(prefixe):
            return valeur
    return PRIORITE_DEFAUT


# ── Засев из git ────────────────────────────────────────────────────────────

def _texte_au_commit(commit: str, chemin: str) -> str | None:
    try:
        out = subprocess.run(["git", "show", f"{commit}:{chemin}"],
                             cwd=RACINE, capture_output=True, timeout=30)
        if out.returncode != 0:
            return None
        return out.stdout.decode("utf-8", "replace")
    except Exception:
        return None


def date_du_dernier_changement(path: Path) -> str | None:
    """Дата коммита, в котором ТЕКСТ страницы стал нынешним.

    Не «последний коммит, тронувший файл»: под это определение попал бы
    инжектор согласия, переписавший заголовок 109 страниц без единого слова
    в тексте. Идём по истории файла от новых к старым и останавливаемся там,
    где текст впервые отличается от текущего.
    """
    rel = str(path.relative_to(RACINE)).replace("\\", "/")
    out = subprocess.run(["git", "log", "--format=%H %ad", "--date=short", "--", rel],
                         cwd=RACINE, capture_output=True, timeout=60)
    lignes = [l.split(" ", 1) for l in out.stdout.decode().splitlines() if l.strip()]
    if not lignes:
        return None

    actuel = empreinte(path.read_text(encoding="utf-8", errors="replace"))
    derniere = lignes[0][1]
    for commit, jour in lignes:
        texte = _texte_au_commit(commit, rel)
        if texte is None:
            break
        if empreinte(texte) != actuel:
            break              # здесь текст был другим -> изменился в следующем
        derniere = jour
    return derniere


# ── Сборка ──────────────────────────────────────────────────────────────────

def charger_etat() -> dict:
    if not ETAT.exists():
        return {}
    try:
        return json.loads(ETAT.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def alternates(infos: dict) -> dict:
    """hreflang только для пар, обе стороны которых существуют на диске.

    В прежнем sitemap у каждого URL стояла ровно одна «альтернатива» — он сам,
    что не описывает ничего. Хуже: hreflang 20 английских страниц ведёт на
    французские адреса, которых нет (собран механически как «{слаг}-fr», тогда
    как реальные французские слаги переведены). Заявлять их здесь значит
    повторить ошибку в файле, который поисковик читает первым.
    """
    connus = {i["url"] for i in infos.values()}
    sortie = {}
    for chemin, info in infos.items():
        paires = {}
        for langue, href in RE_HREFLANG.findall(info["html"]):
            if href in connus:
                paires[langue] = href
        # Набор имеет смысл только если в нём есть кто-то кроме самой страницы.
        sortie[chemin] = paires if len(paires) > 1 else {}
    return sortie


def construire(aujourd_hui: str, seed: bool, garder_dates: bool = False) -> tuple:
    """garder_dates — режим пересчёта хешей после правки самой функции
    empreinte(). Смена способа считать хеш не есть изменение страниц: без
    этого первая же пересборка объявила бы изменившимся весь сайт, то есть
    соврала бы ровно так, как этот файл призван не врать."""
    etat = charger_etat()
    infos, nouveau = {}, {}

    for path in pages():
        html = path.read_text(encoding="utf-8", errors="replace")
        if RE_NOINDEX.search(html):
            continue
        infos[str(path)] = {"path": path, "html": html,
                            "url": url_de(path, html), "hash": empreinte(html)}

    alt = alternates(infos)
    lignes, change, inchange, ajoutes = [], [], 0, []

    for chemin in sorted(infos, key=lambda c: infos[c]["url"]):
        info = infos[chemin]
        url, h = info["url"], info["hash"]
        precedent = etat.get(url)

        if precedent and (garder_dates or precedent.get("hash") == h):
            lastmod = precedent["lastmod"]
            inchange += 1
        elif precedent:
            lastmod = aujourd_hui
            change.append(url)
        else:
            lastmod = (date_du_dernier_changement(info["path"]) or aujourd_hui) \
                      if seed else aujourd_hui
            ajoutes.append(url)

        nouveau[url] = {"hash": h, "lastmod": lastmod}

        bloc = [f"  <url>",
                f"    <loc>{url}</loc>",
                f"    <lastmod>{lastmod}</lastmod>",
                f"    <changefreq>{CHANGEFREQ}</changefreq>",
                f"    <priority>{priorite(info['path'])}</priority>"]
        for langue, href in sorted(alt[chemin].items()):
            bloc.append(f'    <xhtml:link rel="alternate" hreflang="{langue}" href="{href}"/>')
        bloc.append("  </url>")
        lignes.append("\n".join(bloc))

    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n'
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"\n'
           '        xmlns:xhtml="http://www.w3.org/1999/xhtml">\n'
           + "\n".join(lignes) + "\n</urlset>\n")
    return xml, nouveau, change, ajoutes, inchange


def main() -> int:
    parser = argparse.ArgumentParser(description="sitemap.xml по хешу содержимого")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--seed-from-git", action="store_true",
                        help="первый прогон: lastmod берётся из истории, а не «сегодня»")
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--rehash", action="store_true",
                        help="пересчитать хеши, НЕ трогая lastmod — после правки "
                             "самой функции хеширования")
    args = parser.parse_args()

    xml, etat, change, ajoutes, inchange = construire(
        args.date, args.seed_from_git, garder_dates=args.rehash)

    print(f"URL: {len(etat)} | без изменений: {inchange} | "
          f"изменилось: {len(change)} | впервые: {len(ajoutes)}")
    for url in change:
        print(f"  изменено  {url}")
    for url in ajoutes[:14]:
        print(f"  новое     {url}  ({etat[url]['lastmod']})")
    if len(ajoutes) > 14:
        print(f"  … ещё {len(ajoutes) - 14}")

    if args.dry_run:
        print("\n--dry-run: ничего не записано.")
        return 0

    SORTIE.write_text(xml, encoding="utf-8")
    ETAT.parent.mkdir(parents=True, exist_ok=True)
    ETAT.write_text(json.dumps(etat, ensure_ascii=False, indent=2, sort_keys=True),
                    encoding="utf-8")
    print(f"\nзаписано: {SORTIE.name}, {ETAT.relative_to(RACINE)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
