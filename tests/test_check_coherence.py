"""Фикстуры внутренней связности — и ложные срабатывания, которых они стоили.

Половина файла фиксирует то, что сигналить НЕ должно. Первая версия модуля
дала на корпусе один констат, и он был ложным; второй дефект нашёлся только
синтетикой и был хуже — проверка отключала сама себя.

  - «cellars maintain 10°C year-round while streets can reach 25°C in summer»:
    окно контекста шириной в фразу натягивало погреб на уличную температуру, и
    верный текст обвинялся. Правило заменено на «ближайший контекст выигрывает».
  - «40 bottles daily» не сигналило: отсечка «меньше сотни пропускаем», зашитая
    чтобы не ругаться на счётную бутылку, съедала ровно тот случай, ради
    которого канарейка на разделитель тысяч и написана. Отделяется теперь
    контекстом производства, а не величиной.

Второй случай — причина, по которой этот файл существует отдельно от прогона
по корпусу. Прогон был чистым в обоих состояниях: и когда проверка работала, и
когда она молчала. Чистый корпус не доказывает ничего.

    python tests/test_check_coherence.py
"""

import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from scripts.check_coherence import check_file, check_text  # noqa: E402
from scripts.check_numbers import articles, load_refs       # noqa: E402

REFS = load_refs()
ANNEE = 2026


def codes(text):
    return [f["code"] for f in check_text(text, REFS, today_year=ANNEE)["findings"]]


# ── Что должно быть поймано ─────────────────────────────────────────────────

def test_millesime_dans_le_futur():
    assert "VINTAGE_IN_FUTURE" in codes("The 2031 vintage was exceptional.")
    assert "VINTAGE_IN_FUTURE" in codes("Le millésime 2031 est déjà légendaire.")


def test_fourchette_inversee():
    assert "RANGE_INVERTED" in codes("Prices run from 200 to 90 euros.")
    assert "RANGE_INVERTED" in codes("Comptez entre 200 et 90 euros la bouteille.")


def test_date_et_anciennete_ne_concordent_pas():
    assert "DATE_INCOHERENT" in codes(
        "Founded in 1743, the house celebrates 150 years of history.")
    assert "DATE_INCOHERENT" in codes(
        "Fondée en 1743, la maison revendique 150 ans d'histoire.")


def test_rendement_impossible():
    assert "YIELD_IMPLAUSIBLE" in codes(
        "Their 28 hectares yield 900,000 bottles annually.")


def test_temperature_de_service_absurde():
    assert "TEMP_SERVICE_IMPLAUSIBLE" in codes("Serve at 25°C for best results.")
    assert "TEMP_SERVICE_IMPLAUSIBLE" in codes("Servir ce champagne à 25°C.")


def test_temperature_de_cave_absurde():
    assert "TEMP_CELLAR_IMPLAUSIBLE" in codes(
        "Les crayères maintiennent naturellement 30°C toute l'année.")


# ── Канарейка на разделитель тысяч ──────────────────────────────────────────
#
# Проверка объёмов существует не ради фактов, а ради разбора: неразобранное
# «40,000» выглядит не как сбой парсера, а как неправдоподобный факт. Это
# единственное место, где ошибка разбора становится видимой.

def test_canari_du_separateur_mord():
    """«40 bottles daily» — это «40,000», потерявшее разделитель.

    Тест написан после того, как проверка молчала на этой фразе: собственная
    отсечка по величине убивала её первой.
    """
    assert "VOLUME_IMPLAUSIBLE" in codes("Master riddlers turn 40 bottles daily.")
    assert "VOLUME_IMPLAUSIBLE" in codes("The house produces 300 bottles annually.")


def test_volumes_correctement_lus_restent_muets():
    for texte in ("Master riddlers turn 40,000 bottles daily.",
                  "Il exige 50 000 bouteilles par semaine pour le Reich.",
                  "The Germans requisitioned an estimated 14 million bottles.",
                  "34 000 hectares produce 300 million bottles."):
        assert codes(texte) == [], texte


def test_bouteille_comptable_nest_pas_une_production():
    """«A single bottle spends 15 months» — счётная, не производственная.

    Отделяется контекстом темпа, а не порогом величины: порог убивал канарейку.
    """
    for texte in ("A single bottle spends minimum 15 months on its lees.",
                  "Une bouteille de 1996 dégustée à trois stades.",
                  "Each bottle requires an eighth-turn."):
        assert codes(texte) == [], texte


# ── Температура: три контекста, побеждает ближайший ─────────────────────────

