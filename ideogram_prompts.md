# Промпты баннеров разделов — Champagne.now

Формат: `slug: промпт`. Пустые строки и строки с `#` игнорируются.
Slug должен совпадать с каталогом раздела в `en/` — файл сохранится как `banners/banner-{slug}.jpg`.

Генерация разовая:

    python scripts/generate_banners.py --dry-run
    python scripts/generate_banners.py

Промпты ниже — черновики, отредактируйте под нужный визуальный язык до первого запуска.
Единый стиль важнее детализации: баннеры стоят рядом в навигации.

houses: wide editorial banner, historic Champagne house facade in Reims, limestone and wrought iron, low winter sun, muted gold and deep charcoal palette, no text, cinematic

terroir: wide editorial banner, Champagne vineyard rows on chalk slopes at dawn, mist between vines, restrained gold and green palette, no text, cinematic

visit: wide editorial banner, cobbled street in Epernay at golden hour, Avenue de Champagne facades, warm amber light, no text, cinematic

history: wide editorial banner, antique champagne cellar with candlelight, aged oak and riddling racks, sepia and gold palette, no text, cinematic

in-the-cellar: wide editorial banner, deep chalk crayeres tunnel lined with aging bottles, cool blue-grey light with warm lamp accents, no text, cinematic

wine-styles: wide editorial banner, row of champagne glasses with varied hues from pale gold to rose, dark backdrop, soft rim light, no text, cinematic

food-and-champagne: wide editorial banner, oysters and champagne flute on dark slate, cold highlights and gold reflections, overhead composition, no text, cinematic
