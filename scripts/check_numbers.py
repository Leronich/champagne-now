"""check_numbers.py — пересчёт опубликованных чисел против внешнего источника.

Зачем модуль
------------
Проверять числа, доверяя тому, кто их написал, нельзя: уверенность автора не
коррелирует с верностью. Этот модуль ни у кого не спрашивает — он пересчитывает
и сверяется с data/reference_values.json.

Область
-------
Здесь живут утверждения, СВЕРЯЕМЫЕ С ИСТОЧНИКОМ: дозаж против порогов
регламента, пересчёт °C/°F, градус против диапазона, выдержка против минимума
AOC. Внутренние противоречия текста — в check_coherence.py: им источник не
нужен, только текст и пара границ.

Замер корпуса на 2026-08-14 (100 статей en+fr): дозаж 8 упоминаний,
температура 33, выдержка 16, объёмы 36, градус 0.

Default-deny
------------
Утверждение, для которого источник не разрешился, не становится ошибкой, но
уходит в ревью: `unverifiable` -> `needs_review` -> `blocked`. Молча не
публикуется ничего.

Двуязычность с первой строки
----------------------------
Все мотивы покрывают en и fr одной альтернацией, а не параметром языка. Гейт,
говорящий на одном языке, для второго — отсутствующий гейт, причём молча.
"""

from __future__ import annotations

import json
import re
import sys
import unicodedata
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
DATA = RACINE / "data"
REF_PATH = DATA / "reference_values.json"

# 5 % пропускают честное округление и ловят настоящие расхождения.
TOLERANCE = 0.05


def load_refs(path: Path | None = None) -> dict:
    return json.loads((path or REF_PATH).read_text(encoding="utf-8"))


# ── ЧИСЛО. Единственное описание на весь фактчек ─────────────────────────────
#
# Корпус двуязычный, и это меняет разбор по сравнению с одноязычным проектом.
# В одних и тех же статьях встречается:
#
#     40,000 bottles      запятая = тысячи   (английская половина, 9 случаев)
#     34 000 hectares     пробел  = тысячи   (французская половина, 5 случаев)
#     1,84 ha / 3,5 / 2,50   запятая = десятичная (французская половина)
#     2.5                 точка   = десятичная
#
# Мотив, знающий только пробел-как-тысячи, отдаёт запятую десятичной части и
# читает «40,000 bottles» как 40 — ошибка в тысячу раз. Именно этот класс уже
# ловили дважды за день в соседнем проекте портфеля; там он не проявлялся
# только потому, что корпус был одноязычным.
#
# Правило: разделитель, за которым РОВНО три цифры и дальше не цифра, —
# разделитель тысяч. Иначе десятичный.
#
# Остаточная неоднозначность записана честно: французское «1,234» в значении
# «одна целая двести тридцать четыре тысячных» будет прочитано как 1234. На
# корпусе 2026-08-14 таких нет — все десятичные запятые идут с одним-двумя
# знаками. Если появятся, ломаться будет здесь, и чинить надо здесь же:
# описание числа обязано остаться в одном месте.
_ESPACES = "    "
_SEPS = _ESPACES + ",."
_CLS = "".join(f"\\{c}" if c in ".^]\\-" else c for c in _SEPS)

_NUM = rf"(\d{{1,3}}(?:[{_CLS}]\d{{3}})+(?!\d)|\d+(?:[.,]\d+)?)"
_RE_MILLIERS = re.compile(rf"\d{{1,3}}(?:[{_CLS}]\d{{3}})+$")


def _f(s: str) -> float:
    """Число, записанное по-французски или по-английски -> float."""
    s = s.strip()
    if _RE_MILLIERS.fullmatch(s):
        for sep in _SEPS:
            s = s.replace(sep, "")
        return float(s)
    for sep in _ESPACES:
        s = s.replace(sep, "")
    return float(s.replace(",", "."))


# ── Разрешение ссылок ───────────────────────────────────────────────────────

def _strip(s: str) -> str:
    s = unicodedata.normalize("NFKD", s.lower())
    return "".join(c for c in s if not unicodedata.combining(c))


def resolve(ref: str, refs: dict):
    """«eu.sparkling_dosage_g_l.brut_max» -> 12, или None."""
    node = refs
    for part in ref.split("."):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    if isinstance(node, dict):
        return node.get("value", node)
    return node


# ── Констат ─────────────────────────────────────────────────────────────────

class Finding(dict):
    """Констат. `blocking` отделяет ошибку от «проверить руками»."""

    def __init__(self, code, message, quote="", blocking=True, expected=None, stated=None):
        super().__init__(code=code, message=message, quote=quote,
                         blocking=blocking, expected=expected, stated=stated)

    def __str__(self):
        base = f"[{self['code']}] {self['message']}"
        return f"{base} — «{self['quote']}»" if self["quote"] else base


