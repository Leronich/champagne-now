"""
scripts/add_consent.py
Приводит все страницы к схеме «согласие до трекера».

Что делает на каждой странице:
  1. заменяет безусловный блок gtag на Consent Mode v2 с отказом по умолчанию;
  2. подключает /static/consent.css и /static/consent.js;
  3. вынимает инлайновый загрузчик Stay22 — он переезжает в consent.js и
     запускается только после согласия;
  4. вычищает старый баннер (#cookie-banner, .cb-*) с главной страницы.

Идемпотентен: повторный запуск ничего не меняет.

    python scripts/add_consent.py --dry-run
    python scripts/add_consent.py

Почему инжектором, а не руками: страниц 109, и правка формулировки согласия в
109 местах разойдётся при первой же спешке — ровно так на сайте и оказался
баннер на одной странице из 101 при аналитике на всех.
"""

import argparse
import re
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent

GA_ID = "G-J8273H5YMH"
MARQUEUR = "cn-consent-default-v2"        # признак уже обработанной страницы

# Consent Mode обязан выполниться ДО загрузки gtag.js, поэтому остаётся
# инлайном и стоит первым в <head>. Всё остальное — во внешних файлах.
BLOC_CONSENT = f"""<!-- {MARQUEUR}: отказ по умолчанию, до любого трекера -->
<script>
window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments);}}
gtag('consent','default',{{'ad_storage':'denied','ad_user_data':'denied',
'ad_personalization':'denied','analytics_storage':'denied','wait_for_update':500}});
try{{var c=JSON.parse(localStorage.getItem('cn_consent')||'null');
if(c&&c.exp>Date.now()&&c.analytics===true){{gtag('consent','update',{{'analytics_storage':'granted'}});}}
}}catch(e){{}}
gtag('js',new Date());gtag('config','{GA_ID}');
</script>
<link rel="stylesheet" href="/static/consent.css" />"""

SCRIPT_PIED = '<script defer src="/static/consent.js"></script>'

# Блок v1: объявлял отказ по умолчанию, но всё равно грузил gtag.js сразу.
# Consent Mode шлёт бескуковый пинг и в состоянии denied — то есть контакт с
# Google происходил до выбора. Замерено в браузере: после «Refuse» уходил
# один хит. Загрузчик переехал в consent.js и стартует только по согласию.
RE_V1 = re.compile(
    r"[ 	]*<!-- cn-consent-default:.*?<link rel=\"stylesheet\" href=\"/static/consent\.css\" />",
    re.S)

# Старый блок GA: комментарий + загрузчик + инлайн-конфиг.
RE_GA = re.compile(
    r"[ \t]*<!--\s*Google tag \(gtag\.js\)\s*-->\s*"
    r"<script async src=\"https://www\.googletagmanager\.com/gtag/js\?id=[^\"]+\"></script>\s*"
    r"<script>.*?</script>\s*", re.S)

# Инлайновый Stay22 в конце body.
# `(?:(?!</script>).)` вместо простого `.` — не косметика. Первая редакция
# писалась как `<script>…stay22…</script>` с re.S, и точка спокойно пересекала
# закрывающий тег: совпадение начиналось на РАНЕЕМ скрипте (анимация пузырьков)
# и тянулось до Stay22, снося всё между ними — включая подвал и блок квиза.
# На 109 страницах это вырезало 5248 строк и оставило 37 страниц без подвала.
# Здесь точка физически не может выйти за границу своего <script>.
RE_STAY22 = re.compile(
    r"[ \t]*<script>((?:(?!</script>).)*?stay22(?:(?!</script>).)*?)</script>\s*",
    re.S | re.I)

# Старый баннер и его обвязка на главной.
RE_VIEUX_BANNIERE = re.compile(
    r"[ \t]*<!--\s*COOKIE BANNER\s*-->\s*<div id=\"cookie-banner\".*?</div>\s*</div>\s*",
    re.S | re.I)
RE_VIEUX_JS = re.compile(
    r"[ \t]*function cb(?:Accept|Decline)\s*\([^)]*\)\s*\{[^}]*\}\s*", re.S)
RE_VIEUX_APPEL = re.compile(
    r"[ \t]*(?:if\s*\([^)]*cn_cookies[^)]*\)[^;{]*\{[^}]*\}|"
    r"[^\n]*cn_cookies[^\n]*)\n", re.I)


def pages() -> list:
    """Все HTML сайта, кроме служебных каталогов."""
    return sorted(p for p in RACINE.rglob("*.html")
                  if ".wrangler" not in p.parts and "node_modules" not in p.parts)


