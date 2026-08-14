"""check_coherence.py — связность чисел статьи с самой собой.

Зачем второй модуль
-------------------
check_numbers.py пересчитывает то, под чем есть источник: порог регламента,
шкала температур, минимум выдержки. Он предполагает, что источник существует.

По замеру корпуса на 2026-08-14 у большей части чисел его нет: 86 упоминаний
года, 36 объёмов и площадей, 16 сроков — против 8 упоминаний дозажа, где
источник есть. Риск этой массы не «неверная арифметика по верной таблице», а
«текст противоречит сам себе»: дата основания, не сходящаяся с объявленным
возрастом, площадь и производство, дающие невозможную урожайность,
перевёрнутая вилка.

Таблица, которая покрыла бы все 86 годов, была бы каталогом фактов — ровно тем
неуправляемым монстром, от которого отказались в reference_values.json.
Этот модуль заходит с другой стороны: ему нужен только текст и несколько
границ.

Тон констатов
-------------
Почти всё НЕблокирующее. Модуль рассуждает выводом по прозе, а неверный вывод
даёт ложное обвинение — оно дороже пропущенного сомнения, потому что приучает
игнорировать гейт. Блокируют только механические противоречия: вилка, у
которой низ выше верха, и миллезим в будущем.
"""

from __future__ import annotations

import re
import sys
from datetime import date
from pathlib import Path

try:
    from scripts.check_numbers import (RACINE, Finding, _f, _NUM, _sentence_around,
                                       articles, html_text, load_refs)
except ImportError:
    from check_numbers import (RACINE, Finding, _f, _NUM, _sentence_around,
                               articles, html_text, load_refs)


# ── Температура ─────────────────────────────────────────────────────────────
#
# Три уровня вместо одного, и это прямо следствие корпуса. Наивная проверка
# «подача 4-14 °C» обвинила бы верный текст: 11 °C и 12 °C в статьях про
# Ruinart, Taittinger и Montagne de Reims относятся к меловым крайерам,
# которые держат эту температуру круглый год. Погреб — не бокал.
RE_TEMP_SERVICE = re.compile(
    rf"(?:serv(?:e|ed|ing|ir|ez|ice)|drink|boire|d[ée]gust|chilled|frais)"
    rf"[^.]{{0,60}}?{_NUM}\s*°\s*C", re.I)
RE_TEMP_CAVE = re.compile(
    r"cave|cellar|crayèr|crayer|underground|sous\s+terre|"
    r"chalk|craie|m[èe]tres?\s+sous|year[- ]round|toute\s+l[’']ann[ée]e|"
    r"[ée]t[ée]\s+comme\s+hiver", re.I)

# Улица, лето, багажник: температура там нормальна, даже когда выпадает из
# любого «винного» диапазона. Обязательный третий контекст — без него фраза
# «cellars maintain 10°C year-round while streets can reach 25°C in summer»
# судила уличные 25 °C по мерке погреба и обвиняла верный текст.
RE_TEMP_AMBIANT = re.compile(
    r"street|outdoor|outside|summer|heat\s*wave|canicule|ext[ée]rieur|dehors|"
    r"plein\s+soleil|voiture|coffre|car\s+(?:boot|trunk)|in\s+a\s+car|"
    r"room\s+temp|temp[ée]rature\s+ambiante|balcon|terrasse|"
    # Месяцы в обеих языках: список только из французских делал исключение
    # односторонним, и «45°C in a car boot in July» судилось наравне с
    # опиской. Гейт, знающий одну половину корпуса, для второй отсутствует.
    r"juillet|ao[ûu]t|july|august|"
    # «été» пишется как причастие «a été»: без артикля впереди исключение
    # срабатывало на любой фразе в прошедшем времени и глушило правило целиком.
    r"(?:en|cet|l['’]|d['’])\s*[ée]t[ée]\b", re.I)

RE_TEMP_TOUTE = re.compile(rf"{_NUM}\s*°\s*C", re.I)

_CONTEXTES = (("cave", RE_TEMP_CAVE), ("ambiant", RE_TEMP_AMBIANT))


