// KAZYLYK — interactions: nav, reveal, form, analytics.
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
      menu.setAttribute("aria-hidden", open ? "false" : "true");
      menu.classList.toggle("open", open);
      if (nav) nav.classList.toggle("menu-open", open);
      d.body.style.overflow = open ? "hidden" : "";
    }
    burger.addEventListener("click", function () {
      toggle(burger.getAttribute("aria-expanded") !== "true");
    });
    menu.querySelectorAll("a").forEach(function (a) {
      a.addEventListener("click", function () { toggle(false); });
    });
    d.addEventListener("keydown", function (event) {
      if (event.key === "Escape" && burger.getAttribute("aria-expanded") === "true") {
        toggle(false);
        burger.focus();
      }
    });
  }

  // Reveal on scroll (staggered inside grids)
  var reveal = d.querySelectorAll(".reveal");
  d.querySelectorAll(".cols, .steps, .sku-grid, .channels, .forms__grid, .ritual__steps").forEach(function (grid) {
    grid.querySelectorAll(".reveal").forEach(function (el, i) {
      el.style.setProperty("--i", i);
    });
  });
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

  // Hero parallax: arcade fades out on scroll
  var heroArcade = d.querySelector(".hero .arcade img");
  var reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (!reduceMotion && heroArcade) {
    var ticking = false;
    window.addEventListener("scroll", function () {
      if (ticking) return;
      ticking = true;
      window.requestAnimationFrame(function () {
        var y = window.scrollY;
        if (y < window.innerHeight * 1.2) {
          heroArcade.style.opacity = Math.max(0.1, 0.48 - y / 1600);
        }
        ticking = false;
      });
    }, { passive: true });
  }

  // Lightbox for the forms mosaic
  var lightbox = d.createElement("div");
  lightbox.className = "lightbox";
  lightbox.setAttribute("role", "dialog");
  lightbox.setAttribute("aria-modal", "true");
  lightbox.setAttribute("aria-label", "Фото продукта");
  lightbox.innerHTML = '<button class="lightbox__close" aria-label="Закрыть">×</button><img alt="" /><p class="lightbox__caption"></p>';
  d.body.appendChild(lightbox);
  var lbImg = lightbox.querySelector("img");
  var lbCap = lightbox.querySelector(".lightbox__caption");
  function closeLightbox() {
    lightbox.classList.remove("open");
    d.body.style.overflow = "";
  }
  lightbox.addEventListener("click", function (e) {
    if (e.target === lightbox || e.target.classList.contains("lightbox__close")) closeLightbox();
  });
  d.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && lightbox.classList.contains("open")) closeLightbox();
  });
  d.querySelectorAll(".forms__cell").forEach(function (cell) {
    cell.setAttribute("tabindex", "0");
    cell.setAttribute("role", "button");
    function open() {
      var img = cell.querySelector("img");
      var cap = cell.querySelector("figcaption");
      if (!img) return;
      lbImg.src = img.src;
      lbImg.alt = img.alt || "";
      lbCap.textContent = cap ? cap.textContent : "";
      lightbox.classList.add("open");
      d.body.style.overflow = "hidden";
    }
    cell.addEventListener("click", open);
    cell.addEventListener("keydown", function (e) {
      if (e.key === "Enter" || e.key === " ") { e.preventDefault(); open(); }
    });
  });

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
