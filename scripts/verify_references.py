"""verify_references.py — досье на сверку значений из reference_values.json.

Что делает и, главное, чего НЕ делает
-------------------------------------
Скрипт обходит записи, помеченные `verify_todo`, ищет через DataForSEO
официальный документ и складывает кандидатов в досье. На этом он
останавливается. Он не читает документ, не сравнивает цифры и никогда не
поднимает confidence до primary.

Граница проведена не из осторожности, а по факту. Сверка 2026-08-14 нашла
одну ошибку из четырёх, и ошибка была не в цифре: `rendement_butoir` стоял
10 400 кг/га — величина ГОДОВОГО рендемента, устанавливаемого решением на
каждый урожай, тогда как butoir из cahier des charges равен 15 500. Число
выглядело правдоподобно, источник назывался верно, подменено было понятие.
Поисковая выдача такое не ловит в принципе: сниппеты первых результатов
называли как раз цифры, близкие к неверной, потому что пресса цитирует
годовой рендемент. Верное значение лежало только в самом PDF, на девятой
странице из двадцати девяти.

Отсюда правило: выдача ищет ДОКУМЕНТ, значение берётся из документа
человеком. Автоматическое повышение до primary воспроизвело бы ровно ту
ошибку, против которой заведено поле confidence.

Записи с confidence=editorial не запрашиваются вовсе: это наши собственные
границы правдоподобия, внешнего первоисточника у них нет и быть не может.

    python scripts/verify_references.py --dry-run   # что и чем спрашивать, без трат
    python scripts/verify_references.py             # запросить и записать досье
    python scripts/verify_references.py --entry aoc_champagne.surface_aire_ha
"""

from __future__ import annotations

import argparse
import base64
import json
import sys
from pathlib import Path
from urllib.parse import urlparse

import requests

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "scripts"))

# Разбор .env описан в generate_banners — второй копии заводить не будем.
from generate_banners import DEFAULT_ENV, load_env          # noqa: E402
from check_numbers import REF_PATH, load_refs               # noqa: E402

DOSSIER = RACINE / "data" / "verification_dossier.json"

SERP_URL = "https://api.dataforseo.com/v3/serp/google/organic/live/regular"
USER_URL = "https://api.dataforseo.com/v3/appendix/user_data"

# Вес домена. Смысл не в ранжировании качества сайтов, а в одном различии:
# первоисточник против пересказа. Всё, что ниже 50, в досье попадает, но
# помечено как пересказ — читать его вместо документа значит вернуться к
# агрегатору, то есть к secondary.
POIDS = [
    ("inao.gouv.fr",        100),
    ("legifrance.gouv.fr",   95),
    ("eur-lex.europa.eu",    95),
    ("europa.eu",            85),
    ("agriculture.gouv.fr",  85),
    (".gouv.fr",             80),
    ("champagne.fr",         70),   # Comité Champagne — держатель статистики
    ("sgv-champagne.fr",     60),
    (".org",                 40),
]
SEUIL_PRIMAIRE = 70


def poids_domaine(domaine: str) -> int:
    domaine = (domaine or "").lower()
    for motif, valeur in POIDS:
        if domaine.endswith(motif) or motif in domaine:
            return valeur
    return 10


# ── Отбор записей ───────────────────────────────────────────────────────────

def a_verifier(refs: dict, seulement: str = "") -> list:
    """Записи, ждущие сверки.

    Берём то, что несёт verify_todo. Записи editorial отсеиваются раньше:
    у редакционной границы нет внешнего источника, и запрос по ней потратил
    бы деньги на поиск того, чего не существует.
    """
    sortie = []
    for famille, entrees in refs.items():
        if famille.startswith("_") or not isinstance(entrees, dict):
            continue
        for cle, val in entrees.items():
            if cle.startswith("_") or not isinstance(val, dict):
                continue
            chemin = f"{famille}.{cle}"
            if seulement and chemin != seulement:
                continue
            if val.get("confidence") == "editorial":
                continue
            if not val.get("verify_todo"):
                continue
            sortie.append({"chemin": chemin, "famille": famille,
                           "cle": cle, "entree": val})
    return sortie


def requete(item: dict) -> str:
    """Запрос строится из verify_todo, а не из имени поля.

    verify_todo пишется человеком и содержит то, чего в ключе нет: как
    называется документ и у кого он лежит. Ключ `surface_aire_ha` сам по себе
    привёл бы в блог о винах.
    """
    todo = item["entree"]["verify_todo"]
    # Хвост после «в ... нет» — это указание, где искать НЕ надо; обрезаем.
    todo = todo.split(", в ")[0]
    return todo.strip()


# ── DataForSEO ──────────────────────────────────────────────────────────────

def _auth(env: dict) -> str:
    login, mdp = env.get("DATAFORSEO_LOGIN"), env.get("DATAFORSEO_PASSWORD")
    if not (login and mdp):
        print(f"ОШИБКА: в {DEFAULT_ENV} нет DATAFORSEO_LOGIN/PASSWORD", file=sys.stderr)
        sys.exit(1)
    return base64.b64encode(f"{login}:{mdp}".encode()).decode()


def solde(auth: str) -> float | None:
    try:
        r = requests.get(USER_URL, headers={"Authorization": f"Basic {auth}"}, timeout=30)
        res = (r.json().get("tasks") or [{}])[0].get("result") or [{}]
        return (res[0].get("money") or {}).get("balance")
    except Exception:
        return None


