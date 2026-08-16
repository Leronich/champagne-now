"""
scripts/build_hubs.py
Создаёт страницы разделов, на которые ссылается меню каждой статьи.

Зачем
-----
`/en/terroir/`, `/en/wine-styles/`, `/en/journal/` и ещё пятнадцать адресов
стоят в навигации 400+ раз, но ни одного из них не существует. Cloudflare
Pages отдаёт на неизвестный путь главную страницу с кодом 200, поэтому каждый
такой адрес превращался в очередную копию главной. Google завёл отчёт
«Страница является копией, канонический вариант не выбран пользователем» —
и был прав: у главной действительно нет canonical.

Порядок важен: хабы создаются ДО включения настоящего 404. Иначе главное меню
всех 113 страниц начнёт вести на ошибку — соft-дубликат хотя бы показывал
читателю что-то.

Баннеры разделов ставятся фоном там же, где и на статьях: houses и visit
исключены, потому что словарь запрещает генерацию для профилей домов и визитов
(«publish_without_image»), и хаб этого не отменяет.

    python scripts/build_hubs.py --dry-run
    python scripts/build_hubs.py
"""

import argparse
import html as H
import json
import re
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
BASE = "https://champagne.now"
BANNIERES = RACINE / "static" / "banners"

# раздел -> (заголовок en, заголовок fr, дека en, дека fr)
SECTIONS = {
    "terroir": ("The Region", "La Région",
                "Five subregions, one latitude. Chalk, cool weather and the villages that give Champagne its accents.",
                "Cinq sous-régions, une latitude. La craie, le climat frais et les villages qui donnent à la Champagne ses accents."),
    "houses": ("The Houses", "Les Maisons",
               "Grandes maisons and growers: who makes what, and why each tastes the way it does.",
               "Grandes maisons et récoltants : qui fait quoi, et pourquoi chacun a ce goût-là."),
    "wine-styles": ("The Wine", "Le Vin",
                    "Brut to demi-sec, blanc de blancs to rosé — the styles, and what separates them in the glass.",
                    "Du brut au demi-sec, du blanc de blancs au rosé — les styles, et ce qui les sépare dans le verre."),
    "in-the-cellar": ("In the Cellar", "En Cave",
                      "Second fermentation, riddling, dégorgement, dosage: what happens between harvest and cork.",
                      "Prise de mousse, remuage, dégorgement, dosage : ce qui se passe entre la vendange et le bouchon."),
    "history": ("History", "Histoire",
                "From a Benedictine monk to an appellation defended in court — how Champagne became Champagne.",
                "D'un moine bénédictin à une appellation défendue en justice — comment la Champagne est devenue la Champagne."),
    "visit": ("Visit", "Visiter",
              "Getting there, which cellars to book, when to go, and what the region asks of a visitor.",
              "S'y rendre, quelles caves réserver, quand venir, et ce que la région demande au visiteur."),
    "food-and-champagne": ("Food &amp; Champagne", "Accords",
                           "Oysters, aged comté, fried chicken: what champagne does at the table, and why.",
                           "Huîtres, comté affiné, poulet frit : ce que le champagne fait à table, et pourquoi."),
}

# Разделы, где сгенерированный баннер публиковать нельзя — то же правило,
# что и на статьях (vocabulaire/champagne.py: publish_without_image).
SANS_BANNIERE = {"houses", "visit"}

RE_TITRE = re.compile(r'<h1 class="art-title">(.*?)</h1>', re.S)
RE_DECK = re.compile(r'<p class="art-deck[^"]*">(.*?)</p>', re.S)
RE_LABEL = re.compile(r'<div class="art-eyebrow">\s*<span class="label">(.*?)</span>', re.S)


def texte(x):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", x)).strip()


def articles(langue, section):
    out = []
    for p in sorted((RACINE / langue / section).glob("*/index.html")):
        h = p.read_text(encoding="utf-8", errors="replace")
        t = RE_TITRE.search(h)
        d = RE_DECK.search(h)
        if not t:
            continue
        out.append({
            "url": f"/{langue}/{section}/{p.parent.name}/",
            "titre": texte(t.group(1)),
            "deck": texte(d.group(1))[:190] + "…" if d and len(texte(d.group(1))) > 190
                    else (texte(d.group(1)) if d else ""),
        })
    return out


