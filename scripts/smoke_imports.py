#!/usr/bin/env python3
"""Дым: импортируется ли каждый модуль репозитория в чистом окружении?

Класс поломок, на который написан тест, — не конкретный баг, а «зависимость,
которая не приходит из git»: абсолютный путь, пакет, поставленный руками,
файл состояния, никогда не коммиченный. Все они выглядят одинаково — код
работает у автора и нигде больше, — и обнаруживаются только там, где этой
машины нет.

В соседнем проекте портфеля такой тест написан после того, как первый в
истории репозитория прогон CI умер на импорте: модуль искал компонент по
зашитому windows-пути, существовавшему на рабочем месте и больше нигде.

Здесь болезнь та же и ещё не проявилась только потому, что CI нет:

    scripts/image_builder.py       PHOTO_INDEX_ROOT = Path(r"D:\\...\\kohexa-photo-index")
    scripts/submit_photo_requests.py   sys.path.insert(0, PHOTO_INDEX_ROOT)
                                       from vocabulaire.champagne import ...

Проверка провенанса намеренно строгая в CI и мягкая локально. На рабочем месте
хранилище фотографий законно лежит рядом, а не внутри чекаута: кричать на
каждом локальном запуске значит научить себя пропускать этот вывод мимо глаз.
В CI такой поблажки нет — там отсутствие зависимости и есть предмет проверки.

Запуск: python scripts/smoke_imports.py
"""

from __future__ import annotations

import importlib
import os
import pathlib
import re
import sys
import traceback

RACINE = pathlib.Path(__file__).resolve().parent.parent

# Модули, которые импортируются, но не должны выполняться при импорте.
IGNORER = {"__init__", "smoke_imports"}

# Внешние деревья, которые модули репозитория тянут по абсолютному пути.
# Список ведётся явно: молчаливое исключение и есть та поблажка, из-за
# которой поломка доживает до продакшена.
DEPENDANCES_EXTERNES = {
    "vocabulaire": "kohexa-photo-index (словарь ниши)",
    "engine": "kohexa-photo-index (движок фототеки)",
}

EN_CI = os.getenv("CI", "").lower() in ("1", "true", "yes")


def modules() -> list[str]:
    return [f"scripts.{p.stem}" for p in sorted((RACINE / "scripts").glob("*.py"))
            if p.stem not in IGNORER]


def verifier_provenance() -> list[str]:
    """Каждый импортированный модуль пришёл из чекаута?

    Смотрим не только на то, что импорт удался: если завтра кто-то снова
    зашьёт абсолютный путь И этот путь окажется на машине, простой импорт
    снова позеленеет. Требуем, чтобы модуль физически лежал в рабочем дереве.
    """
    soucis = []
    for nom, quoi in DEPENDANCES_EXTERNES.items():
        module = sys.modules.get(nom)
        if module is None:
            continue
        chemin = pathlib.Path(getattr(module, "__file__", "") or "").resolve()
        try:
            chemin.relative_to(RACINE.resolve())
        except ValueError:
            message = (f"'{nom}' загружен из {chemin}, вне чекаута ({RACINE}) — "
                       f"зависимость разрешена локальным путём: {quoi}")
            if EN_CI:
                soucis.append(message)
            else:
                print(f"  ВНИМАНИЕ {message}")
                print("           локально это нормально; в CI станет ошибкой")
    return soucis


# Запрещённый шаблон: имя проекта с молчаливым запасным значением.
# Регулярка скопирована из kohexa-photo-index/engine/projet.py, а не
# импортирована: этот скрипт обязан работать в чекауте без хранилища — ровно ту
# поломку он и стережёт. Пятнадцать символов дублирования лучше, чем проверка,
# которая гаснет вместе с зависимостью.
DEFAUT_SILENCIEUX = re.compile(
    r"""(?:getenv|environ\.get)\(\s*['"]PHOTO_SOURCE['"]\s*,\s*['"]([^'"]+)['"]""")