def _off(stated: float, expected: float) -> float:
    if expected == 0:
        return 0.0 if stated == 0 else 1.0
    return abs(stated - expected) / abs(expected)


def _sentence_around(text: str, start: int, end: int) -> str:
    left = text.rfind(".", 0, start) + 1
    right = text.find(".", end)
    return text[left: right if right != -1 else len(text)]


# ── Текст из HTML ───────────────────────────────────────────────────────────

def html_text(html: str) -> str:
    """Видимый текст страницы.

    Сначала снимаются script/style и комментарии — иначе JSON-LD со схемой
    статьи попадает в проверку и приносит числа, которых читатель не видит:
    даты публикации, идентификаторы. Замер: без этого шага на статью
    добавлялось до полутора десятков ложных чисел.
    """
    html = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", html)
    html = re.sub(r"(?s)<!--.*?-->", " ", html)
    text = re.sub(r"<[^>]+>", " ", html)
    text = (text.replace("&nbsp;", " ").replace("&#39;", "'")
                .replace("&amp;", "&").replace("&quot;", '"'))
    return re.sub(r"[ \t]+", " ", text)


# ── Стили по сладости ───────────────────────────────────────────────────────
#
# Порядок альтернатив — от длинного к короткому. «brut» впереди «extra brut»
# съел бы хвост и все Extra Brut считались бы обычными Brut, то есть проверка
# с потолком 12 вместо 6 молча пропускала бы ровно те случаи, ради которых
# написана.
STYLES = [
    ("brut_nature", r"brut\s*nature|brut\s*z[ée]ro|non[- ]dos[ée]|zero\s*dosage|"
                    r"z[ée]ro\s*dosage|sans\s*dosage|pas\s*dos[ée]"),
    ("demi_sec",    r"demi[- ]sec|semi[- ]dry|semi[- ]sweet"),
    ("extra_brut",  r"extra[- ]brut"),
    ("extra_dry",   r"extra[- ]dry|extra[- ]sec"),
    ("doux",        r"\bdoux\b|\bsweet\b"),
    ("brut",        r"\bbrut\b"),
    ("sec",         r"\bsec\b|\bdry\b"),
]
_RE_STYLES = [(key, re.compile(pat, re.I)) for key, pat in STYLES]

# Границы стиля из таблицы: (минимум или None, максимум или None)
_BORNES = {
    "brut_nature": (None, "brut_nature_max"),
    "extra_brut":  (None, "extra_brut_max"),
    "brut":        (None, "brut_max"),
    "extra_dry":   ("extra_dry_min", "extra_dry_max"),
    "sec":         ("sec_min", "sec_max"),
    "demi_sec":    ("demi_sec_min", "demi_sec_max"),
    "doux":        ("doux_min", None),
}

_UNITE_GL = r"(?:g\s*/\s*l|grammes?\s+par\s+litre|grams?\s+per\s+li(?:ter|tre))"

RE_DOSAGE_RANGE = re.compile(
    rf"{_NUM}\s*(?:-|–|à|to|and|et)\s*{_NUM}\s*{_UNITE_GL}", re.I)
RE_DOSAGE_ONE = re.compile(rf"{_NUM}\s*{_UNITE_GL}", re.I)


def _style_near(sentence: str, position: int) -> str | None:
    """Стиль, БЛИЖАЙШИЙ к числу, а не первый попавшийся в фразе.

    Порядок списка здесь не годится. Реальная фраза корпуса:

        «minimal (extra brut: 0-6g/L) or zero added sugar after dégorgement»

    К числу приклеен «extra brut», но в той же фразе есть «zero … sugar»,
    попадающий под мотив brut_nature. Выбор по порядку списка давал потолок
    3 г/л вместо 6 и обвинял верный текст — то есть ровно то ложное
    обвинение, которое дороже пропущенного сомнения.
    """
    best, best_dist = None, None
    for key, rx in _RE_STYLES:
        for m in rx.finditer(sentence):
            dist = 0 if m.start() <= position <= m.end() else min(
                abs(m.start() - position), abs(m.end() - position))
            if best_dist is None or dist < best_dist:
                best, best_dist = key, dist
    return best


def _band(style: str, table: dict) -> tuple:
    lo_key, hi_key = _BORNES[style]
    lo = table.get(lo_key) if lo_key else None
    hi = table.get(hi_key) if hi_key else None
    return lo, hi