def _contexte_proche(text: str, position: int) -> str | None:
    """Какой контекст БЛИЖЕ к числу — погреб или улица.

    Окно фиксированной ширины не годится: в одной фразе корпуса стоят и
    погреб, и улица, и любое окно, достаточно широкое чтобы увидеть первый,
    натягивает его и на второй. Побеждает ближайшее слово — то же правило,
    что и при выборе стиля дозажа.
    """
    fenetre_debut = max(0, position - 140)
    fenetre = text[fenetre_debut: position + 60]
    relative = position - fenetre_debut

    best, best_dist = None, None
    for nom, rx in _CONTEXTES:
        for m in rx.finditer(fenetre):
            dist = min(abs(m.start() - relative), abs(m.end() - relative))
            if best_dist is None or dist < best_dist:
                best, best_dist = nom, dist
    return best


def check_temps(text: str, refs: dict) -> list[Finding]:
    p = refs["plausibility"]
    out = []
    deja = []

    for m in RE_TEMP_SERVICE.finditer(text):
        deja.append(m.start())
        v = _f(m.group(1))
        lo, hi = p["service_temp_c"]["min"], p["service_temp_c"]["max"]
        if not (lo <= v <= hi):
            out.append(Finding(
                "TEMP_SERVICE_IMPLAUSIBLE",
                f"температура подачи {v:g} °C вне диапазона {lo}-{hi} °C",
                m.group(0).strip(), blocking=False,
                expected=f"{lo}-{hi}", stated=v))

    lo_c, hi_c = p["cellar_temp_c"]["min"], p["cellar_temp_c"]["max"]
    lo_a, hi_a = p["temp_absurde_c"]["min"], p["temp_absurde_c"]["max"]
    for m in RE_TEMP_TOUTE.finditer(text):
        if any(abs(m.start() - d) < 80 for d in deja):
            continue
        v = _f(m.group(1))
        contexte = _contexte_proche(text, m.start())
        # Улица или салон машины: значение вне «винных» границ там нормально и
        # является предметом фразы, а не опиской.
        if contexte == "ambiant":
            continue
        # Погреб: значение своё, диапазон свой. Молчим, если попадает.
        if contexte == "cave":
            if not (lo_c <= v <= hi_c):
                out.append(Finding(
                    "TEMP_CELLAR_IMPLAUSIBLE",
                    f"температура погреба {v:g} °C вне диапазона {lo_c}-{hi_c} °C",
                    m.group(0).strip(), blocking=False,
                    expected=f"{lo_c}-{hi_c}", stated=v))
            continue
        if not (lo_a <= v <= hi_a):
            out.append(Finding(
                "TEMP_ABSURDE",
                f"температура {v:g} °C вне любого правдоподобного диапазона "
                f"({lo_a}…{hi_a} °C) — вероятна опечатка или перепутанная шкала",
                m.group(0).strip(), blocking=False,
                expected=f"{lo_a}-{hi_a}", stated=v))
    return out


# ── Объёмы и площади: канарейка на разделитель ──────────────────────────────
#
# Проверка существует не ради фактов, а ради разбора. Если «40,000 bottles»
# прочитано как 40, это видно здесь и только здесь: 40 бутылок в день у
# мастера-ремюора абсурдны, а 40 000 — норма. Ошибка разбора выглядит как
# ошибка факта, поэтому её и ловим границей снизу.
RE_BOTTLES = re.compile(
    rf"{_NUM}\s*(million|millions|milliard|billion)?\s*"
    rf"(?:bottles?|bouteilles?)", re.I)
RE_HECTARES = re.compile(rf"{_NUM}\s*(?:ha\b|hectares?)", re.I)
_FACTEURS = {"million": 1e6, "millions": 1e6, "milliard": 1e9, "billion": 1e9}

# Темп или объём производства. Отличает производственное число от счётного.
RE_PRODUCTION_CTX = re.compile(
    r"dail(?:y|ies)|annual|per\s+year|each\s+year|a\s+year|per\s+day|"
    r"par\s+an|par\s+jour|par\s+semaine|per\s+week|chaque\s+ann[ée]e|"
    r"produc|produit|produis|output|turn|remue|requisition|exige", re.I)


def _bottles(m) -> float:
    return _f(m.group(1)) * _FACTEURS.get((m.group(2) or "").lower(), 1)