# ── Перекрёстная ссылка на соседнее издание портфеля ────────────────────────
#
# Ставится только там, где тема действительно продолжается: еда и вино, стили
# вина, работа в погребе. На хабах про Шампань как место (terroir, houses,
# visit, history) её нет — отсылка к бургундским аппелласьонам там была бы не
# рекомендацией, а врезкой ради врезки.
#
# rel="noopener" без nofollow — сознательно: это редакционная рекомендация, а
# не оплаченная ссылка. hreflang="fr" стоит потому, что mon-caviste.fr
# франкоязычен, а блок висит на английских страницах: разметка обязана
# сказать читателю и роботу, на каком языке будет то, куда он идёт.
RENVOIS = {
    "food-and-champagne": (
        "For wine pairing beyond Champagne — Burgundy, Bordeaux, Loire — "
        '<a href="https://mon-caviste.fr" target="_blank" rel="noopener" hreflang="fr">Mon Caviste</a> '
        "covers the full spectrum of French appellations with the same editorial independence."),
    "wine-styles": (
        "Exploring French wines beyond the Champagne region? "
        '<a href="https://mon-caviste.fr" target="_blank" rel="noopener" hreflang="fr">Mon Caviste</a> '
        "is an independent editorial guide to French appellations, growers, and cellar vocabulary."),
    "in-the-cellar": (
        "The vocabulary of the cellar is not unique to Champagne. "
        '<a href="https://mon-caviste.fr" target="_blank" rel="noopener" hreflang="fr">Mon Caviste</a> '
        "follows the same techniques through the other French appellations, from vinification to bottle age."),
}


def renvoi(langue: str, section: str) -> str:
    """Сноска ставится только на английских хабах перечисленных разделов."""
    if langue != "en" or section not in RENVOIS:
        return ""
    return ('\n<div class="art-aside art-aside--editorial">\n'
            f'  <p>{RENVOIS[section]}</p>\n'
            "</div>\n")


