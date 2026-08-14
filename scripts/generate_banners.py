"""
scripts/generate_banners.py
Генерация статичных баннеров разделов через Ideogram 3.0.

РАЗОВЫЙ СКРИПТ. Не подключён к ежедневному пайплайну и не должен быть подключён:
баннеры хабов статичны, генерируются один раз и не пересобираются при публикации статей.
Запуск только вручную:

    python scripts/generate_banners.py --dry-run     # посмотреть план, ничего не тратя
    python scripts/generate_banners.py               # сгенерировать недостающие
    python scripts/generate_banners.py --force       # перегенерировать всё

Контракт:
  ideogram_prompts.md  →  static/banners/banner-{slug}.jpg  →  URL для шаблонов хабов

Файлы кладутся прямо в static/ и раздаются Cloudflare Pages вместе с остальным сайтом —
отдельного медиа-хранилища не требуется.

Общую квоту фотопайплайна (kohexa-photo-index) не трогает: прямой вызов Ideogram,
никакого резервирования, никакой конкуренции с mon-caviste / dedicawine.

ВАЖНО: Ideogram отдаёт крупные JPEG (~1.2 МБ на 1536x512). Перед публикацией
пережимайте — ориентир ~150 КБ при quality 82-92.
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

import requests

# ── ПУТИ ────────────────────────────────────────────────────────────────────

REPO_ROOT   = Path(__file__).resolve().parent.parent
PROMPTS_MD  = REPO_ROOT / "ideogram_prompts.md"
BANNERS_DIR = REPO_ROOT / "static" / "banners"

# Манифест держим вне static/ — иначе он раздавался бы вместе с сайтом
MANIFEST = REPO_ROOT / "banners.json"

# .env лежит на уровень выше репозитория и называется .env.txt
DEFAULT_ENV = REPO_ROOT.parent / ".env.txt"

# Публичный префикс, под которым static/ раздаётся Pages
SITE_BASE = "https://champagne.now"
PUBLIC_PREFIX = "/static/banners"

# ── API ─────────────────────────────────────────────────────────────────────

IDEOGRAM_URL = "https://api.ideogram.ai/v1/ideogram-v3/generate"

# 3x1 — широкий баннер под шапку хаба. Меняется флагом --aspect.
DEFAULT_ASPECT = "3x1"
DEFAULT_SPEED = "DEFAULT"
DEFAULT_STYLE = "DESIGN"

TIMEOUT_GENERATE = 180
TIMEOUT_TRANSFER = 120


# ── ENV ─────────────────────────────────────────────────────────────────────

def load_env(env_path: Path) -> dict:
    """Минимальный парсер .env — без зависимости от python-dotenv."""
    if not env_path.exists():
        die(f"не найден файл окружения: {env_path}\n"
            f"       укажите путь явно через --env")

    env = {}
    for line in env_path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key.strip()] = value.strip().strip('"').strip("'")
    return env


# ── ПРОМПТЫ ─────────────────────────────────────────────────────────────────

# Формат строки в ideogram_prompts.md:
#   slug: текст промпта
# Допускаются markdown-списки ("- slug: ..."), комментарии (#) и пустые строки.
PROMPT_LINE = re.compile(r"^\s*(?:[-*]\s*)?([a-z0-9][a-z0-9-]*)\s*:\s*(.+?)\s*$")
# Строка «похожа на промпт, но битая» — только про такие имеет смысл ругаться.
# Обычная проза в шапке файла отсеивается молча.
SLUG_START = re.compile(r"^\s*(?:[-*]\s*)?[a-z0-9][a-z0-9-]*\s*:")


def read_prompts(path: Path) -> list:
    """Читает ideogram_prompts.md построчно → [{'slug':..., 'prompt':...}]."""
    if not path.exists():
        die(f"не найден {path}\n"
            f"       создайте файл со строками вида:\n"
            f"         houses: wide editorial banner, chalk cellar, gold light\n"
            f"         terroir: wide banner, Champagne vineyard rows at dawn")

    prompts, seen, bad = [], set(), []
    for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue

        match = PROMPT_LINE.match(line)
        if not match:
            if SLUG_START.match(line):
                bad.append((lineno, line))
            continue

        slug, prompt = match.group(1), match.group(2)
        if slug in seen:
            die(f"{path.name}:{lineno}: slug '{slug}' повторяется")
        seen.add(slug)
        prompts.append({"slug": slug, "prompt": prompt})

    for lineno, line in bad:
        warn(f"{path.name}:{lineno}: пропущена строка (нет 'slug: промпт') — {line[:60]}")

    if not prompts:
        die(f"{path.name}: не найдено ни одной валидной строки")
    return prompts


# ── IDEOGRAM ────────────────────────────────────────────────────────────────

def generate(prompt: str, api_key: str, aspect: str, speed: str, style: str) -> str:
    """Вызывает Ideogram 3.0 и возвращает временный URL картинки."""
    response = requests.post(
        IDEOGRAM_URL,
        headers={"Api-Key": api_key},
        # v3 принимает multipart/form-data, не JSON
        files={
            "prompt":           (None, prompt),
            "aspect_ratio":     (None, aspect),
            "rendering_speed":  (None, speed),
            "style_type":       (None, style),
            "num_images":       (None, "1"),
        },
        timeout=TIMEOUT_GENERATE,
    )
    if response.status_code != 200:
        raise RuntimeError(f"Ideogram {response.status_code}: {response.text[:300]}")

    data = response.json().get("data") or []
    if not data:
        raise RuntimeError(f"Ideogram вернул пустой data: {response.text[:300]}")

    entry = data[0]
    if entry.get("is_image_safe") is False:
        raise RuntimeError("Ideogram пометил изображение как небезопасное")

    url = entry.get("url")
    if not url:
        raise RuntimeError(f"в ответе нет url: {json.dumps(entry)[:300]}")
    return url


def download(url: str, dest: Path) -> int:
    """Ссылки Ideogram живут ограниченное время — сохраняем немедленно."""
    response = requests.get(url, timeout=TIMEOUT_TRANSFER)
    response.raise_for_status()

    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(response.content)
    return len(response.content)


# ── МАНИФЕСТ ────────────────────────────────────────────────────────────────

def load_manifest() -> dict:
    if not MANIFEST.exists():
        return {}
    try:
        return json.loads(MANIFEST.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        warn(f"{MANIFEST.name} повреждён — начинаем с пустого")
        return {}


def save_manifest(manifest: dict) -> None:
    MANIFEST.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


# ── ВЫВОД ───────────────────────────────────────────────────────────────────

def warn(message: str) -> None:
    print(f"  ! {message}", file=sys.stderr)


def die(message: str) -> None:
    print(f"ОШИБКА: {message}", file=sys.stderr)
    sys.exit(1)


def public_url(slug: str) -> str:
    return f"{SITE_BASE}{PUBLIC_PREFIX}/banner-{slug}.jpg"


def print_urls(slugs: list) -> None:
    """Итоговая таблица для подстановки в шаблоны хабов."""
    present = [s for s in slugs if (BANNERS_DIR / f"banner-{s}.jpg").exists()]
    if not present:
        print("\nГотовых баннеров на диске нет.")
        return

    print("\n" + "=" * 78)
    print("URL для шаблонов хабов")
    print("=" * 78)
    width = max(len(s) for s in present)
    for slug in sorted(present):
        print(f"  {slug:<{width}}  {public_url(slug)}")
    print()


# ── MAIN ────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Разовая генерация баннеров хабов через Ideogram в static/banners/"
    )
    parser.add_argument("--env", type=Path, default=DEFAULT_ENV,
                        help=f"путь к .env (по умолчанию {DEFAULT_ENV})")
    parser.add_argument("--prompts", type=Path, default=PROMPTS_MD,
                        help="путь к ideogram_prompts.md")
    parser.add_argument("--aspect", default=DEFAULT_ASPECT,
                        help=f"соотношение сторон (по умолчанию {DEFAULT_ASPECT})")
    parser.add_argument("--speed", default=DEFAULT_SPEED,
                        choices=["TURBO", "DEFAULT", "QUALITY"],
                        help="rendering_speed Ideogram")
    parser.add_argument("--style", default=DEFAULT_STYLE,
                        choices=["AUTO", "GENERAL", "REALISTIC", "DESIGN", "FICTION"],
                        help="style_type Ideogram")
    parser.add_argument("--only", metavar="SLUG", action="append",
                        help="обработать только указанные slug (можно повторять)")
    parser.add_argument("--force", action="store_true",
                        help="перегенерировать даже то, что уже есть")
    parser.add_argument("--dry-run", action="store_true",
                        help="показать план, не вызывая API")
    args = parser.parse_args()

    prompts = read_prompts(args.prompts)
    if args.only:
        wanted = set(args.only)
        unknown = wanted - {p["slug"] for p in prompts}
        if unknown:
            die(f"нет таких slug в {args.prompts.name}: {', '.join(sorted(unknown))}")
        prompts = [p for p in prompts if p["slug"] in wanted]

    all_slugs = [p["slug"] for p in prompts]
    manifest = load_manifest()

    # Баннеры статичны: уже лежащее на диске не трогаем
    todo = [
        item for item in prompts
        if args.force or not (BANNERS_DIR / f"banner-{item['slug']}.jpg").exists()
    ]

    skipped = len(prompts) - len(todo)
    print(f"Промптов: {len(prompts)} | к обработке: {len(todo)} | пропущено готовых: {skipped}")

    if args.dry_run:
        for item in todo:
            print(f"  → banner-{item['slug']}.jpg  ({item['prompt'][:60]}…)")
        print("\n--dry-run: API не вызывался, ничего не потрачено.")
        print_urls(all_slugs)
        return 0

    if not todo:
        print("Всё уже сгенерировано. Для пересборки — --force.")
        print_urls(all_slugs)
        return 0

    env = load_env(args.env)
    ideogram_key = env.get("IDEOGRAM_API_KEY") or os.environ.get("IDEOGRAM_API_KEY")
    if not ideogram_key:
        die(f"IDEOGRAM_API_KEY не найден в {args.env}")

    failed = []
    for index, item in enumerate(todo, 1):
        slug, prompt = item["slug"], item["prompt"]
        local = BANNERS_DIR / f"banner-{slug}.jpg"
        print(f"\n[{index}/{len(todo)}] {slug}")

        try:
            print(f"  генерация ({args.aspect}, {args.speed}, {args.style})…")
            temp_url = generate(prompt, ideogram_key, args.aspect, args.speed, args.style)
            size = download(temp_url, local)
            print(f"  сохранено: {local.name} ({size // 1024} КБ)")

            manifest[slug] = {
                "prompt": prompt,
                "local": str(local.relative_to(REPO_ROOT)).replace("\\", "/"),
                "url": public_url(slug),
            }
            # пишем после каждого баннера — прерывание не теряет прогресс
            save_manifest(manifest)

        except Exception as error:
            warn(f"{slug}: {error}")
            failed.append(slug)

    print(f"\nГотово. Успешно: {len(todo) - len(failed)} | с ошибкой: {len(failed)}")
    if failed:
        print(f"Не удалось: {', '.join(failed)}")
    else:
        print("Не забудьте пережать новые файлы перед публикацией (~150 КБ).")

    print_urls(all_slugs)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