def verifier_nom_projet() -> list[str]:
    """Имя проекта объявлено, а не унаследовано от чужого дефолта?

    Та же болезнь, что и остальные проверки этого файла — «работает на дефолте
    разработчика», — но про переменную, а не про путь. Расход по общей квоте
    Unsplash списывается на имя проекта, и в исходном компоненте оно читалось
    так:

        PHOTO_SOURCE = os.getenv("PHOTO_SOURCE", ...)   # запасное «moncaviste»

    — многоточие в примере намеренно: иначе строка попалась бы собственной же
    проверке ниже.

    Этот сайт родился копией пайплайна mon-caviste, и копия унесла с собой
    чужое имя. 14.08.2026 расход champagne.now молча ушёл на счёт mon-caviste,
    а обнаружилось это у mon-caviste и не сразу — как «почему-то не хватает
    фото». Дефолт в источнике убран; проверка здесь стережёт возврат шаблона
    при следующем копировании.

    `image_builder.py` объявляет `PROJECT = "champagnenow"` константой и в
    переменной окружения не нуждается — поэтому её отсутствие тут не ошибка.
    Ошибка — запасное значение, подставляющее чужое имя.
    """
    soucis = []
    for chemin in sorted(RACINE.rglob("*.py")):
        if "__pycache__" in chemin.parts or chemin.resolve() == pathlib.Path(__file__).resolve():
            continue
        try:
            texte = chemin.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for i, ligne in enumerate(texte.splitlines(), 1):
            trouve = DEFAUT_SILENCIEUX.search(ligne)
            if trouve:
                soucis.append(
                    f"{chemin.relative_to(RACINE)}:{i} — запасное имя проекта "
                    f"«{trouve.group(1)}»: расход уйдёт на чужой счёт молча")
    if not soucis:
        print("  OK    имя проекта объявлено явно, без запасного значения")
    return soucis


def verifier_donnees() -> list[str]:
    """Данные, без которых модули бесполезны, читаются — и из чекаута?

    Импорт не доказывает работоспособность. Модуль может прекрасно
    импортироваться и искать свою таблицу на диске, которого нет.
    """
    soucis = []
    try:
        from scripts.check_numbers import load_refs, REF_PATH
        refs = load_refs()
    except Exception as e:
        return [f"reference_values.json не читается: {type(e).__name__}: {e}"]

    manquants = [c for c in ("eu", "plausibility", "constants") if c not in refs]
    if manquants:
        soucis.append(f"reference_values.json без обязательных семейств: {manquants}")

    chemin = pathlib.Path(REF_PATH).resolve()
    try:
        chemin.relative_to(RACINE.resolve())
    except ValueError:
        soucis.append(f"таблица значений читается из {chemin}, вне чекаута")

    if not soucis:
        familles = [k for k in refs if not k.startswith("_")]
        print(f"  OK    reference_values.json: семейств {len(familles)} — {', '.join(familles)}")
    return soucis


def main() -> int:
    sys.path.insert(0, str(RACINE))
    echecs: list[tuple[str, str]] = []

    for nom in modules():
        try:
            importlib.import_module(nom)
            print(f"  OK    {nom}")
        except BaseException:
            # SystemExit тоже: модуль, выходящий на импорте, сломан не меньше
            # модуля, который бросает.
            echecs.append((nom, traceback.format_exc()))
            print(f"  СБОЙ  {nom}")

    for souci in verifier_provenance():
        echecs.append(("провенанс", souci))
        print(f"  СБОЙ  провенанс: {souci}")

    for souci in verifier_nom_projet():
        echecs.append(("имя проекта", souci))
        print(f"  СБОЙ  имя проекта: {souci}")

    for souci in verifier_donnees():
        echecs.append(("данные", souci))
        print(f"  СБОЙ  данные: {souci}")

    print()
    if not echecs:
        mode = "CI" if EN_CI else "локально"
        print(f"OK — {len(modules())} модуль(ей) импортированы в чистом окружении ({mode}).")
        return 0

    for nom, detail in echecs:
        print(f"::error::{nom}: зависимость не удовлетворена одним лишь репозиторием")
        for ligne in detail.strip().splitlines()[-10:]:
            print(f"    {ligne}")
    print(f"\nСБОЙ — {len(echecs)} точк(и) зависимости не покрыты содержимым "
          f"репозитория: модуль не найден, путь к данным разрешён машиной, "
          f"либо таблица значений отсутствует.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
