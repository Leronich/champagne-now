import re
import os
import glob

# TYPOGRAPHY SPEC — точечные замены по селектору
# Формат: (селектор_подстрока, старый_размер, новый_размер)
FIXES = [
    # → 12px
    ('.label',              r'font-size\s*:\s*10(?:\.5)?px', 'font-size:12px'),
    ('.aff-label',          r'font-size\s*:\s*10(?:\.5)?px', 'font-size:12px'),
    ('.art-badge',          r'font-size\s*:\s*10(?:\.5)?px', 'font-size:12px'),
    ('.wca-style',          r'font-size\s*:\s*11px',          'font-size:12px'),
    ('.ps-name',            r'font-size\s*:\s*10(?:\.5)?px', 'font-size:12px'),
    ('.num-label',          r'font-size\s*:\s*10(?:\.5)?px', 'font-size:12px'),
    ('.eat-addr',           r'font-size\s*:\s*13px',          'font-size:12px'),
    ('.rc-type',            r'font-size\s*:\s*13px',          'font-size:12px'),
    ('.result-style',       r'font-size\s*:\s*10(?:\.5)?px', 'font-size:12px'),
    ('.result-eyebrow',     r'font-size\s*:\s*10(?:\.5)?px', 'font-size:12px'),

    # → 13px
    ('.q-step',             r'font-size\s*:\s*10\.5px',       'font-size:13px'),
    ('.intro-meta b',       r'font-size\s*:\s*10(?:\.5)?px', 'font-size:13px'),
    ('.nav-links a',        r'font-size\s*:\s*10\.5px',       'font-size:13px'),
    ('.breadcrumb-inner',   r'font-size\s*:\s*11px',          'font-size:13px'),
    ('.inline-quiz-link',   r'font-size\s*:\s*11px',          'font-size:13px'),
    ('.quiz-strip-meta',    r'font-size\s*:\s*12px',          'font-size:13px'),
    ('.quiz-strip-meta b',  r'font-size\s*:\s*12px',          'font-size:13px'),
    ('.hero-eyebrow span',  r'font-size\s*:\s*11px',          'font-size:13px'),
    ('.scroll-cue',         r'font-size\s*:\s*10\.5px',       'font-size:13px'),
    ('.region-card .more',  r'font-size\s*:\s*11\.5px',       'font-size:13px'),
    ('.wine-card .roman',   r'font-size\s*:\s*12px',          'font-size:13px'),
    ('.wine-card .index',   r'font-size\s*:\s*12px',          'font-size:13px'),
    ('.rail-hint',          r'font-size\s*:\s*11px',          'font-size:13px'),
    ('.q-opt-sub',          r'font-size\s*:\s*11(?:\.5)?px', 'font-size:13px'),
    ('.ag-disclaimer',      r'font-size\s*:\s*11px',          'font-size:13px'),
    ('.ag-question',        r'font-size\s*:\s*11px',          'font-size:13px'),

    # → 15px
    ('.aff-link',           r'font-size\s*:\s*13px',          'font-size:15px'),
    ('.visit-address',      r'font-size\s*:\s*13px',          'font-size:15px'),
    ('.visit-meta',         r'font-size\s*:\s*13px',          'font-size:15px'),
    ('.wca-link',           r'font-size\s*:\s*13px',          'font-size:15px'),
    ('.grower-link',        r'font-size\s*:\s*13px',          'font-size:15px'),
    ('.pi-link',            r'font-size\s*:\s*13px',          'font-size:15px'),
    ('.wca-price',          r'font-size\s*:\s*13px',          'font-size:15px'),
    ('.pi-price',           r'font-size\s*:\s*13px',          'font-size:15px'),
    ('.pi-cuvee',           r'font-size\s*:\s*13px',          'font-size:15px'),
    ('.ms-practical',       r'font-size\s*:\s*13px',          'font-size:15px'),
    ('.ps-why',             r'font-size\s*:\s*13px',          'font-size:15px'),
    ('.pc-price',           r'font-size\s*:\s*13px',          'font-size:15px'),
    ('.cb-text',            r'font-size\s*:\s*13px',          'font-size:15px'),
    ('.foot',               r'font-size\s*:\s*12px',          'font-size:15px'),
]

def fix_css_file(path):
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()

    original = content
    changes = []

    for selector, old_pattern, new_value in FIXES:
        # Найти блок CSS для этого селектора
        # Ищем селектор, затем внутри его блока { } меняем font-size
        
        # Паттерн: селектор ... { ... font-size: Xpx ... }
        # Используем поиск блока после селектора
        escaped = re.escape(selector)
        
        # Найти все вхождения селектора в файле
        for m in re.finditer(escaped, content):
            start = m.start()
            # Найти открывающую скобку после селектора
            brace_open = content.find('{', start)
            if brace_open == -1:
                continue
            # Найти закрывающую скобку
            brace_close = content.find('}', brace_open)
            if brace_close == -1:
                continue
            
            block = content[brace_open:brace_close+1]
            new_block, n = re.subn(old_pattern, new_value, block)
            if n > 0:
                content = content[:brace_open] + new_block + content[brace_close+1:]
                changes.append(f'  {selector}: {new_value}')

    if content != original:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        return changes
    return []

def main():
    # Найти все CSS файлы
    base = os.path.dirname(os.path.abspath(__file__))
    css_files = glob.glob(os.path.join(base, '**', '*.css'), recursive=True)
    
    # Также HTML файлы (inline <style>)
    html_files = glob.glob(os.path.join(base, '**', '*.html'), recursive=True)
    
    all_files = css_files + html_files
    total_changes = 0
    
    for path in sorted(all_files):
        changes = fix_css_file(path)
        if changes:
            print(f'\n{os.path.relpath(path, base)}:')
            for c in changes:
                print(c)
            total_changes += len(changes)
    
    print(f'\n✓ Total: {total_changes} changes across {len(all_files)} files')

if __name__ == '__main__':
    main()
