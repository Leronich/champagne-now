"""Фикстуры сверки с источником — и ложные обвинения, которых они стоили.

Треть файла фиксирует случаи, которые НЕ должны сигналить. Это не украшение:
первая версия модуля дала на корпусе две ошибки, обе ложные, обе на одном
механизме — стиль по сладости выбирался первым по списку, а не ближайшим к
числу.

Отдельная забота этого файла — проверка крепости. На корпусе 2026-08-14 ноль
упоминаний градуса, то есть в обычном прогоне она молчит всегда. Проверка,
которая никогда не срабатывает, неотличима от сломанной: через полгода никто
не вспомнит, молчит она потому что всё хорошо, или потому что регулярка
перестала совпадать. Здесь она кусается по требованию.

    python tests/test_check_numbers.py
"""

import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from scripts.check_numbers import (_f, _NUM, articles, check_file,  # noqa: E402
                                   check_text, html_text, load_refs)

REFS = load_refs()


def codes(text):
    return [f["code"] for f in check_text(text, REFS)["findings"]]


# ── Число: две нотации в одном корпусе ──────────────────────────────────────
#
# Главный риск переноса из одноязычного проекта. Там запятая всегда десятичная,
# здесь она же — разделитель тысяч в английской половине. Мотив, знающий только
# пробел, читает «40,000 bottles» как 40: ошибка в тысячу раз, и выглядит она
# не как сбой разбора, а как неправдоподобный факт.

def test_nombre_deux_notations():
    for texte, attendu in (("40,000 bottles", 40000.0),     # тысячи по-английски
                           ("34 000 hectares", 34000.0),    # тысячи по-французски
                           ("1 200 000 bouteilles", 1200000.0),
                           ("1,84 hectare", 1.84),          # десятичная запятая
                           ("3,5 g/L", 3.5),
                           ("2,50", 2.5),
                           ("2.5", 2.5),
                           ("102", 102.0)):
        import re
        m = re.search(_NUM, texte)
        assert m, texte
        assert _f(m.group(1)) == attendu, (texte, m.group(1), _f(m.group(1)))


def test_un_seul_motif_de_nombre():
    """Защита от повторного расползания описания числа.

    В соседнем проекте портфеля один и тот же баг разделителя чинился трижды —
    ровно потому, что число описывалось в трёх местах. Если появится четвёртое
    определение, тест обязан упасть раньше, чем оно разойдётся с первым.
    """
    from scripts import check_coherence as C, check_numbers as N
    assert C._NUM is N._NUM
    assert C.RE_HECTARES.pattern.startswith(N._NUM)
    assert C.RE_BOTTLES.pattern.startswith(N._NUM)


# ── Дозаж: что должно быть поймано ──────────────────────────────────────────

def test_extra_brut_au_dessus_du_plafond():
    assert "DOSAGE_STYLE_MISMATCH" in codes(
        "This Extra Brut carries 10 g/L of residual sugar.")


def test_demi_sec_en_dessous_du_plancher():
    assert "DOSAGE_STYLE_MISMATCH" in codes(
        "Ce Demi-Sec titre 8 grammes par litre de sucre.")


def test_fourchette_de_dosage_inversee():
    assert "DOSAGE_RANGE_INVERTED" in codes("A Brut with 20 to 8 g/L of sugar.")


def test_dosage_sans_style_part_en_revue():
    """Default-deny: неразрешимое не публикуется молча.

    «45 g/L» у конкретной кюве без названия стиля сверить не с чем. Это не
    ошибка и не проходной случай — это ревью.
    """
    r = check_text("Le dosage généreux de 45 g/L transforme l'expérience.", REFS)
    assert "DOSAGE_STYLE_UNKNOWN" in [f["code"] for f in r["findings"]]
    assert r["errors"] == []
    assert r["needs_review"] and r["blocked"]


# ── Дозаж: что сигналить НЕ должно ──────────────────────────────────────────