def check_dosage(text: str, refs: dict) -> list[Finding]:
    """Значение в г/л против порога названного рядом стиля."""
    table = refs.get("eu", {}).get("sparkling_dosage_g_l", {})
    if not table:
        return [Finding("REF_MISSING", "в таблице нет eu.sparkling_dosage_g_l",
                        blocking=False)]

    out, couverts = [], []

    def juger(valeurs, quote, sentence, position):
        style = _style_near(sentence, position)
        if style is None:
            out.append(Finding(
                "DOSAGE_STYLE_UNKNOWN",
                f"дозаж {quote.strip()} назван без стиля по сладости — "
                "сверить с регламентом невозможно",
                quote.strip(), blocking=False))
            return
        lo, hi = _band(style, table)
        for v in valeurs:
            if hi is not None and v > hi * (1 + TOLERANCE):
                out.append(Finding(
                    "DOSAGE_STYLE_MISMATCH",
                    f"{v:g} г/л при стиле «{style}»: регламент даёт потолок {hi} г/л",
                    quote.strip(), expected=f"<= {hi}", stated=v))
            elif lo is not None and v < lo * (1 - TOLERANCE):
                out.append(Finding(
                    "DOSAGE_STYLE_MISMATCH",
                    f"{v:g} г/л при стиле «{style}»: регламент даёт минимум {lo} г/л",
                    quote.strip(), expected=f">= {lo}", stated=v))

    for m in RE_DOSAGE_RANGE.finditer(text):
        lo_v, hi_v = _f(m.group(1)), _f(m.group(2))
        couverts.append((m.start(), m.end()))
        sentence = _sentence_around(text, m.start(), m.end())
        # Смещение числа ВНУТРИ фразы — по нему выбирается ближайший стиль.
        position = m.start() - (text.rfind(".", 0, m.start()) + 1)
        if lo_v > hi_v:
            out.append(Finding(
                "DOSAGE_RANGE_INVERTED",
                f"вилка дозажа от {lo_v:g} до {hi_v:g} г/л: нижняя граница выше верхней",
                m.group(0).strip(), expected=f"{hi_v:g}-{lo_v:g}", stated=f"{lo_v:g}-{hi_v:g}"))
            continue
        juger((lo_v, hi_v), m.group(0), sentence, position)

    for m in RE_DOSAGE_ONE.finditer(text):
        if any(a <= m.start() < b for a, b in couverts):
            continue                       # уже разобрано как вилка
        juger((_f(m.group(1)),), m.group(0),
              _sentence_around(text, m.start(), m.end()),
              m.start() - (text.rfind(".", 0, m.start()) + 1))
    return out


# ── Температура: пересчёт шкал ──────────────────────────────────────────────
#
# В корпусе соседствуют «Serve at 8°C» и «properly chilled — 46°F». Модуль,
# знающий только Цельсий, во втором случае либо промолчит, либо примет 46 за
# °C и обвинит верный текст.
RE_TEMP_PAIR = re.compile(
    rf"{_NUM}\s*°\s*C[^.]{{0,20}}?{_NUM}\s*°\s*F"
    rf"|{_NUM}\s*°\s*F[^.]{{0,20}}?{_NUM}\s*°\s*C", re.I)


def check_temp_conversion(text: str, refs: dict) -> list[Finding]:
    c = refs["constants"]["fahrenheit_offset"]
    facteur, decalage = c["factor"], c["value"]
    out = []
    for m in RE_TEMP_PAIR.finditer(text):
        groupes = [g for g in m.groups() if g]
        if len(groupes) != 2:
            continue
        # Порядок ветвей: первая — C затем F, вторая — F затем C.
        if re.match(rf"^{_NUM}\s*°\s*C", m.group(0), re.I):
            celsius, fahrenheit = _f(groupes[0]), _f(groupes[1])
        else:
            fahrenheit, celsius = _f(groupes[0]), _f(groupes[1])
        attendu = celsius * facteur + decalage
        if _off(fahrenheit, attendu) <= TOLERANCE:
            continue
        out.append(Finding(
            "TEMP_CONVERSION_WRONG",
            f"{celsius:g} °C это {attendu:.1f} °F, в тексте {fahrenheit:g} °F",
            m.group(0).strip(), expected=round(attendu, 1), stated=fahrenheit))
    return out


# ── Градус ──────────────────────────────────────────────────────────────────
#
# Контекст обязателен. Шампанское описывают процентами ассамбляжа —
# «100% Chardonnay», «80% Pinot Noir», — и без требования контекста проверка
# срабатывала бы на каждом сорте винограда.
RE_ABV = re.compile(rf"{_NUM}\s*(?:%|degr[ée]s?)", re.I)
RE_ABV_CTX = re.compile(r"vol\.?|alcool|alcohol|abv|titr", re.I)