def test_cave_et_rue_dans_la_meme_phrase():
    """Единственный ложный констат первой версии, дословно из корпуса.

    «cellars maintain 10°C year-round while streets can reach 25°C in summer»:
    окно в 120 знаков видело «cellars … year-round» и судило уличные 25 °C по
    мерке погреба (9-14 °C).
    """
    assert codes("Bring layers; cellars maintain 10°C year-round while "
                 "streets can reach 25°C in summer.") == []


def test_temperatures_de_cave_reelles_du_corpus():
    """11 °C и 12 °C в статьях — это крайеры Реймса, а не подача.

    Наивная проверка подачи (4-14 °C) их бы пропустила по совпадению, но
    диапазон погреба существует затем, чтобы совпадение не подменяло правило.
    """
    for texte in ("Les caves, creusées au IVe siècle, maintiennent naturellement 11°C.",
                  "18 mètres sous terre, température constante à 12°C.",
                  "The chalk cellars hold 10°C year-round."):
        assert codes(texte) == [], texte


def test_temperature_ambiante_nest_jugee_par_aucune_plage():
    for texte in ("Streets can reach 25°C in summer.",
                  "Sous une canicule à 35°C, la vigne souffre.",
                  "Two hours at 45°C in a car boot in July ruins a bottle."):
        assert codes(texte) == [], texte


def test_temperature_de_service_conforme():
    for texte in ("Serve at 8°C, no colder.",
                  "The Champagne should be equally cold, around 6°C.",
                  "Servir le champagne à 10°C en verres tulipe."):
        assert codes(texte) == [], texte


# ── Что сигналить НЕ должно ─────────────────────────────────────────────────

def test_fenetre_de_garde_dans_le_futur():
    """«won't see its full potential until 2035» — окно выдержки, не ошибка.

    Будущего урожая не существует; будущей зрелости — сколько угодно. Первая
    версия правила, сигналившая на любой будущий год, обвиняла бы обычную для
    темы формулировку.
    """
    assert codes("Released in 2024, it won't see its full potential until 2035.") == []
    assert codes("Il sera meilleur en 2035, à attendre jusqu'en 2030.") == []


def test_anciennete_juste_reste_muette():
    assert codes("Founded in 1743, the house celebrates 283 years of history.") == []
    assert codes("Fondée en 1772, la maison a 254 ans d'existence.") == []


def test_separateur_de_milliers_ne_cree_pas_de_fourchette_inversee():
    """«from 900 to 1,200 euros» — не перевёрнутая вилка.

    В соседнем проекте портфеля этот случай дал четыре ложных констата: число
    ломалось по разделителю, и 1 200 читалось как 1.
    """
    assert codes("Expect from 900 to 1,200 euros a bottle.") == []
    assert codes("Comptez entre 900 et 1 200 euros.") == []


def test_enumeration_de_millesimes_nest_pas_une_fourchette():
    assert codes("Les millésimes de 2014 et 2013 sont très différents.") == []


def test_surface_reelle_du_corpus():
    """Clos du Mesnil — 1,84 га. Монопль, а не ошибка разбора."""
    assert codes("Le Clos du Mesnil couvre 1,84 hectare.") == []
    assert codes("Their 28 hectares span Dizy, Hautvillers and Avize.") == []


def test_rendement_plausible_reste_muet():
    """34 000 га и 300 млн бутылок дают 66 гл/га — порядок апелласьона."""
    assert codes("Les 34 000 hectares produisent 300 millions de bouteilles.") == []


def test_article_normal_ne_declenche_rien():
    """28 га и 240 000 бутылок — это 64 гл/га, в порядке апелласьона.

    В первой редакции фикстуры здесь стояли 900 000 бутылок, перенесённые из
    положительного теста: 241 гл/га, вдвое выше потолка. Проверка была права,
    ошибалась фикстура — случай, ради которого отрицательные тесты и считают
    арифметику, а не переписывают правдоподобно выглядящие строки.
    """
    assert codes(
        "Founded in 1743, the house has 283 years of history. The 2018 vintage "
        "rested 36 months on its lees. Serve at 8°C. The cellars hold 11°C "
        "year-round. Their 28 hectares make 240,000 bottles a year."
    ) == []


# ── Корпус ──────────────────────────────────────────────────────────────────

def test_corpus_publie_reste_silencieux():
    """104 статьи, ноль констатов.

    Тест намеренно строже, чем у сверки с источником: этому модулю нечего
    отправлять в ревью — он либо видит противоречие, либо нет.
    """
    bruit = []
    for path in articles(RACINE):
        res = check_file(path, REFS)
        if res["findings"]:
            bruit.append((str(path.parent.relative_to(RACINE)),
                          [f["code"] for f in res["findings"]]))
    assert bruit == [], bruit


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
