/* nav.js — мобильное меню.
 *
 * Отдельным файлом, а не инлайном на каждой странице: функция одна на 132
 * страницы, и правка в одном месте лучше, чем 132 расхождения. По той же
 * причине здесь нет onclick в разметке — обработчик вешается по классу, и
 * добавить кнопку на новую страницу можно, ничего не зная про JS.
 */
(function () {
  "use strict";

  function overlay() { return document.getElementById("navOverlay"); }

  function basculer(force) {
    var o = overlay();
    if (!o) return;
    var ouvert = (force === undefined) ? !o.classList.contains("open") : force;
    o.classList.toggle("open", ouvert);
    // Фон не должен прокручиваться под открытым меню.
    document.body.style.overflow = ouvert ? "hidden" : "";
  }

  document.addEventListener("click", function (e) {
    if (e.target.closest(".nav-burger, .nav-overlay-close")) {
      e.preventDefault();
      basculer();
      return;
    }
    // Клик по ссылке внутри меню: уходим на страницу, но меню закрываем —
    // иначе при возврате назад оно осталось бы открытым.
    if (e.target.closest(".nav-overlay a")) basculer(false);
    // Клик по фону вне списка ссылок тоже закрывает.
    else if (e.target.classList.contains("nav-overlay")) basculer(false);
  });

  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") basculer(false);
  });

  // Поворот экрана в альбом на планшете уводит нас за 640px, где оверлея нет:
  // если его не закрыть, страница останется с заблокированной прокруткой.
  window.addEventListener("resize", function () {
    if (window.innerWidth > 640) basculer(false);
  });

  // Открытым меню не должно пережить переход «назад» из кэша браузера.
  window.addEventListener("pageshow", function () { basculer(false); });
})();
