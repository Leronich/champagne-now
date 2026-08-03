import os
import shutil
import glob

# Папки где index.html НУЖЕН — не трогаем
KEEP_AS_INDEX = {
    '',           # корень
    'en',
    'fr', 
    'en/quiz',
    'fr/quiz',
    'en/legal',
    'fr/legal',
    'en/contact',
    'fr/contact',
    'en/editorial',
    'fr/editorial',
    'en/terroir',
    'fr/terroir',
    'en/houses',
    'fr/houses',
    'en/history',
    'fr/history',
    'en/wine-styles',
    'fr/wine-styles',
    'en/food-and-champagne',
    'fr/food-and-champagne',
    'en/in-the-cellar',
    'fr/in-the-cellar',
    'en/visit',
    'fr/visit',
    'en/journal',
    'fr/journal',
}

base = os.path.dirname(os.path.abspath(__file__))
moved = 0
skipped = 0

# Найти все index.html
for root, dirs, files in os.walk(base):
    # Пропускаем .git
    dirs[:] = [d for d in dirs if d != '.git' and d != 'static']
    
    if 'index.html' not in files:
        continue
    
    rel = os.path.relpath(root, base).replace('\\', '/')
    
    # Пропускаем если это папка из KEEP_AS_INDEX
    if rel in KEEP_AS_INDEX or rel == '.':
        skipped += 1
        continue
    
    # Название файла = название папки + .html
    folder_name = os.path.basename(root)
    parent = os.path.dirname(root)
    new_path = os.path.join(parent, folder_name + '.html')
    old_path = os.path.join(root, 'index.html')
    
    # Перемещаем файл
    shutil.move(old_path, new_path)
    print(f'  {rel}/index.html → {os.path.relpath(new_path, base)}')
    moved += 1
    
    # Удаляем пустую папку
    try:
        os.rmdir(root)
    except OSError:
        print(f'  [!] Папка не пуста, не удалена: {rel}')

print(f'\n✓ Перемещено: {moved} файлов')
print(f'  Пропущено (index нужен): {skipped} папок')
print(f'\nДалее:')
print(f'  1. Включи Pretty URLs в Cloudflare Pages → Settings → Build')
print(f'  2. git add -A')
print(f'  3. git commit -m "Flatten URL structure"')
print(f'  4. git push')
