import re
import os
import glob

# Эти два style-блока были добавлены fix_fonts.py — удаляем их
PATTERNS = [
    # Первый блок
    re.compile(
        r'<style>\s*/\* ── GLOBAL TYPOGRAPHY.*?</style>',
        re.DOTALL
    ),
    # Второй блок  
    re.compile(
        r'<style>\s*/\* GLOBAL TYPOGRAPHY.*?</style>',
        re.DOTALL
    ),
]

base = os.path.dirname(os.path.abspath(__file__))
html_files = glob.glob(os.path.join(base, '**', '*.html'), recursive=True)

fixed = 0
for path in sorted(html_files):
    with open(path, encoding='utf-8') as f:
        content = f.read()
    
    original = content
    for pattern in PATTERNS:
        content = pattern.sub('', content)
    
    if content != original:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f'Fixed: {os.path.relpath(path, base)}')
        fixed += 1

print(f'\n✓ Removed injected styles from {fixed} files')