# Доля страницы, которую инжектор вправе удалить. Он вынимает блок gtag,
# загрузчик Stay22 и старый баннер — вместе это малая часть даже короткой
# страницы. Всё, что больше, означает жадное совпадение, а не работу.
PERTE_MAX = 0.25


def verifier(avant: str, apres: str) -> str:
    """Пусто, если преобразование безопасно; иначе описание проблемы."""
    for balise in ("</body>", "</html>"):
        if avant.count(balise) != apres.count(balise):
            return f"нарушена структура: {balise}"
    for balise in ("<footer", "<nav", "<article", "<main"):
        if apres.count(balise) < avant.count(balise):
            return f"потерян блок {balise} ({avant.count(balise)} → {apres.count(balise)})"
    if len(avant) and (len(avant) - len(apres)) / len(avant) > PERTE_MAX:
        perdu = 100 * (len(avant) - len(apres)) // len(avant)
        return f"удалено {perdu}% страницы — похоже на жадное совпадение"
    return ""


def transformer(html: str) -> tuple:
    """(новый html, список сделанного). Пустой список — страница не тронута."""
    fait = []

    if MARQUEUR in html:
        return html, fait                      # уже обработана

    # Миграция v1 -> v2: снимаем прежний блок целиком, дальше кладётся новый.
    if RE_V1.search(html):
        html = RE_V1.sub("", html, count=1)
        html = re.sub(r"[ 	]*<script async src=\"https://www\.googletagmanager\.com/"
                      r"gtag/js\?id=[^\"]+\"></script>\s*", "", html, count=1)
        fait.append("v1→v2 (gtag.js убран из головы)")

    # 1. GA -> Consent Mode
    if RE_GA.search(html):
        html = RE_GA.sub(BLOC_CONSENT + "\n", html, count=1)
        fait.append("gtag→consent")
    else:
        # Страница без аналитики (юридические, quiz): баннер всё равно нужен —
        # Stay22 на них стоял, а согласие не спрашивалось вовсе.
        html = html.replace("<meta charset=\"utf-8\" />",
                            "<meta charset=\"utf-8\" />\n" + BLOC_CONSENT, 1)
        fait.append("consent (без GA)")

    # 2. Инлайновый Stay22 -> под согласие
    if RE_STAY22.search(html):
        html = RE_STAY22.sub("", html)
        fait.append("stay22→под согласие")

    # 3. Старый баннер главной
    if RE_VIEUX_BANNIERE.search(html):
        html = RE_VIEUX_BANNIERE.sub("", html)
        fait.append("старый баннер снят")
    if RE_VIEUX_JS.search(html):
        html = RE_VIEUX_JS.sub("", html)
        fait.append("cbAccept/cbDecline сняты")

    # 4. Скрипт согласия перед </body>
    if SCRIPT_PIED not in html:
        html = html.replace("</body>", SCRIPT_PIED + "\n</body>", 1)
        fait.append("consent.js")

    return html, fait


def main() -> int:
    parser = argparse.ArgumentParser(description="Согласие до трекера на всех страницах")
    parser.add_argument("--dry-run", action="store_true", help="показать, не записывая")
    args = parser.parse_args()

    touchees, deja, resume, refus = 0, 0, {}, []
    for path in pages():
        avant = path.read_text(encoding="utf-8", errors="replace")
        apres, fait = transformer(avant)
        if not fait:
            deja += 1
            continue

        # Предохранитель. Инжектор режет по регулярным выражениям, а жадное
        # выражение съедает молча и правдоподобно: страница остаётся валидной,
        # просто без половины содержимого. Проверяем то, что заведомо должно
        # уцелеть, и отказываемся писать, если не уцелело.
        souci = verifier(avant, apres)
        if souci:
            refus.append((str(path.relative_to(RACINE)), souci))
            continue
        touchees += 1
        for f in fait:
            resume[f] = resume.get(f, 0) + 1
        if not args.dry_run:
            path.write_text(apres, encoding="utf-8")

    if refus:
        print(f"ОТКАЗ на {len(refus)} страниц(ах) — ничего не записано:")
        for nom, souci in refus[:10]:
            print(f"  {nom}: {souci}")
        return 1

    print(f"страниц всего: {len(pages())} | изменено: {touchees} | без изменений: {deja}")
    for quoi, n in sorted(resume.items(), key=lambda kv: -kv[1]):
        print(f"  {n:>4}  {quoi}")
    if args.dry_run:
        print("\n--dry-run: ничего не записано.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