def page(langue, section, titre, deck, items, alt_url):
    est_fr = langue == "fr"
    banniere = "" if section in SANS_BANNIERE else f"banner-{section}.jpg"
    if banniere and not (BANNIERES / banniere).exists():
        banniere = ""

    classe = "art-hero fade" + (" art-hero--illus" if banniere else "")
    style = f' style="--illus:url(/static/banners/{banniere})"' if banniere else ""
    marque = (f'    <span class="illus-mark">Illustration</span>\n' if banniere else "")

    cartes = "\n".join(
        f'      <a href="{a["url"]}" class="related-card fade" style="--d:{0.05*(i+1):.2f}s">\n'
        f'        <div class="rc-type">{H.escape(texte(titre))}</div>\n'
        f'        <div class="rc-title">{a["titre"]}</div>\n'
        f'        <span class="rc-arrow">→</span>\n'
        f'      </a>'
        for i, a in enumerate(items))

    fil = "Accueil" if est_fr else "Champagne.now"
    lang_bloc = (f'<div class="lang"><a href="{alt_url}">EN</a> · <b>FR</b></div>'
                 if est_fr else
                 f'<div class="lang"><b>EN</b> · <a href="{alt_url}">FR</a></div>')
    liste = ", ".join(a["titre"] for a in items[:6])

    schema = {
        "@context": "https://schema.org", "@type": "CollectionPage",
        "name": texte(titre), "description": texte(deck),
        "url": f"{BASE}/{langue}/{section}/",
        "publisher": {"@type": "Organization", "name": "Champagne.now", "url": BASE},
        "hasPart": [{"@type": "Article", "headline": a["titre"],
                     "url": BASE + a["url"]} for a in items],
    }

    return f"""<!doctype html>
<html lang="{langue}">
<head>
<meta charset="utf-8" />
<meta name='impact-site-verification' value='d9700790-fcb7-412a-8cb2-ae6a55ebdea5'>
<!-- cn-consent-default-v2: отказ по умолчанию, до любого трекера -->
<script>
window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments);}}
gtag('consent','default',{{'ad_storage':'denied','ad_user_data':'denied',
'ad_personalization':'denied','analytics_storage':'denied','wait_for_update':500}});
try{{var c=JSON.parse(localStorage.getItem('cn_consent')||'null');
if(c&&c.exp>Date.now()&&c.analytics===true){{gtag('consent','update',{{'analytics_storage':'granted'}});}}
}}catch(e){{}}
gtag('js',new Date());gtag('config','G-J8273H5YMH');
</script>
<link rel="stylesheet" href="/static/consent.css" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>{texte(titre)} — Champagne.now</title>
<meta name="description" content="{texte(deck)}" />
<link rel="canonical" href="{BASE}/{langue}/{section}/" />
<link rel="alternate" hreflang="en" href="{BASE}{'/en/' + section + '/' if est_fr else '/' + langue + '/' + section + '/'}" />
<link rel="alternate" hreflang="fr" href="{BASE}{'/' + langue + '/' + section + '/' if est_fr else '/fr/' + section + '/'}" />
<script type="application/ld+json">
{json.dumps(schema, ensure_ascii=False, indent=2)}
</script>
<link rel="preconnect" href="https://fonts.googleapis.com" />
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,300;0,400;0,500;0,600;0,700;1,300;1,400;1,500&family=EB+Garamond:ital,wght@0,400;0,500;1,400;1,500&display=swap" rel="stylesheet" />
<link rel="stylesheet" href="/static/styles.css" />
<link rel="stylesheet" href="/static/article.css" />
</head>
<body>

<nav class="nav" id="nav">
  <div class="nav-links">
    <a href="/{langue}/terroir/">{'La Région' if est_fr else 'The Region'}</a>
    <a href="/{langue}/wine-styles/">{'Le Vin' if est_fr else 'The Wine'}</a>
    <a href="/{langue}/journal/">Journal</a>
    <a href="/#quiz">Quiz</a>
  </div>
  <div class="wordmark"><a href="/">Champagne<span class="dot"></span>now</a></div>
  <div class="nav-right">
    {lang_bloc}
    <a href="/#quiz" class="res">{'Trouvez votre moment' if est_fr else 'Find Your Moment'}</a>
  </div>
</nav>

<div class="breadcrumb-bar">
  <div class="breadcrumb-inner">
    <a href="/">{fil}</a>
    <span class="bc-sep">·</span>
    <span>{texte(titre)}</span>
  </div>
</div>

<header class="{classe}"{style}>
  <div class="art-hero-inner">
    <div class="art-eyebrow"><span class="label">{'Rubrique' if est_fr else 'Section'}</span></div>
    <h1 class="art-title">{titre}</h1>
    <p class="art-deck">{deck}</p>
    <div class="art-meta">
      <span><b>{'Articles' if est_fr else 'Articles'}</b> {len(items)}</span>
    </div>
  </div>
{marque}</header>

<section class="related">
  <div class="related-inner">
    <div class="label fade">{'Tout la rubrique' if est_fr else 'Everything in this section'}</div>
    <div class="related-grid">
{cartes}
    </div>
  </div>
{renvoi(langue, section)}</section>

<section class="quiz-strip">
  <div class="quiz-strip-inner fade">
    <div class="label">{'Trouvez votre champagne' if est_fr else 'Find Your Champagne'}</div>
    <p class="quiz-strip-text">{'Sept questions sur votre soirée, votre humeur, la compagnie à table — et une bouteille choisie comme le ferait un sommelier.' if est_fr else 'Seven questions about your evening, your mood, the company at the table — and a bottle chosen the way a sommelier would.'}</p>
    <a href="/#quiz" class="btn btn--filled">{'Trouvez votre moment' if est_fr else 'Find your Champagne moment'}<span class="arrow"></span></a>
  </div>
</section>

<footer class="foot">
<div>© MMXXV Champagne.now · <i>Maison Indépendante</i></div>
<div class="center">Champagne · Now</div>
<div class="right">{'Boire avec lenteur · <i>Take your time</i>' if est_fr else 'Drink slowly · <i>Boire avec lenteur</i>'}</div>
</footer>
<script>
(function(){{
  const nav = document.getElementById('nav');
  window.addEventListener('scroll', ()=>{{
    nav.classList.toggle('scrolled', window.scrollY > 40);
  }}, {{passive:true}});
  const obs = new IntersectionObserver(entries=>{{
    entries.forEach(e=>{{ if(e.isIntersecting){{ e.target.classList.add('in'); obs.unobserve(e.target); }} }});
  }}, {{threshold:.1, rootMargin:'0px 0px -6% 0px'}});
  document.querySelectorAll('.fade').forEach(el=>obs.observe(el));
}})();
</script>
<script defer src="/static/consent.js"></script>
</body>
</html>
"""