def check_volumes(text: str, refs: dict) -> list[Finding]:
    p = refs["plausibility"]
    out = []
    lo, hi = p["production_bottles"]["min"], p["production_bottles"]["max"]
    for m in RE_BOTTLES.finditer(text):
        v = _bottles(m)
        # Отсечка по величине здесь не годится: «40 bottles daily» — это ровно
        # тот случай, ради которого проверка написана (неразобранное «40,000»),
        # и порог «меньше сотни пропускаем» съедал бы её первой. Отделяем по
        # контексту: счётная бутылка («a single bottle spends 15 months»)
        # темпа производства рядом не имеет.
        if not RE_PRODUCTION_CTX.search(text[max(0, m.start() - 90): m.end() + 60]):
            continue
        if not (lo <= v <= hi):
            out.append(Finding(
                "VOLUME_IMPLAUSIBLE",
                f"{v:,.0f} бутылок вне правдоподобного диапазона "
                f"{lo:,.0f}…{hi:,.0f} — проверить и число, и его разбор",
                m.group(0).strip(), blocking=False,
                expected=f"{lo:,.0f}-{hi:,.0f}", stated=v))

    lo_s, hi_s = p["surface_ha"]["min"], p["surface_ha"]["max"]
    for m in RE_HECTARES.finditer(text):
        v = _f(m.group(1))
        if not (lo_s <= v <= hi_s):
            out.append(Finding(
                "SURFACE_IMPLAUSIBLE",
                f"{v:g} га вне правдоподобного диапазона {lo_s}…{hi_s} га",
                m.group(0).strip(), blocking=False,
                expected=f"{lo_s}-{hi_s}", stated=v))
    return out


# ── Урожайность: площадь x производство ─────────────────────────────────────

def check_yield(text: str, refs: dict) -> list[Finding]:
    """Площадь и производство в ОДНОЙ фразе -> гл/га.

    Сопоставление — догадка: ничто не гарантирует, что оба числа про один и
    тот же объект. Площадь апелласьона рядом с производством одного дома дала
    бы бессмыслицу. Отсюда двойная предосторожность — одна фраза и близость в
    140 знаков — и неблокирующий констат.
    """
    p = refs["plausibility"]["rendement_hl_ha"]
    litres = refs["constants"]["bottle_volume_l"]["value"]
    par_hl = refs["constants"]["litres_per_hl"]["value"]
    out = []

    for ms in RE_HECTARES.finditer(text):
        debut = text.rfind(".", 0, ms.start()) + 1
        fin = text.find(".", ms.end())
        fin = fin if fin != -1 else len(text)
        for mb in RE_BOTTLES.finditer(text, debut, fin):
            if abs(mb.start() - ms.end()) > 140:
                continue
            ha = _f(ms.group(1))
            if ha <= 0:
                continue
            hl = _bottles(mb) * litres / par_hl
            rendement = hl / ha
            if p["min"] <= rendement <= p["max"]:
                break
            out.append(Finding(
                "YIELD_IMPLAUSIBLE",
                f"{ha:g} га и {mb.group(0).strip()} дают {rendement:.0f} гл/га, "
                f"вне диапазона {p['min']}-{p['max']} гл/га",
                text[debut:fin].strip()[:160], blocking=False,
                expected=f"{p['min']}-{p['max']}", stated=round(rendement)))
            break
    return out


# ── Даты ────────────────────────────────────────────────────────────────────

RE_YEAR = re.compile(r"\b(1[0-9]{3}|20[0-9]{2})\b")
RE_MILLESIME_YEAR = re.compile(
    r"(?:mill[ée]simes?|vendanges?|vintages?|harvests?)\s+(?:de\s+|of\s+)?"
    r"\b(1[0-9]{3}|20[0-9]{2})\b"
    r"|\b(1[0-9]{3}|20[0-9]{2})\s+(?:vintage|harvest|mill[ée]sime)\b", re.I)

# Апостроф терпимый: корпус мешает прямой и типографский.
_APO = r"[’'\s]?"
RE_ELAPSED = re.compile(
    rf"(?:il y a|depuis|voil[àa]|for the past|over)\s+{_NUM}\s*(?:ans?|years?)"
    rf"|{_NUM}\s*ans?\s+(?:plus tard|apr[èe]s|d{_APO}histoire|d{_APO}existence|"
    rf"d{_APO}[âa]ge|d{_APO}anciennet[ée])"
    rf"|{_NUM}\s*years?\s+(?:later|on|of history|of existence|of tradition|ago)", re.I)


