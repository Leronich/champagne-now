#!/usr/bin/env python3
"""
fix_fonts.py — применяет правильные размеры шрифтов ко всем HTML файлам сайта.

Запуск:
  python fix_fonts.py --dir "D:\бизнес\домены\Champagne.now\champagne-site"
"""

import re
import argparse
from pathlib import Path

# Целевые размеры шрифтов
FONT_RULES = """
/* ── GLOBAL TYPOGRAPHY — Champagne.now ── */
.label, .aff-label, .art-badge, .wca-style, .ps-name,
.num-label, .eat-addr, .rc-type, .q-step,
.result-style, .result-eyebrow { font-size: 12px !important; }

.nav-links a, .breadcrumb-inner, .inline-quiz-link,
.quiz-strip-meta, .quiz-strip-meta b, .art-meta,
.hero-eyebrow span, .scroll-cue, .region-card .more,
.wine-card .roman, .wine-card .index, .rail-hint,
.q-opt-sub, .intro-label, .intro-meta { font-size: 13px !important; }

.aff-link, .visit-address, .visit-meta, .wca-link,
.grower-link, .pi-link, .wca-price, .pi-price, .pi-cuvee,
.ms-practical, .eat-why, .ps-why, .pc-price,
.cb-text, .disclaimer-bar, .ag-disclaimer,
.ag-links, .foot { font-size: 15px !important; }
"""

def fix_html(path: Path) -> bool:
    content = path.read_text(encoding='utf-8')
    original = content
    changed = False

    # 1. Add global font rules if not already present
    if 'GLOBAL TYPOGRAPHY' not in content:
        content = content.replace('</head>', f'<style>{FONT_RULES}</style>\n</head>')
        changed = True

    # 2. Fix disclaimer-bar if present (was doubled to 23px+)
    content = re.sub(r'(\.disclaimer-bar\s*\{[^}]*?)font-size:\s*\d+px', 
                     r'\g<1>font-size: 13px', content)

    if content != original:
        path.write_text(content, encoding='utf-8')
        return True
    return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dir', required=True, help='Path to champagne-site root')
    args = parser.parse_args()

    root = Path(args.dir)
    html_files = list(root.rglob('*.html'))
    
    updated = 0
    for f in html_files:
        if fix_html(f):
            print(f"  ✓ {f.relative_to(root)}")
            updated += 1
        
    print(f"\nDone. Updated {updated}/{len(html_files)} files.")


if __name__ == '__main__':
    main()