def test_style_le_plus_proche_gagne():
    """Две ложные ошибки на корпусе, обе на этой фразе.

    Реальный текст: «Champagne with minimal (extra brut: 0-6g/L) or zero added
    sugar after dégorgement». К числу приклеен extra brut (потолок 6), но в той
    же фразе есть «zero … sugar», попадающий под мотив brut_nature (потолок 3).
    Выбор по порядку списка обвинял верный текст — в en и fr версиях статьи.
    """
    assert codes("Champagne with minimal (extra brut: 0-6g/L) or zero "
                 "added sugar after dégorgement.") == []
    assert codes("Champagne avec un dosage minimal (extra brut : 0-6 g/L) "
                 "ou zéro sucre ajouté après dégorgement.") == []


def test_dosages_conformes_restent_muets():
    """Стиль обязан стоять в той же фразе, что и число.

    Область поиска — фраза, а не страница, и это осознанный выбор: статья о
    Brut, упоминающая заодно Demi-Sec, приписала бы числу не тот потолок.
    Плата за это — фразы вроде «Le dosage de 6 à 12 grammes par litre révèle
    la personnalité», где стиль назван в заголовке страницы: они уходят в
    ревью, а не проходят молча. Именно так и выглядят 4 констата на корпусе.
    """
    for texte in ("Brut Champagne with 6-12 grams per liter of residual sugar.",
                  "Le Brut titre de 6 à 12 grammes par litre.",
                  "Demi-Sec Champagne with 32-50 grams per liter.",
                  "Un Extra Brut à 4 g/L, tendu et droit."):
        assert codes(texte) == [], texte


def test_perimetre_du_style_ne_deborde_pas():
    """«brut» внутри «extra brut» не должен красть потолок.

    Если короткий мотив съест длинный, все Extra Brut будут судиться по
    потолку 12 вместо 6 — то есть проверка промолчит ровно там, ради чего
    написана.
    """
    assert codes("This Extra Brut carries 10 g/L.") != []
    assert codes("This Brut carries 10 g/L.") == []


# ── Температура: пересчёт шкал ──────────────────────────────────────────────

def test_conversion_celsius_fahrenheit_fausse():
    assert "TEMP_CONVERSION_WRONG" in codes("Serve at 8°C (52°F) in a tulip glass.")


def test_conversion_juste_reste_muette():
    assert codes("Serve at 8°C (46°F) in a tulip glass.") == []


# ── Крепость: проверка, молчащая на корпусе ─────────────────────────────────
#
# На 2026-08-14 в 104 статьях ноль упоминаний градуса. Оба теста ниже — весь
# документ о том, что этот контроль жив.

def test_abv_mord_quand_le_degre_est_nomme():
    assert "ABV_OUT_OF_RANGE" in codes("The wine titre 16 % vol of alcohol.")
    assert "ABV_OUT_OF_RANGE" in codes("Un vin qui titre 16 % d'alcool.")


def test_pourcentage_d_assemblage_nest_pas_un_degre():
    """Шампанское описывают процентами сортов, а не только крепостью.

    Без требования контекста проверка сигналила бы на каждом ассамбляже —
    а их в корпусе десятки против нуля упоминаний градуса.
    """
    for texte in ("A blend of 100% Chardonnay from Avize.",
                  "80% Pinot Noir, 20% Chardonnay.",
                  "Un assemblage de 100 % Meunier.",
                  "Grand Cru vineyards rated 100% on the échelle des crus."):
        assert codes(texte) == [], texte


def test_abv_dans_la_plage_du_champagne():
    assert codes("A Champagne at 12 % vol of alcohol.") == []
    assert codes("Ce champagne titre 12,5 % vol.") == []


# ── Выдержка ────────────────────────────────────────────────────────────────

def test_elevage_sous_le_minimum_aoc():
    assert "AGING_BELOW_AOC" in codes("This vintage rested 20 months on its lees.")