def chercher(auth: str, mots: str, profondeur: int = 10) -> tuple:
    """(кандидаты, стоимость). Кандидат — то, что предстоит ПРОЧИТАТЬ."""
    corps = [{"language_code": "fr", "location_code": 2250,
              "keyword": mots, "depth": profondeur}]
    r = requests.post(SERP_URL, timeout=90,
                      headers={"Authorization": f"Basic {auth}",
                               "Content-Type": "application/json"},
                      data=json.dumps(corps))
    d = r.json()
    if r.status_code != 200 or d.get("status_code") != 20000:
        raise RuntimeError(f"DataForSEO {r.status_code}: {d.get('status_message')}")

    candidats = []
    for tache in d.get("tasks") or []:
        for res in tache.get("result") or []:
            for item in res.get("items") or []:
                if item.get("type") != "organic":
                    continue
                url = item.get("url") or ""
                domaine = item.get("domain") or urlparse(url).netloc
                candidats.append({
                    "url": url,
                    "domaine": domaine,
                    "titre": (item.get("title") or "").strip(),
                    "poids": poids_domaine(domaine),
                    "pdf": url.lower().endswith(".pdf"),
                })
    # Первоисточники наверх; PDF чуть выше при равном весе — регламенты
    # почти всегда выкладывают файлом, а не страницей.
    candidats.sort(key=lambda c: (-c["poids"], not c["pdf"]))
    return candidats, float(d.get("cost") or 0)


# ── Досье ───────────────────────────────────────────────────────────────────

def charger_dossier() -> dict:
    if not DOSSIER.exists():
        return {}
    try:
        return json.loads(DOSSIER.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def ecrire_dossier(dossier: dict) -> None:
    dossier["_lisez_moi"] = (
        "Кандидаты на прочтение, собранные scripts/verify_references.py. "
        "Это НЕ подтверждённые значения: скрипт нашёл документы, но не читал их. "
        "Порядок работы: открыть первоисточник, найти величину, сверить с "
        "reference_values.json, и только тогда поднять confidence до primary, "
        "проставив citation и номер страницы. Ошибка 2026-08-14 была подменой "
        "понятия при верной на вид цифре — её ловит только чтение документа."
    )
    DOSSIER.parent.mkdir(parents=True, exist_ok=True)
    DOSSIER.write_text(json.dumps(dossier, ensure_ascii=False, indent=2, sort_keys=True),
                       encoding="utf-8")


def afficher(item: dict, candidats: list) -> None:
    entree = item["entree"]
    valeur = entree.get("value", {k: v for k, v in entree.items()
                                  if isinstance(v, (int, float))})
    print(f"\n{item['chemin']}")
    print(f"  текущее значение : {valeur}")
    print(f"  confidence       : {entree.get('confidence')}")
    print(f"  что сверять      : {entree['verify_todo']}")
    if not candidats:
        print("  кандидатов не найдено")
        return
    print("  кандидаты (сначала первоисточники):")
    for c in candidats[:6]:
        marque = "ПЕРВОИСТОЧНИК" if c["poids"] >= SEUIL_PRIMAIRE else "пересказ"
        pdf = " [pdf]" if c["pdf"] else ""
        print(f"    {marque:<14} {c['domaine'][:32]:<34}{pdf}")
        print(f"      {c['titre'][:76]}")
        print(f"      {c['url'][:104]}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Досье на сверку значений reference_values.json")
    parser.add_argument("--dry-run", action="store_true",
                        help="показать запросы, ничего не потратив")
    parser.add_argument("--entry", default="",
                        help="только одна запись, например aoc_champagne.surface_aire_ha")
    parser.add_argument("--force", action="store_true",
                        help="перезапросить даже то, что уже в досье")
    parser.add_argument("--depth", type=int, default=10, help="глубина выдачи")
    args = parser.parse_args()

    refs = load_refs()
    items = a_verifier(refs, args.entry)

    if not items:
        cible = f" по фильтру {args.entry}" if args.entry else ""
        print(f"Записей с verify_todo{cible} нет.")
        print(f"Таблица: {REF_PATH.relative_to(RACINE)}")
        return 0

    print(f"К сверке: {len(items)}")
    for item in items:
        print(f"  {item['chemin']:<40} {requete(item)[:60]}")

    if args.dry_run:
        print(f"\n--dry-run: запросов не отправлено, потрачено $0.")
        return 0

    env = load_env(DEFAULT_ENV)
    auth = _auth(env)
    balance = solde(auth)
    if balance is not None:
        print(f"\nбаланс DataForSEO: ${balance:.2f}")

    dossier = charger_dossier()
    total, erreurs = 0.0, []

    for item in items:
        if item["chemin"] in dossier and not args.force:
            print(f"\n{item['chemin']} — уже в досье, пропуск (--force чтобы обновить)")
            continue
        mots = requete(item)
        try:
            candidats, cout = chercher(auth, mots, args.depth)
        except Exception as e:
            erreurs.append((item["chemin"], str(e)))
            print(f"\n{item['chemin']} — ОШИБКА: {e}")
            continue
        total += cout
        afficher(item, candidats)
        dossier[item["chemin"]] = {
            "requete": mots,
            "valeur_actuelle": item["entree"].get("value"),
            "confidence_actuelle": item["entree"].get("confidence"),
            "verify_todo": item["entree"]["verify_todo"],
            "candidats": candidats[:8],
            "statut": "a_lire",       # меняет человек, прочитав документ
        }

    ecrire_dossier(dossier)
    print(f"\n{'=' * 74}")
    print(f"потрачено: ${total:.4f} | досье: {DOSSIER.relative_to(RACINE)}")
    print("Скрипт нашёл документы. Значение подтверждает человек, прочитав их —")
    print("подмену понятия при верной на вид цифре поиск не ловит.")
    if erreurs:
        print(f"\nс ошибкой: {len(erreurs)}")
        for chemin, detail in erreurs:
            print(f"  {chemin}: {detail}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