def main() -> int:
    ap = argparse.ArgumentParser(description="Страницы разделов")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    faits = []
    for section, (t_en, t_fr, d_en, d_fr) in SECTIONS.items():
        for langue, titre, deck in (("en", t_en, d_en), ("fr", t_fr, d_fr)):
            items = articles(langue, section)
            if not items:
                print(f"  пропуск {langue}/{section}: статей нет")
                continue
            autre = f"/{'fr' if langue == 'en' else 'en'}/{section}/"
            html = page(langue, section, titre, deck, items, autre)
            chemin = RACINE / langue / section / "index.html"
            faits.append((f"/{langue}/{section}/", len(items), len(html)))
            if not args.dry_run:
                chemin.parent.mkdir(parents=True, exist_ok=True)
                chemin.write_text(html, encoding="utf-8")

    print(f"хабов: {len(faits)}")
    for url, n, taille in faits:
        print(f"  {url:<26} {n:>2} статей  {taille // 1024} КБ")
    if args.dry_run:
        print("\n--dry-run: ничего не записано.")
    return 0


if __name__ == "__main__":
    sys.exit(main())


# ── Журнал и французский контакт ────────────────────────────────────────────
#
# «Journal» стоит в меню каждой статьи (63 ссылки en + 62 fr) и никогда не
# существовал. Это не раздел с собственными статьями, а перечень всего — его и
# строим, группируя по разделам.

