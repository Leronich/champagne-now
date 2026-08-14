"""
scripts/image_builder.py
Тонкий клиент к kohexa-photo-index для сайта Champagne.now.

НЕ содержит:
- ключа Unsplash (он в kohexa-photo-index)
- логики скачивания — фотографии отдаются хотлинком с images.unsplash.com,
  перехостить их лицензия запрещает
- сборки атрибуции: `credit_html` приходит готовым из движка. Собирать её
  здесь означало бы воспроизвести ровно тот класс ошибок, ради которого
  движок и отдаёт готовый HTML.

Контракт (см. kohexa-photo-index/demandes/LISEZ-MOI.md):
  заявка   demandes/champagnenow-{дата}.json  → {"project", "requests": [...]}
  ответ    catalogue.json[request_id]         → {"status", "candidates": [...]}
  ключ     champagnenow-{slug}-{role}

Ответ асинхронный. Потребитель обязан уметь опубликовать страницу без фото и
подставить его вторым проходом — синхронного ожидания в контракте нет.
"""

import json
from pathlib import Path

# Пути — абсолютные, не относительные от pipeline.py
PHOTO_INDEX_ROOT = Path(r"D:\бизнес\домены\kohexa-photo-index")
CATALOGUE        = PHOTO_INDEX_ROOT / "catalogue.json"
DEMANDES_DIR     = PHOTO_INDEX_ROOT / "demandes"

PROJECT = "champagnenow"   # BUDGET_KEY в vocabulaire/champagne.py
VOCAB   = "champagne"      # ключ в словаре vocabulaires движка

# Дефисы, не подчёркивания — так роли называются в контракте
ROLES = ("hero", "inline-1", "inline-2")

# ≥1.6 для hero: он же кормит баннер хаба, обрезаемый в 2.5:1
RATIO_MIN = {"hero": 1.6, "inline-1": 1.2, "inline-2": 1.2}

# Буфер кандидатов против отбраковки на вычитке. Для hero цена ошибки выше.
BUFFER = {"hero": 4, "inline-1": 2, "inline-2": 2}

# ── СТАТУСЫ ─────────────────────────────────────────────────────────────────

STATUS_PENDING = "pending"   # заявка в очереди
STATUS_READY   = "ready"     # кандидаты подготовлены
STATUS_FAILED  = "failed"    # движок не смог, причина в reason
STATUS_MISSING = "missing"   # заявки на это вообще не подавали


# ── КЛЮЧИ ───────────────────────────────────────────────────────────────────

def request_id(slug: str, role: str) -> str:
    """Идентификатор ответа в catalogue.json. Дефисы, не двоеточия."""
    return f"{PROJECT}-{slug}-{role}"


# ── ЧТЕНИЕ ──────────────────────────────────────────────────────────────────

def _load_catalogue() -> dict:
    if not CATALOGUE.exists():
        return {}
    with open(CATALOGUE, encoding="utf-8") as f:
        return json.load(f)


def photo(slug: str, role: str = "hero") -> dict:
    """
    Фотография для роли статьи.

    slug — slug статьи ("bollinger", "cote-des-blancs")
    role — "hero" | "inline-1" | "inline-2"

    Возвращает:
      url         — hotlink на images.unsplash.com с параметрами рендера
      credit_html — готовая атрибуция от движка (не собирается здесь)
      legende     — ручная подпись, если её писали; иначе пустая строка
      ratio       — соотношение сторон выбранного кадра
      photo_key   — устойчивый ключ фото в реестре
      status      — ready | pending | failed | missing
      reason      — только при failed
    """
    entry = _load_catalogue().get(request_id(slug, role))

    if entry is None:
        return _empty(STATUS_MISSING)

    status = entry.get("status", STATUS_PENDING)
    if status != STATUS_READY:
        result = _empty(status)
        if entry.get("reason"):
            result["reason"] = entry["reason"]
        return result

    candidates = entry.get("candidates") or []
    if not candidates:
        # ready без кандидатов — противоречие в ответе, трактуем как отсутствие
        return _empty(STATUS_FAILED, reason="ready_without_candidates")

    # Первый кандидат — тот, который вернул бы простой отбор; остальные буфер
    best = candidates[0]
    return {
        "url":         best.get("url", ""),
        "credit_html": best.get("credit_html", ""),
        "legende":     best.get("legende", ""),
        "ratio":       best.get("ratio"),
        "photo_key":   best.get("photo_key", ""),
        "status":      STATUS_READY,
    }


