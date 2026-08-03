import os
import re
import glob
from datetime import datetime

BASE_DATE = "2025-06-01"  # datePublished для всех статей
MOD_DATE  = datetime.today().strftime("%Y-%m-%d")  # dateModified = сегодня

AUTHOR_BLOCK = ''',
  "author": {
    "@type": "Organization",
    "name": "Champagne.now Editorial",
    "url": "https://champagne.now/en/editorial/"
  },
  "datePublished": "''' + BASE_DATE + '''",
  "dateModified": "''' + MOD_DATE + '''"'''

# Byline HTML — вставляем после art-eyebrow и перед h1
BYLINE_EN = '    <div class="art-byline">Champagne.now Editorial</div>\n'
BYLINE_FR = '    <div class="art-byline">Rédaction Champagne.now</div>\n'

base = os.path.dirname(os.path.abspath(__file__))
html_files = glob.glob(os.path.join(base, '**', '*.html'), recursive=True)

schema_fixed = 0
byline_added = 0
skipped = 0

for path in sorted(html_files):
    with open(path, encoding='utf-8') as f:
        content = f.read()

    original = content
    changed = False

    # 1. Fix Schema.org — add author, datePublished, dateModified
    if '"@type": "Article"' in content and '"author"' not in content:
        # Insert after publisher block closing }
        content = re.sub(
            r'("publisher"\s*:\s*\{[^}]+\})',
            r'\1' + AUTHOR_BLOCK,
            content,
            count=1
        )
        schema_fixed += 1
        changed = True

    # 2. Add byline after <h1 class="art-title">
    if 'art-byline' not in content and 'art-title' in content:
        lang = 'fr' if 'lang="fr"' in content[:200] else 'en'
        byline = BYLINE_FR if lang == 'fr' else BYLINE_EN
        content = content.replace(
            '    <h1 class="art-title">',
            byline + '    <h1 class="art-title">',
            1
        )
        byline_added += 1
        changed = True

    if changed:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
    else:
        skipped += 1

print(f'✓ Schema author added:  {schema_fixed} files')
print(f'✓ Byline added:         {byline_added} files')
print(f'  Skipped (no change):  {skipped} files')

# 3. Add editorial link to footer
footer_en_old = '<a href="/en/legal/terms/">Terms</a> · <a href="/en/legal/privacy/">Privacy</a> · <a href="/en/legal/affiliate/">Affiliate Disclosure</a>'
footer_en_new = '<a href="/en/legal/terms/">Terms</a> · <a href="/en/legal/privacy/">Privacy</a> · <a href="/en/legal/affiliate/">Affiliate Disclosure</a> · <a href="/en/editorial/">Editorial Standards</a>'

footer_fr_old = '<a href="/en/legal/terms/">Terms</a> · <a href="/en/legal/privacy/">Privacy</a> · <a href="/en/legal/affiliate/">Affiliate Disclosure</a>'
footer_fr_new = '<a href="/en/legal/terms/">Terms</a> · <a href="/en/legal/privacy/">Privacy</a> · <a href="/en/legal/affiliate/">Affiliate Disclosure</a> · <a href="/fr/editorial/">Charte Éditoriale</a>'

print("\nNote: run this script from the champagne-site root directory")
print("Then place editorial_en.html → en/editorial/index.html")
print("And editorial_fr.html → fr/editorial/index.html")