def journal(langue: str) -> str:
    est_fr = langue == "fr"
    blocs = []
    total = 0
    for section, (t_en, t_fr, _, _) in SECTIONS.items():
        items = articles(langue, section)
        if not items:
            continue
        total += len(items)
        nom = t_fr if est_fr else t_en
        cartes = "\n".join(
            f'      <a href="{a["url"]}" class="related-card fade" style="--d:{0.04*(i+1):.2f}s">\n'
            f'        <div class="rc-type">{texte(nom)}</div>\n'
            f'        <div class="rc-title">{a["titre"]}</div>\n'
            f'        <span class="rc-arrow">→</span>\n'
            f'      </a>' for i, a in enumerate(items))
        blocs.append(
            f'  <div class="related-inner">\n'
            f'    <div class="label fade"><a href="/{langue}/{section}/">{nom}</a></div>\n'
            f'    <div class="related-grid">\n{cartes}\n    </div>\n  </div>')

    titre = "Journal"
    deck = ("Tout ce que nous avons publié, par rubrique."
            if est_fr else "Everything we have published, by section.")
    autre = f"/{'fr' if langue == 'en' else 'en'}/journal/"
    lang_bloc = (f'<div class="lang"><a href="{autre}">EN</a> · <b>FR</b></div>' if est_fr
                 else f'<div class="lang"><b>EN</b> · <a href="{autre}">FR</a></div>')
    schema = {"@context": "https://schema.org", "@type": "CollectionPage",
              "name": "Journal", "description": deck,
              "url": f"{BASE}/{langue}/journal/",
              "publisher": {"@type": "Organization", "name": "Champagne.now", "url": BASE}}

    return f"""<!doctype html>
<html lang="{langue}">
<head>
<meta charset="utf-8" />
<meta name='impact-site-verification' value='d9700790-fcb7-412a-8cb2-ae6a55ebdea5'>
<!-- cn-consent-default-v2: отказ по умолчанию, до любого трекера -->
<script>
window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments);}}
gtag('consent','default',{{'ad_storage':'denied','ad_user_data':'denied',
'ad_personalization':'denied','analytics_storage':'denied','wait_for_update':500}});
try{{var c=JSON.parse(localStorage.getItem('cn_consent')||'null');
if(c&&c.exp>Date.now()&&c.analytics===true){{gtag('consent','update',{{'analytics_storage':'granted'}});}}
}}catch(e){{}}
gtag('js',new Date());gtag('config','G-J8273H5YMH');
</script>
<link rel="stylesheet" href="/static/consent.css" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Journal — Champagne.now</title>
<meta name="description" content="{deck}" />
<link rel="canonical" href="{BASE}/{langue}/journal/" />
<link rel="alternate" hreflang="en" href="{BASE}/en/journal/" />
<link rel="alternate" hreflang="fr" href="{BASE}/fr/journal/" />
<script type="application/ld+json">
{json.dumps(schema, ensure_ascii=False, indent=2)}
</script>
<link rel="preconnect" href="https://fonts.googleapis.com" />
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,300;0,400;0,500;0,600;0,700;1,300;1,400;1,500&family=EB+Garamond:ital,wght@0,400;0,500;1,400;1,500&display=swap" rel="stylesheet" />
<link rel="stylesheet" href="/static/styles.css" />
<link rel="stylesheet" href="/static/article.css" />
</head>
<body>

<nav class="nav" id="nav">
  <div class="nav-links">
    <a href="/{langue}/terroir/">{'La Région' if est_fr else 'The Region'}</a>
    <a href="/{langue}/wine-styles/">{'Le Vin' if est_fr else 'The Wine'}</a>
    <a href="/{langue}/journal/">Journal</a>
    <a href="/#quiz">Quiz</a>
  </div>
  <div class="wordmark"><a href="/">Champagne<span class="dot"></span>now</a></div>
  <div class="nav-right">
    {lang_bloc}
    <a href="/#quiz" class="res">{'Trouvez votre moment' if est_fr else 'Find Your Moment'}</a>
  </div>
</nav>

<div class="breadcrumb-bar">
  <div class="breadcrumb-inner">
    <a href="/">{'Accueil' if est_fr else 'Champagne.now'}</a>
    <span class="bc-sep">·</span>
    <span>Journal</span>
  </div>
</div>

<header class="art-hero fade">
  <div class="art-hero-inner">
    <div class="art-eyebrow"><span class="label">{'Sommaire' if est_fr else 'Index'}</span></div>
    <h1 class="art-title">{titre}</h1>
    <p class="art-deck">{deck}</p>
    <div class="art-meta"><span><b>Articles</b> {total}</span></div>
  </div>
</header>

<section class="related">
{chr(10).join(blocs)}
</section>

<footer class="foot">
<div>© MMXXV Champagne.now · <i>Maison Indépendante</i></div>
<div class="center">Champagne · Now</div>
<div class="right">{'Boire avec lenteur · <i>Take your time</i>' if est_fr else 'Drink slowly · <i>Boire avec lenteur</i>'}</div>
</footer>
<script>
(function(){{
  const nav = document.getElementById('nav');
  window.addEventListener('scroll', ()=>{{
    nav.classList.toggle('scrolled', window.scrollY > 40);
  }}, {{passive:true}});
  const obs = new IntersectionObserver(entries=>{{
    entries.forEach(e=>{{ if(e.isIntersecting){{ e.target.classList.add('in'); obs.unobserve(e.target); }} }});
  }}, {{threshold:.1, rootMargin:'0px 0px -6% 0px'}});
  document.querySelectorAll('.fade').forEach(el=>obs.observe(el));
}})();
</script>
<script defer src="/static/consent.js"></script>
</body>
</html>
"""
