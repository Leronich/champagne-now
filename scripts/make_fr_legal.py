"""
scripts/make_fr_legal.py
Французские юридические страницы: fr/legal/{cookies,confidentialite,conditions,affiliation}.

Зачем: у сайта 50 французских статей и ни одной юридической страницы
по-французски. Уведомление на языке, которого читатель не выбирал, — это
уведомление, которого нет; для французской аудитории и французского
регулятора это существенно.

Тексты описывают то, что код ДЕЛАЕТ, а не то, что принято писать. Проверено по
исходникам на 2026-08-14: GA4 с Consent Mode (по умолчанию denied), Stay22
грузится только после согласия, Impact — только мета-тег верификации без
скрипта и cookie, форм на сайте нет ни одной, выбор хранится в localStorage
шесть месяцев.

    python scripts/make_fr_legal.py --dry-run
    python scripts/make_fr_legal.py

Это не юридическое заключение: тексты описывают техническую реальность и
должны быть просмотрены юристом до того, как на них станут ссылаться.
"""

import argparse
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
DATE = "août 2026"

NAV = """<nav class="nav scrolled" id="nav">
  <div class="nav-links">
    <a href="/fr/terroir/">La Région</a>
    <a href="/fr/wine-styles/">Le Vin</a>
    <a href="/fr/journal/">Journal</a>
    <a href="/#quiz">Quiz</a>
  </div>
  <div class="wordmark"><a href="/">Champagne<span class="dot"></span>now</a></div>
  <div class="nav-right">
    <div class="lang">EN · <b>FR</b></div>
    <a href="/#quiz" class="res">Trouvez votre moment</a>
  </div>
</nav>"""

PIED = """<footer class="foot">
<div>© MMXXV Champagne.now · <i>Maison Indépendante</i></div>
<div class="center">Champagne · Now</div>
<div class="right">Boire avec lenteur · <i>Take your time</i></div>
</footer>"""

CONSENT_HEAD = """<!-- cn-consent-default-v2: отказ по умолчанию, до любого трекера -->
<script>
window.dataLayer=window.dataLayer||[];function gtag(){dataLayer.push(arguments);}
gtag('consent','default',{'ad_storage':'denied','ad_user_data':'denied',
'ad_personalization':'denied','analytics_storage':'denied','wait_for_update':500});
try{var c=JSON.parse(localStorage.getItem('cn_consent')||'null');
if(c&&c.exp>Date.now()&&c.analytics===true){gtag('consent','update',{'analytics_storage':'granted'});}
}catch(e){}
gtag('js',new Date());gtag('config','G-J8273H5YMH');
</script>
<link rel="stylesheet" href="/static/consent.css" />"""


def page(slug, en_slug, titre, description, corps):
    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8" />
<link rel="icon" href="/static/favicon.svg" type="image/svg+xml">
<link rel="icon" href="/static/favicon.png" sizes="32x32" type="image/png">
<link rel="apple-touch-icon" href="/static/apple-touch-icon.png">
{CONSENT_HEAD}
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>{titre} — Champagne.now</title>
<meta name="description" content="{description}" />
<meta name="robots" content="index,follow" />
<link rel="canonical" href="https://champagne.now/fr/legal/{slug}/" />
<link rel="alternate" hreflang="fr" href="https://champagne.now/fr/legal/{slug}/" />
<link rel="alternate" hreflang="en" href="https://champagne.now/en/legal/{en_slug}/" />
<link rel="preconnect" href="https://fonts.googleapis.com" />
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,300;0,400;0,500;1,300;1,400&family=EB+Garamond:ital,wght@0,400;0,500;1,400&display=swap" rel="stylesheet" />
<link rel="stylesheet" href="/static/styles.css" />
<link rel="stylesheet" href="/static/article.css" />
<link rel="stylesheet" href="/static/legal.css" />
</head>
<body>
{NAV}

<div class="legal-wrap">
  <div class="legal-header">
    <div class="label">Mentions légales</div>
    <h1>{titre}</h1>
    <p class="legal-date">Dernière mise à jour : {DATE}</p>
  </div>

  <div class="legal-body">
{corps}
  </div>

  <div class="legal-nav">
    <a href="/fr/legal/cookies/">Cookies</a> ·
    <a href="/fr/legal/confidentialite/">Confidentialité</a> ·
    <a href="/fr/legal/conditions/">Conditions</a> ·
    <a href="/fr/legal/affiliation/">Affiliation</a>
  </div>
</div>