def check_abv(text: str, refs: dict) -> list[Finding]:
    p = refs["plausibility"]["abv_pct"]
    out = []
    for m in RE_ABV.finditer(text):
        fenetre = text[max(0, m.start() - 40): m.end() + 25]
        if not RE_ABV_CTX.search(fenetre):
            continue
        v = _f(m.group(1))
        if not (p["min"] <= v <= p["max"]):
            out.append(Finding(
                "ABV_OUT_OF_RANGE",
                f"градус {v:g} % вне диапазона шампанского {p['min']}-{p['max']} %",
                m.group(0).strip(), blocking=False,
                expected=f"{p['min']}-{p['max']}", stated=v))
    return out


# ── Выдержка против минимума AOC ────────────────────────────────────────────

RE_LEES = re.compile(
    rf"{_NUM}\s*(?:months?|mois)[^.]{{0,40}}?"
    rf"(?:on\s+(?:its\s+|the\s+)?lees|sur\s+lattes?|sur\s+lies)"
    rf"|(?:on\s+(?:its\s+|the\s+)?lees|sur\s+lattes?|sur\s+lies)[^.]{{0,40}}?"
    rf"{_NUM}\s*(?:months?|mois)", re.I)
RE_MILLESIME_CTX = re.compile(r"vintage|mill[ée]sim", re.I)
# «minimum 15 months» — это изложение нормы, а не заявление о конкретной кюве.
RE_NORME_CTX = re.compile(r"minimum|at least|au moins|r[èe]glement|requires?|exige", re.I)


def check_aging(text: str, refs: dict) -> list[Finding]:
    seuils = refs.get("aoc_champagne", {}).get("elevage_min_mois", {})
    if not seuils:
        return []
    out = []
    for m in RE_LEES.finditer(text):
        capture = next((g for g in m.groups() if g), None)
        if capture is None:
            continue
        mois = _f(capture)
        phrase = _sentence_around(text, m.start(), m.end())
        if RE_NORME_CTX.search(phrase):
            continue                       # текст излагает норму, не нарушает её
        millesime = bool(RE_MILLESIME_CTX.search(phrase))
        seuil = seuils["millesime"] if millesime else seuils["non_millesime"]
        if mois < seuil:
            quoi = "миллезимного" if millesime else "невинтажного"
            out.append(Finding(
                "AGING_BELOW_AOC",
                f"{mois:g} мес на осадке для {quoi} — минимум AOC {seuil} мес "
                f"от даты тиража",
                m.group(0).strip(), blocking=False,
                expected=f">= {seuil}", stated=mois))
    return out


# ── Вход ────────────────────────────────────────────────────────────────────

CHECKS = (check_dosage, check_temp_conversion, check_abv, check_aging)


def check_text(text: str, refs: dict | None = None) -> dict:
    refs = refs if refs is not None else load_refs()
    findings = []
    for fn in CHECKS:
        findings.extend(fn(text, refs))

    errors = [str(f) for f in findings if f["blocking"]]
    unverifiable = [str(f) for f in findings if not f["blocking"]]
    return {
        "errors": errors,
        "unverifiable": unverifiable,
        "needs_review": bool(unverifiable),
        "blocked": bool(errors) or bool(unverifiable),
        "findings": findings,
    }


def check_file(path: Path, refs: dict | None = None) -> dict:
    return check_text(html_text(path.read_text(encoding="utf-8", errors="replace")), refs)


def articles(racine: Path | None = None) -> list[Path]:
    racine = racine or RACINE
    return sorted(p for langue in ("en", "fr")
                  for p in (racine / langue).glob("*/*/index.html"))


def main(argv: list[str]) -> int:
    refs = load_refs()
    cibles = [Path(a) for a in argv if not a.startswith("-")] or articles()
    verbeux = "-v" in argv or "--verbose" in argv

    total_err = total_rev = 0
    for path in cibles:
        res = check_file(path, refs)
        if not res["findings"] and not verbeux:
            continue
        rel = path.parent.relative_to(RACINE)
        print(f"\n{rel}")
        for ligne in res["errors"]:
            print(f"  ОШИБКА  {ligne}")
        for ligne in res["unverifiable"]:
            print(f"  ревью   {ligne}")
        total_err += len(res["errors"])
        total_rev += len(res["unverifiable"])

    print(f"\n{'=' * 74}")
    print(f"статей: {len(cibles)} | ошибок: {total_err} | в ревью: {total_rev}")
    return 1 if total_err else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
