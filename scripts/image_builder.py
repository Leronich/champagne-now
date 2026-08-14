"""
champagne_render/image_builder.py
Тонкий клиент к kohexa-photo-index для сайта Champagne.now.

НЕ содержит:
- ключа Unsplash (он в kohexa-photo-index)
- логики скачивания
- собственной дедупликации

Контракт:
  photo(key, role, lang) -> {"url": str, "credit_html": str, "source": str, "status": str}
  request_photos(page_slug, page_type, lang) -> list[PhotoResult]
"""

import json
import os
from pathlib import Path
from typing import Optional
from datetime import date

# Пути — абсолютные, не относительные от pipeline.py
PHOTO_INDEX_ROOT = Path(r"D:\бизнес\домены\kohexa-photo-index")
CATALOGUE        = PHOTO_INDEX_ROOT / "catalogue.json"
DEMANDES_DIR     = PHOTO_INDEX_ROOT / "demandes"
VOCAB_MODULE     = "vocabulaire.champagne"

# Импорт словаря
from vocabulaire.champagne import PAGE_TYPE_RULES, ATTRIBUTION_TEMPLATES, ILLUSTRATION_LABEL

# ── СТАТУСЫ ─────────────────────────────────────────────────────────────────

STATUS_PENDING  = "pending"
STATUS_READY    = "ready"
STATUS_MISSING  = "missing"   # нет в каталоге — страница публикуется без фото
STATUS_IDEOGRAM = "ideogram"  # fallback к генерации, нужна маркировка


# ── ОСНОВНЫЕ ФУНКЦИИ ────────────────────────────────────────────────────────

def photo(key: str, role: str, lang: str = "en") -> dict:
    """
    Получить фото из каталога по ключу и роли.
    key  — slug статьи (например "bollinger", "cote-des-blancs")
    role — "hero" | "inline_1" | "inline_2"
    lang — "en" | "fr" (для локализации credit_html)

    Возвращает словарь с полями:
      url         — CDN URL изображения (или None если pending/missing)
      credit_html — готовый HTML атрибуции (Unsplash) или label (Ideogram)
      source      — "unsplash" | "ideogram" | None
      status      — "ready" | "pending" | "missing" | "ideogram"
    """
    catalogue = _load_catalogue()
    photo_key = f"{key}:{role}"

    if photo_key not in catalogue:
        return _pending_result(key, role)

    entry = catalogue[photo_key]
    source = entry.get("source", "unsplash")

    if source == "unsplash":
        return {
            "url":         entry["url"],
            "credit_html": _build_credit_html(entry, lang),
            "source":      "unsplash",
            "status":      STATUS_READY,
        }
    elif source == "ideogram":
        return {
            "url":         entry["url"],
            "credit_html": ILLUSTRATION_LABEL.get(lang, "Illustration"),
            "source":      "ideogram",
            "status":      STATUS_IDEOGRAM,
        }
    else:
        return _pending_result(key, role)


def request_photos(page_slug: str, page_type: str, lang: str = "en") -> list:
    """
    Положить заявку на фото для страницы в очередь kohexa-photo-index.
    Вызывается из render.py перед публикацией статьи.

    page_slug — slug страницы ("bollinger", "cote-des-blancs")
    page_type — тип из PAGE_TYPE_RULES ("house_profile", "terroir", ...)
    lang      — "en" | "fr"

    Возвращает список ролей с текущим статусом:
    [{"role": "hero", "status": "pending"}, ...]
    """
    rules = PAGE_TYPE_RULES.get(page_type, {})
    query_builder = rules.get("query_builder")

    if query_builder is None:
        return []

    queries = query_builder(page_slug)
    if not queries:
        # Нет терминов для поиска — пробуем общий fallback
        queries = [f"champagne {page_type.replace('_', ' ')}"]

    demande = {
        "project":    "champagnenow",
        "page_slug":  page_slug,
        "page_type":  page_type,
        "lang":       lang,
        "date":       date.today().isoformat(),
        "roles": {
            "hero":     {"queries": queries, "min_w": 1200, "min_h": 400},
            "inline_1": {"queries": queries, "min_w": 800,  "min_h": 400},
        },
        "avoid_synthetic": True,
        "fallback_to_ideogram": rules.get("fallback_to_ideogram", False),
        "min_candidates": rules.get("min_candidates", 3),
    }

    # Записать заявку
    DEMANDES_DIR.mkdir(parents=True, exist_ok=True)
    demande_path = DEMANDES_DIR / f"champagnenow-{page_slug}-{date.today().isoformat()}.json"
    with open(demande_path, "w", encoding="utf-8") as f:
        json.dump(demande, f, ensure_ascii=False, indent=2)

    return [
        {"role": "hero",     "status": STATUS_PENDING},
        {"role": "inline_1", "status": STATUS_PENDING},
    ]