def photos_for(slug: str) -> dict:
    """Все роли статьи разом: {role: результат photo()}."""
    return {role: photo(slug, role) for role in ROLES}


def _empty(status: str, reason: str = "") -> dict:
    result = {
        "url":         None,
        "credit_html": "",
        "legende":     "",
        "ratio":       None,
        "photo_key":   "",
        "status":      status,
    }
    if reason:
        result["reason"] = reason
    return result


# ── РЕНДЕР ──────────────────────────────────────────────────────────────────

def render_image_block(slug: str, role: str = "hero", alt: str = "",
                       css_class: str = "art-image") -> str:
    """
    Готовый HTML-блок для шаблона.

    Пока статус не ready — возвращает пустую строку: страница публикуется без
    фотографии, а не с плейсхолдером. Плейсхолдер пришлось бы вычищать вторым
    проходом, пустота исчезает сама.
    """
    result = photo(slug, role)
    if result["status"] != STATUS_READY or not result["url"]:
        return ""

    caption = result["legende"]
    credit = result["credit_html"]
    # Подпись и атрибуция — разные вещи: подпись описывает кадр, атрибуция
    # обязательна по лицензии. Атрибуция не опускается никогда.
    inner = f"{caption} {credit}".strip() if caption else credit

    return (
        f'<figure class="{css_class}">'
        f'<img src="{result["url"]}" alt="{alt}" loading="lazy" />'
        f'<figcaption class="art-image-caption">{inner}</figcaption>'
        f'</figure>'
    )


# ── ЗАЯВКИ ──────────────────────────────────────────────────────────────────

def build_request(slug: str, role: str, subniche: str, section: str = "",
                  wine_type: str = None, priority_batch: str = "",
                  backfill: bool = False) -> dict:
    """
    Одна запись в requests[] заявки.

    subniche движок кладёт и в page["slug"], и в page["title_hint"] — именно по
    нему распознаются регион и стиль. Поэтому это не косметическое поле:
    от него зависит, что попадёт в отбор.

    wine_type передаётся движку как type_force. Значение, которого нет в
    TYPE_MARKERS, забанило бы маркеры ВСЕХ типов и обнулило вивьер, поэтому
    вызывающий обязан передавать только известный ключ либо None.
    """
    request = {
        "request_id":       request_id(slug, role),
        "subniche":         subniche,
        "role":             role,
        "vocab":            VOCAB,
        "quantity_needed":  1,
        "quantity_buffer":  BUFFER.get(role, 2),
        "aspect_ratio_min": RATIO_MIN.get(role, 1.2),
        "backfill":         backfill,
    }
    if section:
        request["section"] = section
    if wine_type:
        request["wine_type"] = wine_type
    if priority_batch:
        request["priority_batch"] = priority_batch
    return request


def write_demande(requests: list, date_iso: str) -> Path:
    """Кладёт заявку в demandes/. Один файл на проект и партию."""
    DEMANDES_DIR.mkdir(parents=True, exist_ok=True)
    path = DEMANDES_DIR / f"{PROJECT}-{date_iso}.json"
    payload = {"project": PROJECT, "requests": requests}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return path


# ── СВОДКА ──────────────────────────────────────────────────────────────────

def summary(slugs: list) -> dict:
    """Сколько ролей в каком статусе — чтобы видеть готовность до рендера."""
    counts = {STATUS_READY: 0, STATUS_PENDING: 0,
              STATUS_FAILED: 0, STATUS_MISSING: 0}
    for slug in slugs:
        for result in photos_for(slug).values():
            counts[result["status"]] = counts.get(result["status"], 0) + 1
    return counts


if __name__ == "__main__":
    import sys

    probe = sys.argv[1:] or ["cote-des-blancs", "krug", "reims-guide"]
    print(f"Каталог: {CATALOGUE}")
    print(f"существует: {CATALOGUE.exists()}\n")
    for slug in probe:
        print(slug)
        for role, result in photos_for(slug).items():
            note = result.get("reason", "")
            url = (result["url"] or "")[:60]
            print(f"  {role:<9} {result['status']:<8} {url}{note}")