def test_enonce_de_la_norme_nest_pas_une_infraction():
    """«minimum 15 months on the lees» — изложение правила, а не нарушение.

    В корпусе такая фраза есть дословно (history/methode-champenoise). Без
    исключения по контексту нормы модуль обвинял бы статью, которая правило
    как раз объясняет.
    """
    for texte in ("A single bottle spends minimum 15 months on its lees.",
                  "Regulation requires at least 15 months on the lees.",
                  "L'AOC exige au moins 15 mois sur lattes."):
        assert codes(texte) == [], texte


# ── HTML ────────────────────────────────────────────────────────────────────

def test_json_ld_nest_pas_scanne():
    """Числа из разметки читатель не видит, и проверять их незачем.

    Без снятия <script> в проверку попадали даты публикации и идентификаторы
    схемы — до полутора десятков лишних чисел на статью.
    """
    html = ('<script type="application/ld+json">{"datePublished":"2031-01-01",'
            '"dosage":"99 g/L"}</script><p>Un Brut à 8 g/L.</p>')
    texte = html_text(html)
    assert "99" not in texte and "2031" not in texte
    assert codes(texte) == []


# ── Корпус ──────────────────────────────────────────────────────────────────

def test_corpus_sans_erreur_bloquante():
    """104 статьи, ноль блокирующих ошибок.

    День, когда тест упадёт, означает одно из двух: в статью попало неверное
    число или правило стало слишком широким. Оба случая стоят взгляда до
    публикации.
    """
    fautes = []
    for path in articles(RACINE):
        res = check_file(path, REFS)
        if res["errors"]:
            fautes.append((str(path.parent.relative_to(RACINE)), res["errors"]))
    assert fautes == [], fautes


def test_corpus_revue_reste_du_type_connu():
    """Непроверяемое на корпусе — только «дозаж без названного стиля».

    Появление другого кода в ревью означает новый класс неразрешимых
    утверждений, и его надо разобрать, а не растворить в общем счётчике.
    """
    inconnus = []
    for path in articles(RACINE):
        for f in check_file(path, REFS)["findings"]:
            if not f["blocking"] and f["code"] != "DOSAGE_STYLE_UNKNOWN":
                inconnus.append((str(path.parent.relative_to(RACINE)), f["code"]))
    assert inconnus == [], inconnus


# ── Таблица значений ────────────────────────────────────────────────────────

def test_chaque_entree_porte_sa_provenance():
    """source + confidence + verified_on, иначе запись не считается.

    Правило записано в _meta таблицы; тест не даёт ему остаться декларацией.
    """
    manquants = []
    for famille, entrees in REFS.items():
        if famille.startswith("_") or not isinstance(entrees, dict):
            continue
        for cle, val in entrees.items():
            if cle.startswith("_") or not isinstance(val, dict):
                continue
            for champ in ("source", "confidence", "verified_on"):
                if champ not in val:
                    manquants.append(f"{famille}.{cle}: нет {champ}")
    assert manquants == [], manquants


def test_secondary_porte_son_verify_todo():
    """Значение, не снятое с официального текста, обязано сказать, где сверять.

    Иначе secondary через полгода неотличимо от primary, и таблица начинает
    врать тем самым полем, которое заведено против вранья.
    """
    nus = []
    for famille, entrees in REFS.items():
        if famille.startswith("_") or not isinstance(entrees, dict):
            continue
        for cle, val in entrees.items():
            if isinstance(val, dict) and val.get("confidence") == "secondary" \
                    and "verify_todo" not in val:
                nus.append(f"{famille}.{cle}")
    assert nus == [], nus


if __name__ == "__main__":
    import traceback
    fns = [(n, f) for n, f in sorted(globals().items())
           if n.startswith("test_") and callable(f)]
    ko = 0
    for name, fn in fns:
        try:
            fn()
            print(f"  ok   {name}")
        except AssertionError:
            ko += 1
            print(f"  СБОЙ {name}")
            traceback.print_exc(limit=2)
    print(f"\n{len(fns) - ko}/{len(fns)} проходят")
    sys.exit(1 if ko else 0)