{PIED}
<script defer src="/static/consent.js"></script>
</body>
</html>
"""


COOKIES = """
    <h2>Rien avant votre choix</h2>
    <p>Aucun traceur soumis à consentement n'est déposé tant que vous n'avez pas
    répondu au bandeau. La mesure d'audience est déclarée refusée par défaut
    (<i>Consent Mode</i>, <code>analytics_storage: denied</code>) et n'est
    activée qu'après un clic sur « Accepter ». Le script d'affiliation n'est
    chargé qu'au même moment.</p>

    <h2>Ce que nous déposons, et pourquoi</h2>
    <div class="cookie-table">
      <div class="ct-row"><span>Nom</span><span>Type</span><span>Finalité</span><span>Durée</span></div>
      <div class="ct-row"><span>cn_consent</span><span>Stockage local</span>
        <span>Conserve votre choix, pour ne pas vous le redemander à chaque page</span><span>6 mois</span></div>
      <div class="ct-row"><span>_ga, _ga_*</span><span>Mesure d'audience</span>
        <span>Google Analytics 4 — statistiques de fréquentation. Déposé uniquement après acceptation</span><span>2 ans</span></div>
      <div class="ct-row"><span>Stay22</span><span>Affiliation</span>
        <span>Attribution des liens vers des partenaires. Chargé uniquement après acceptation</span><span>Variable</span></div>
      <div class="ct-row"><span>Travelpayouts</span><span>Affiliation</span>
        <span>Réécriture et attribution des liens affiliés voyage. Chargé uniquement après acceptation</span><span>Variable</span></div>
    </div>
    <p><i>cn_consent</i> n'est pas un cookie mais une entrée de stockage local :
    il ne quitte jamais votre navigateur et n'est envoyé à aucun serveur. Il est
    nécessaire au respect de votre choix, et à ce titre exempté de consentement.</p>

    <h2>Revenir sur votre décision</h2>
    <p>Le lien <b>« Gérer les cookies »</b> en bas de chaque page rouvre le
    bandeau. Refuser après avoir accepté désactive immédiatement la mesure
    d'audience. Passé six mois, le choix expire et la question est reposée.</p>

    <h2>Responsables de traitement</h2>
    <p>Champagne.now pour le site ; Google Ireland Limited pour Google
    Analytics ; Stay22 Inc. et Travelpayouts pour les liens affiliés. Aucun
    autre tiers ne reçoit de données depuis ces pages.</p>
    <p>Le script Travelpayouts est distribué par son fournisseur sous une forme
    conçue pour s'exécuter avant tout le reste. Il est ici chargé depuis notre
    propre code, après acceptation seulement : si vous refusez, il n'est pas
    téléchargé du tout.</p>

    <h2>Ce que nous ne faisons pas</h2>
    <p>Pas de publicité ciblée, pas de revente de données, pas de suivi entre
    sites. Les paramètres publicitaires de Google restent refusés en toute
    circonstance, y compris après acceptation.</p>

    <h2>Contact</h2>
    <p>Une question sur ce document : <a href="/fr/contact/">nous écrire</a>.</p>
"""

CONFIDENTIALITE = """
    <h2>Ce que nous ne collectons pas</h2>
    <p>Ce site ne comporte aucun formulaire : ni compte, ni inscription, ni
    infolettre, ni commentaire. Nous ne vous demandons donc ni nom, ni adresse,
    ni courriel, et nous n'en conservons aucun.</p>

    <h2>Ce qui est collecté, si vous l'acceptez</h2>
    <p>Après acceptation du bandeau, Google Analytics 4 mesure la fréquentation :
    pages consultées, durée, provenance approximative, type d'appareil. Ces
    données sont traitées par Google Ireland Limited pour notre seul compte.
    Sans acceptation, rien n'est mesuré.</p>

    <h2>Liens affiliés</h2>
    <p>Certains liens mènent à des partenaires. S'ils sont activés, les scripts
    Stay22 et Travelpayouts permettent d'attribuer la visite. Le partenaire
    applique alors sa propre politique, sur laquelle nous n'avons pas la main.
    Ces deux scripts ne sont chargés qu'après acceptation du bandeau.</p>

    <h2>Hébergement</h2>
    <p>Le site est hébergé sur Cloudflare Pages. L'hébergeur traite les journaux
    techniques nécessaires à la remise des pages et à la sécurité, indépendamment
    de votre choix sur les traceurs.</p>

    <h2>Vos droits</h2>
    <p>Accès, rectification, effacement, opposition, portabilité : ces droits
    s'exercent auprès de nous pour ce que nous détenons — c'est-à-dire, en
    pratique, votre choix de traceurs et les statistiques agrégées. Vous pouvez
    aussi saisir la CNIL.</p>

    <h2>Durées</h2>
    <p>Choix de traceurs : 6 mois. Données Google Analytics : 2 ans. Aucune autre
    donnée n'est conservée par nos soins.</p>

    <h2>Contact</h2>
    <p><a href="/fr/contact/">Nous écrire</a>.</p>