def render_image_block(key: str, role: str, lang: str = "en",
                       alt: str = "", css_class: str = "art-image") -> str:
    """
    Готовый HTML-блок для вставки в шаблон.
    Если статус pending или missing — возвращает пустую строку (страница без фото).
    Если ideogram — рендерит с другим CSS классом и без attribution-ссылки на Unsplash.
    """
    result = photo(key, role, lang)

    if result["status"] in (STATUS_PENDING, STATUS_MISSING):
        return ""  # публикуем без фото, не с плейсхолдером

    if result["status"] == STATUS_IDEOGRAM:
        return (
            f'<figure class="{css_class} {css_class}--illustration">'
            f'<img src="{result["url"]}" alt="{alt}" loading="lazy" />'
            f'<figcaption class="art-image-caption art-image-caption--illustration">'
            f'{result["credit_html"]}'
            f'</figcaption>'
            f'</figure>'
        )

    # Unsplash — с attribution
    return (
        f'<figure class="{css_class}">'
        f'<img src="{result["url"]}" alt="{alt}" loading="lazy" />'
        f'<figcaption class="art-image-caption">'
        f'{result["credit_html"]}'
        f'</figcaption>'
        f'</figure>'
    )


# ── ВСПОМОГАТЕЛЬНЫЕ ────────────────────────────────────────────────────────

def _load_catalogue() -> dict:
    """Читает catalogue.json из kohexa-photo-index."""
    if not CATALOGUE.exists():
        return {}
    with open(CATALOGUE, encoding="utf-8") as f:
        return json.load(f)


def _build_credit_html(entry: dict, lang: str) -> str:
    """Строит локализованный attribution HTML для Unsplash-фото."""
    template = ATTRIBUTION_TEMPLATES.get(lang, ATTRIBUTION_TEMPLATES["en"])
    return template.format(
        photographer=entry.get("photographer_name", ""),
        photographer_url=entry.get("photographer_url", ""),
        photo_url=entry.get("photo_url", ""),
    )


def _pending_result(key: str, role: str) -> dict:
    return {
        "url":         None,
        "credit_html": "",
        "source":      None,
        "status":      STATUS_PENDING,
    }


# ── BATCH HELPER ────────────────────────────────────────────────────────────

def request_all_pages(pages: list, lang: str = "en") -> dict:
    """
    Подать заявки на фото для всех страниц сразу.
    pages — список словарей {"slug": str, "type": str, "lang": str}

    Возвращает сводку: {"slug": [роли со статусами]}
    """
    summary = {}
    for page in pages:
        slug      = page["slug"]
        page_type = page.get("type", "terroir")
        page_lang = page.get("lang", lang)
        results   = request_photos(slug, page_type, page_lang)
        summary[slug] = results
        print(f"  → {slug} ({page_type}): {len(results)} roles queued")
    return summary


if __name__ == "__main__":
    # Быстрая проверка — подать заявки на первые 5 страниц
    test_pages = [
        {"slug": "cote-des-blancs",   "type": "terroir",      "lang": "en"},
        {"slug": "bollinger",          "type": "house_profile", "lang": "en"},
        {"slug": "blanc-de-blancs",    "type": "wine_styles",   "lang": "en"},
        {"slug": "champagne-harvest",  "type": "in_the_cellar", "lang": "en"},
        {"slug": "epernay-guide",      "type": "visit",         "lang": "en"},
    ]
    print("Submitting photo requests to kohexa-photo-index...")
    summary = request_all_pages(test_pages)
    print(f"\nDone. {len(summary)} pages queued.")
    print("Check kohexa-photo-index/demandes/ for request files.")
