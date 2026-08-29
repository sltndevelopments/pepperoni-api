// KAZYLYK — interactions: nav, reveal, accordion sync, packaging hotspots, form, analytics.
(function () {
  "use strict";
  var d = document;

  // Nav scroll state
  var nav = d.querySelector(".nav");
  function onScroll() {
    if (!nav) return;
    nav.classList.toggle("is-scrolled", window.scrollY > 40);
  }
  onScroll();
  window.addEventListener("scroll", onScroll, { passive: true });

  // Mobile menu
  var burger = d.querySelector(".nav__burger");
  var menu = d.querySelector(".mobile-menu");
  if (burger && menu) {
    function toggle(open) {
      burger.setAttribute("aria-expanded", open ? "true" : "false");
      menu.classList.toggle("open", open);
      d.body.style.overflow = open ? "hidden" : "";
    }
    burger.addEventListener("click", function () {
      toggle(burger.getAttribute("aria-expanded") !== "true");
    });
    menu.querySelectorAll("a").forEach(function (a) {
      a.addEventListener("click", function () { toggle(false); });
    });
  }

  // Reveal on scroll
  var reveal = d.querySelectorAll(".reveal");
  if ("IntersectionObserver" in window && reveal.length) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting) {
          e.target.classList.add("in");
          io.unobserve(e.target);
        }
      });
    }, { rootMargin: "0px 0px -8% 0px", threshold: 0.08 });
    reveal.forEach(function (el) { io.observe(el); });
  } else {
    reveal.forEach(function (el) { el.classList.add("in"); });
  }

  // Analytics (dataLayer hooks, privacy-respecting, no external script)
  function ev(name, data) {
    window.dataLayer = window.dataLayer || [];
    window.dataLayer.push(Object.assign({ event: name }, data || {}));
    if (window.console && console.debug) console.debug("[event]", name, data || {});
  }
  d.querySelectorAll("[data-ev]").forEach(function (el) {
    el.addEventListener("click", function () {
      ev(el.getAttribute("data-ev"), { label: el.getAttribute("data-ev-label") || el.textContent.trim().slice(0, 40) });
    });
  });

  // Interactive packaging: highlight hotspots from legend and vice-versa
  var stage = d.querySelector(".packart__stage");
  if (stage) {
    var hots = stage.querySelectorAll(".packart__hot");
    var legends = d.querySelectorAll(".packart__legend button");
    function activate(idx) {
      hots.forEach(function (h, i) { h.classList.toggle("is-active", i === idx); });
      legends.forEach(function (b, i) { b.classList.toggle("is-active", i === idx); });
    }
    legends.forEach(function (b, i) {
      b.addEventListener("click", function () { activate(i); });
    });
    hots.forEach(function (h, i) {
      h.addEventListener("mouseenter", function () { activate(i); });
      h.addEventListener("focus", function () { activate(i); });
    });
  }

  // Order form: build a mailto, no backend. Honeypot + consent.
  var form = d.querySelector("#order-form");
  if (form) {
    var status = d.querySelector("#order-status");
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      var honey = form.querySelector("input[name='company_url']");
      if (honey && honey.value) { return; } // bot
      var consent = form.querySelector("input[name='consent']");
      if (consent && !consent.checked) {
        showStatus("Подтвердите согласие на обработку данных.", true);
        return;
      }
      var name = (form.querySelector("[name='name']") || {}).value || "";
      var phone = (form.querySelector("[name='phone']") || {}).value || "";
      var kind = (form.querySelector("[name='kind']") || {}).value || "";
      var msg = (form.querySelector("[name='message']") || {}).value || "";
      if (!name || !phone) {
        showStatus("Укажите имя и телефон.", true);
        return;
      }
      var subject = "Заказ KAZYLYK: " + kind;
      var body = "Имя: " + name + "\nТелефон: " + phone + "\nТип: " + kind + "\n\n" + msg;
      var F = window.KAZYLYK || {};
      var href = "mailto:" + (F.email || "info@kazandelikates.tatar") + "?subject=" + encodeURIComponent(subject) + "&body=" + encodeURIComponent(body);
      ev("order_start", { kind: kind });
      showStatus("Заявка готовится. Если почтовая программа не открылась, напишите нам на " + (F.email || "") + " или позвоните " + (F.phone || "") + ".", false);
      window.location.href = href;
    });
    function showStatus(text, isError) {
      if (!status) return;
      status.textContent = text;
      status.classList.add("show");
      status.classList.toggle("error", !!isError);
    }
  }
})();