"""

CONDITIONS = """
    <h2>Objet du site</h2>
    <p>Champagne.now est une publication éditoriale consacrée à la Champagne.
    Ce n'est pas une boutique : rien n'y est vendu, et aucune commande n'y est
    prise.</p>

    <h2>Contenu</h2>
    <p>Les textes sont fournis à titre informatif. Nous les voulons exacts et
    les corrigeons quand ils ne le sont pas, sans pouvoir garantir qu'ils le
    soient à chaque instant. Ils ne constituent ni un conseil professionnel, ni
    une recommandation d'achat.</p>

    <h2>Propriété</h2>
    <p>Les textes et les éléments graphiques sont la propriété de Champagne.now.
    Les photographies proviennent de leurs auteurs respectifs et sont créditées
    à l'endroit où elles figurent.</p>

    <h2>Liens externes</h2>
    <p>Les liens sortants sont proposés pour leur intérêt. Nous ne maîtrisons ni
    leur contenu ni leur devenir.</p>

    <h2>Alcool</h2>
    <p>Ce site parle de vin. Sa lecture s'adresse aux personnes en âge de
    consommer de l'alcool dans leur pays de résidence. L'abus d'alcool est
    dangereux pour la santé ; à consommer avec modération.</p>

    <h2>Modifications</h2>
    <p>Ces conditions peuvent évoluer. La date en tête indique la dernière
    révision.</p>
"""

AFFILIATION = """
    <h2>Ce que cela signifie</h2>
    <p>Certains liens de ce site sont des liens affiliés : si vous passez par
    eux et effectuez un achat, nous pouvons percevoir une commission. Le prix
    que vous payez est identique.</p>

    <h2>Ce que cela ne change pas</h2>
    <p>Le choix éditorial précède le lien, jamais l'inverse. Une maison n'est ni
    citée ni omise selon qu'elle rémunère un programme d'affiliation. Rien sur
    ce site n'est un contenu sponsorisé.</p>

    <h2>Techniquement</h2>
    <p>L'attribution passe par Stay22, chargé uniquement après acceptation du
    bandeau. Si vous refusez, les liens continuent de fonctionner et mènent au
    même endroit : ils ne sont simplement plus attribués.</p>

    <h2>Programmes</h2>
    <p>Nous participons à des programmes d'affiliation de marchands de vin et de
    services de voyage. La liste évolue ; ce document est mis à jour en
    conséquence.</p>

    <h2>Contact</h2>
    <p>Une question sur ce point : <a href="/fr/contact/">nous écrire</a>.</p>
"""

PAGES = [
    ("cookies", "cookies", "Politique cookies",
     "Ce que Champagne.now dépose comme traceurs, à quelles fins, et comment revenir sur votre choix.",
     COOKIES),
    ("confidentialite", "privacy", "Politique de confidentialité",
     "Quelles données Champagne.now traite, lesquelles il ne collecte pas, et comment exercer vos droits.",
     CONFIDENTIALITE),
    ("conditions", "terms", "Conditions d'utilisation",
     "Conditions d'utilisation du site éditorial Champagne.now.",
     CONDITIONS),
    ("affiliation", "affiliate", "Divulgation d'affiliation",
     "Comment Champagne.now utilise les liens affiliés et ce que cela ne change pas.",
     AFFILIATION),
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Французские юридические страницы")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    for slug, en_slug, titre, desc, corps in PAGES:
        chemin = RACINE / "fr" / "legal" / slug / "index.html"
        html = page(slug, en_slug, titre, desc, corps)
        etat = "существует" if chemin.exists() else "новая"
        print(f"  {etat:<11} fr/legal/{slug}/index.html  ({len(html)} байт)")
        if not args.dry_run:
            chemin.parent.mkdir(parents=True, exist_ok=True)
            chemin.write_text(html, encoding="utf-8")

    if args.dry_run:
        print("\n--dry-run: ничего не записано.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
