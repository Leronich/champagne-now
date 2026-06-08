import os
import glob

STAY22_SCRIPT = '''<script>
(function (s, t, a, y, twenty, two) {
  s.Stay22 = s.Stay22 || {};
  s.Stay22.params = { lmaID: '6a26f659df1132ff5008cb9d' };
  twenty = t.createElement(a); two = t.getElementsByTagName(a)[0];
  twenty.async = 1; twenty.src = y; two.parentNode.insertBefore(twenty, two);
})(window, document, 'script', 'https://scripts.stay22.com/letmeallez.js');
</script>'''

base = os.path.dirname(os.path.abspath(__file__))
html_files = glob.glob(os.path.join(base, '**', '*.html'), recursive=True)

added = 0
skipped = 0

for path in sorted(html_files):
    with open(path, encoding='utf-8') as f:
        content = f.read()
    
    # Пропускаем если уже есть
    if 'stay22.com' in content:
        skipped += 1
        continue
    
    # Вставляем перед </body>
    if '</body>' in content:
        content = content.replace('</body>', STAY22_SCRIPT + '\n</body>')
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        added += 1

print(f'✓ Added Stay22 to {added} files')
print(f'  Skipped {skipped} files (already had Stay22)')
