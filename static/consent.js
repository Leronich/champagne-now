/* consent.js — сбор и хранение согласия на трекеры.
 *
 * Почему файлом, а не инлайном на каждой странице: логика одна на 109
 * страниц, и правка формулировки в одном месте лучше, чем 109 расхождений.
 * Инлайном остаётся только Consent Mode по умолчанию — он обязан выполниться
 * ДО загрузки gtag.js, иначе счётчик успевает сработать.
 *
 * Что было до 2026-08-14 и почему это переписано:
 *   — gtag('config') стоял безусловно строкой 6 каждой страницы;
 *   — cbAccept() и cbDecline() обе только писали флаг в localStorage и
 *     прятали баннер, не трогая аналитику. «Отказаться» не отключало ничего;
 *   — баннер стоял на 1 странице из 101;
 *   — отозвать согласие было нельзя, срок хранения — бессрочный.
 *
 * Требования, под которые это написано (CNIL, цитаты в consent.css и в
 * политике cookies): согласие до размещения трекера, отказ так же прост, как
 * принятие, перечисление целей и ответственных, срок хранения выбора порядка
 * шести месяцев.
 */
(function () {
  "use strict";

  var CLE = "cn_consent";
  var DUREE = 182 * 24 * 60 * 60 * 1000;   // ~6 месяцев, ориентир CNIL
  var STAY22 = "6a26f659df1132ff5008cb9d";
  var TRAVELPAYOUTS = "https://emrldco.com/NTYyNTI4.js?t=562528";

  var FR = document.documentElement.lang === "fr";

  var T = FR ? {
    texte: "Nous déposons des traceurs à deux fins : <b>mesure d'audience</b> " +
           "et <b>attribution des liens affiliés</b>. Aucun ne se déclenche " +
           "avant votre choix.",
    parties: "Responsables de traitement : Champagne.now, Google Ireland Ltd " +
             "(Google Analytics), Stay22 Inc. et Travelpayouts (liens affiliés).",
    liens: [["/fr/legal/cookies/", "Politique cookies"],
            ["/fr/legal/confidentialite/", "Confidentialité"],
            ["/fr/legal/affiliation/", "Affiliation"]],
    ok: "Accepter", non: "Refuser", gerer: "Gérer les cookies"
  } : {
    texte: "We set trackers for two purposes: <b>audience measurement</b> and " +
           "<b>affiliate link attribution</b>. Neither runs before you choose.",
    parties: "Data controllers: Champagne.now, Google Ireland Ltd " +
             "(Google Analytics), Stay22 Inc. and Travelpayouts (affiliate links).",
    liens: [["/en/legal/cookies/", "Cookie Policy"],
            ["/en/legal/privacy/", "Privacy"],
            ["/en/legal/affiliate/", "Affiliate Disclosure"]],
    ok: "Accept", non: "Refuse", gerer: "Manage cookies"
  };

  function lire() {
    try {
      var c = JSON.parse(localStorage.getItem(CLE) || "null");
      // Просроченный выбор — как отсутствующий: спрашиваем заново.
      return (c && c.exp > Date.now()) ? c : null;
    } catch (e) { return null; }
  }

  function ecrire(accepte) {
    try {
      localStorage.setItem(CLE, JSON.stringify({
        analytics: accepte, affiliate: accepte,
        date: new Date().toISOString(), exp: Date.now() + DUREE
      }));
    } catch (e) {}
  }

  // gtag.js не стоит в <head>: даже в состоянии denied Consent Mode шлёт
  // бескуковый пинг, то есть обращается к Google до всякого выбора. Замерено
  // 2026-08-14: после «Refuser» уходил один хит. Отказ должен означать
  // отсутствие контакта, а не контакт без cookie.
  var gaCharge = false;
  function chargerGA() {
    if (gaCharge || document.getElementById("cn-ga")) return;
    gaCharge = true;
    var s = document.createElement("script");
    s.id = "cn-ga";
    s.async = true;
    s.src = "https://www.googletagmanager.com/gtag/js?id=G-J8273H5YMH";
    document.head.appendChild(s);
  }

  function appliquer(accepte) {
    if (accepte) chargerGA();
    if (typeof window.gtag === "function") {
      window.gtag("consent", "update", {
        analytics_storage: accepte ? "granted" : "denied",
        ad_storage: "denied", ad_user_data: "denied", ad_personalization: "denied"
      });
    }
    if (accepte) { chargerStay22(); chargerTravelPayouts(); }
  }

  // Stay22 ставит свои cookies, поэтому грузится только после согласия.
  // Раньше он стоял инлайном в конце каждой страницы и запускался всегда —
  // включая юридические страницы, где аналитики нет вовсе.
  var stay22Charge = false;
  function chargerStay22() {
    if (stay22Charge || document.getElementById("cn-stay22")) return;
    stay22Charge = true;
    window.Stay22 = window.Stay22 || {};
    window.Stay22.params = { lmaID: STAY22 };
    var s = document.createElement("script");
    s.id = "cn-stay22";
    s.async = true;
    s.src = "https://scripts.stay22.com/letmeallez.js";
    document.head.appendChild(s);
  }

  // Travelpayouts. Le fournisseur le distribue en <script> inline place dans
  // <head>, avec un jeu d'attributs (nowprocket, data-noptimize, data-cfasync,
  // data-no-defer) dont la fonction est d'empecher tout report de son
  // execution. C'est incompatible avec un consentement prealable : un script
  // concu pour ne pas etre differe s'execute avant que le lecteur ait choisi.
  //
  // Il ne se contente pas de compter. Il remplace window.open,
  // Element.setAttribute, cloneNode et replaceChild, reecrit les liens
  // affilies, prend un instantane du HTML — et redefinit
  // Function.prototype.toString pour que ses propres correctifs se presentent
  // comme du code natif. Raison de plus pour qu'il ne parte qu'apres un oui
  // explicite, comme Stay22.
  var tpCharge = false;
  function chargerTravelPayouts() {
    if (tpCharge || document.getElementById("cn-tp")) return;
    tpCharge = true;
    var s = document.createElement("script");
    s.id = "cn-tp";
    s.async = true;
    s.setAttribute("data-cmp-ab", "2");
    s.src = TRAVELPAYOUTS;
    document.head.appendChild(s);
  }

  function construire() {
    var bar = document.createElement("div");
    bar.id = "cn-consent";
    bar.setAttribute("role", "dialog");
    bar.setAttribute("aria-label", FR ? "Choix des traceurs" : "Tracker choice");

    var liens = T.liens.map(function (l) {
      return '<a href="' + l[0] + '">' + l[1] + "</a>";
    }).join(" · ");

    bar.innerHTML =
      '<div class="cn-inner">' +
        '<p class="cn-text">' + T.texte + " " + liens +
          '<span class="cn-parties">' + T.parties + "</span>" +
        "</p>" +
        '<div class="cn-btns">' +
          '<button type="button" data-cn="no">' + T.non + "</button>" +
          '<button type="button" data-cn="ok">' + T.ok + "</button>" +
        "</div>" +
      "</div>";

    bar.addEventListener("click", function (e) {
      var b = e.target.closest("button[data-cn]");
      if (!b) return;
      var accepte = b.getAttribute("data-cn") === "ok";
      var avant = lire();
      ecrire(accepte);
      appliquer(accepte);
      bar.hidden = true;
      // Отзыв согласия: скрипт, уже загруженный на этой странице, выгрузить
      // нельзя — Consent Mode лишь запретит ему хранилище, но соединения с
      // Google продолжатся до конца сессии страницы. Перезагрузка — простой и
      // честный способ сделать «Отказаться» немедленным, а не отложенным.
      if (!accepte && avant && avant.analytics === true) location.reload();
    });

    document.body.appendChild(bar);
    return bar;
  }

  var barre = null;
  function afficher() {
    if (!barre) barre = construire();
    barre.hidden = false;
  }

  // Возврат к выбору: ссылка в подвале. Отзыв должен быть не сложнее согласия.
  function poserLienPied() {
    var pied = document.querySelector("footer.foot");
    if (!pied || pied.querySelector(".cn-revoke")) return;
    var hote = pied.querySelector(".right") || pied.lastElementChild || pied;
    var b = document.createElement("button");
    b.type = "button";
    b.className = "cn-revoke";
    b.textContent = T.gerer;
    b.addEventListener("click", afficher);
    hote.appendChild(document.createTextNode(" · "));
    hote.appendChild(b);
  }

  function demarrer() {
    var choix = lire();
    if (choix) {
      appliquer(choix.analytics === true);
    } else {
      afficher();                 // до выбора не грузится ничего стороннего
    }
    poserLienPied();
  }

  window.cnConsentOpen = afficher;   // на случай ссылки из текста политики

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", demarrer);
  } else {
    demarrer();
  }
})();
