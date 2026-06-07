#!/usr/bin/env python3
"""
fix_fonts2.py — принудительно обновляет типографику во всех HTML файлах.
"""
import argparse
from pathlib import Path

NEW_RULES = """<style>
/* GLOBAL TYPOGRAPHY — Champagne.now v2 */
.label, .aff-label, .art-badge, .wca-style, .ps-name,
.num-label, .eat-addr, .rc-type, .q-step,
.result-style, .result-eyebrow, .ag-links,
.intro-label, .intro-meta b { font-size: 12px !important; }

.nav-links a, .breadcrumb-inner, .inline-quiz-link,
.quiz-strip-meta, .quiz-strip-meta b, .art-meta,
.hero-eyebrow span, .scroll-cue, .region-card .more,
.wine-card .roman, .wine-card .index, .rail-hint,
.q-opt-sub, .intro-meta, .disclaimer-bar, .ag-disclaimer,
.ag-question, .cb-accept, .cb-decline { font-size: 13px !important; }

.aff-link, .visit-address, .visit-meta, .wca-link,
.grower-link, .pi-link, .wca-price, .pi-price, .pi-cuvee,
.ms-practical, .eat-why, .ps-why, .pc-price,
.cb-text, .foot, .foot .right { font-size: 15px !important; }
</style>"""

def fix_html(path: Path) -> bool:
    content = path.read_text(encoding='utf-8')
    
    # Remove old global typography block if exists
    import re
    content = re.sub(r'<style>\s*/\* GLOBAL TYPOGRAPHY.*?</style>\s*', '', content, flags=re.DOTALL)
    
    # Add new rules before </head>
    if '</head>' in content:
        content = content.replace('</head>', NEW_RULES + '\n</head>', 1)
        path.write_text(content, encoding='utf-8')
        return True
    return False

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dir', required=True)
    args = parser.parse_args()

    root = Path(args.dir)
    files = [f for f in root.rglob('*.html') if 'node_modules' not in str(f)]
    
    updated = 0
    for f in files:
        if fix_html(f):
            print(f"  ✓ {f.relative_to(root)}")
            updated += 1
    
    print(f"\nDone. Updated {updated}/{len(files)} files.")

if __name__ == '__main__':
    main()