def check_dates(text: str, refs: dict, today_year: int | None = None) -> list[Finding]:
    annee = today_year or date.today().year
    out = []

    # Только МИЛЛЕЗИМ в будущем. Просто будущий год блокировать нельзя:
    # «won't see its full potential until 2035» — это окно выдержки, обычная
    # для темы формулировка. Будущего урожая не существует, будущей зрелости —
    # сколько угодно.
    for m in RE_MILLESIME_YEAR.finditer(text):
        y = int(next(g for g in m.groups() if g))
        if y > annee:
            out.append(Finding(
                "VINTAGE_IN_FUTURE",
                f"миллезим {y} позже текущего года ({annee}) — такого урожая нет",
                _sentence_around(text, m.start(), m.end()).strip()[:160],
                blocking=True, expected=f"<= {annee}", stated=y))

    # «основан в 1743 … 250 лет истории»: 1743 + 250 = 1993, а не 2026.
    for m in RE_ELAPSED.finditer(text):
        capture = next((g for g in m.groups() if g), None)
        if capture is None:
            continue
        n = _f(capture)
        phrase = _sentence_around(text, m.start(), m.end())
        annees = [int(y) for y in RE_YEAR.findall(phrase)]
        if not annees:
            continue
        base = min(annees)
        implique = base + n
        # 3 года допуска: «около 280 лет» на 1743 остаётся честным.
        if abs(implique - annee) > 3 and implique != base:
            out.append(Finding(
                "DATE_INCOHERENT",
                f"{base} + {n:.0f} = {implique:.0f}, а сейчас {annee} — "
                "дата и объявленный возраст не сходятся",
                phrase.strip()[:160], blocking=False,
                expected=annee, stated=int(implique)))
    return out


# ── Перевёрнутая вилка ──────────────────────────────────────────────────────
#
# Только «между X и Y» и «от X до Y». Перечисление вроде «de 2014 et 2013» —
# это список миллезимов, а не вилка: включать его значит выдумывать ошибку.
RE_RANGE_ANY = re.compile(
    rf"(?:entre\s+{_NUM}\s*et\s+{_NUM}|de\s+{_NUM}\s*[àa]\s+{_NUM}"
    rf"|between\s+{_NUM}\s*and\s+{_NUM}|from\s+{_NUM}\s*to\s+{_NUM})", re.I)


def check_contradictions(text: str, refs: dict) -> list[Finding]:
    """Вилка, у которой нижняя граница выше верхней. Механично, потому блокирует."""
    out = []
    for m in RE_RANGE_ANY.finditer(text):
        nums = [g for g in m.groups() if g]
        if len(nums) != 2:
            continue
        lo, hi = _f(nums[0]), _f(nums[1])
        if lo > hi:
            out.append(Finding(
                "RANGE_INVERTED",
                f"вилка от {lo:g} до {hi:g}: нижняя граница выше верхней",
                m.group(0).strip(), blocking=True,
                expected=f"{hi:g}-{lo:g}", stated=f"{lo:g}-{hi:g}"))
    return out


# ── Вход ────────────────────────────────────────────────────────────────────

CHECKS = (check_temps, check_volumes, check_yield, check_contradictions)


def check_text(text: str, refs: dict | None = None,
               today_year: int | None = None) -> dict:
    refs = refs if refs is not None else load_refs()
    findings = []
    for fn in CHECKS:
        findings.extend(fn(text, refs))
    findings.extend(check_dates(text, refs, today_year))

    errors = [str(f) for f in findings if f["blocking"]]
    doubts = [str(f) for f in findings if not f["blocking"]]
    return {
        "errors": errors,
        "doubts": doubts,
        "needs_review": bool(doubts),
        "blocked": bool(errors) or bool(doubts),
        "findings": findings,
    }


def check_file(path: Path, refs: dict | None = None) -> dict:
    return check_text(html_text(path.read_text(encoding="utf-8", errors="replace")), refs)


def main(argv: list[str]) -> int:
    refs = load_refs()
    cibles = [Path(a) for a in argv if not a.startswith("-")] or articles()
    verbeux = "-v" in argv or "--verbose" in argv

    total_err = total_dbt = 0
    for path in cibles:
        res = check_file(path, refs)
        if not res["findings"] and not verbeux:
            continue
        print(f"\n{path.parent.relative_to(RACINE)}")
        for ligne in res["errors"]:
            print(f"  ОШИБКА  {ligne}")
        for ligne in res["doubts"]:
            print(f"  сомнение {ligne}")
        total_err += len(res["errors"])
        total_dbt += len(res["doubts"])

    print(f"\n{'=' * 74}")
    print(f"статей: {len(cibles)} | ошибок: {total_err} | сомнений: {total_dbt}")
    return 1 if total_err else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
