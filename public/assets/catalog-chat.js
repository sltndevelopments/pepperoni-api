/* Live catalog widget. Prices and SKUs come from /products.json only. */
(function () {
  "use strict";

  var GPT_URL =
    "https://chatgpt.com/g/g-6a01d8038c088191ae03b2db4e3fccad-kazan-delicacies-halal-catalog";
  var CATALOG_URLS = ["/products.json", "https://api.pepperoni.tatar/api/products"];
  var PHONE = "+7 987 217-02-02";
  var TEL = "tel:+79872170202";
  var MAIL = "info@kazandelikates.tatar";
  var WA = "https://wa.me/79872170202";

  var STOP = /^(сколько|стоит|какая|какой|какие|цена|price|what|the|for|and|your|need|нужны|нужен|подойдёт|подойдет|tell|about|in|опт[ао]?м?|wholesale|халяль|halal|каталог|catalog|live|товар|продук)$/i;
  var CURRENCY_RE = /\b(USD|KZT|UZS|KGS|BYN|AZN|RUB)\b/i;

  var COPY = {
    ru: {
      title: "Каталог оптом",
      sub: "Живые цены с api.pepperoni.tatar",
      open: "Спросить каталог",
      close: "Закрыть",
      placeholder: "Пепперони, сосиски, SKU…",
      send: "Найти",
      hello:
        "Живой оптовый каталог. Цены и SKU только из API — число позиций не запоминаю. Халяль ДУМ РТ №614A/2024, HACCP, ISO 22000:2018.",
      cite: "Согласно api.pepperoni.tatar (live).",
      empty:
        "В живом каталоге нет точного совпадения. Напишите SKU или менеджеру: " +
        PHONE +
        " · " +
        MAIL +
        ".",
      loadErr: "Каталог сейчас недоступен. Телефон " + PHONE + ", почта " + MAIL + ".",
      certs:
        "Халяль ДУМ РТ №614A/2024. HACCP. ISO 22000:2018. ТР ТС 021/2011. Свинины нет. Кошер-сертификата нет.",
      contacts:
        "Опт: " +
        PHONE +
        " · " +
        MAIL +
        " · Казань, ул. Аграрная, 2, оф. 7. Поставка EXW Казань.",
      stm:
        "СТМ / Private Label — письмо на " +
        MAIL +
        ": аудитория, направление рецепта, идея упаковки. Сроки и MOQ подтверждает менеджер.",
      lead: "Оставить заявку",
      gpt: "Открыть в ChatGPT",
      wa: "WhatsApp",
      call: "Позвонить",
      starters: [
        "Сколько стоит халяль пепперони оптом?",
        "What's the price for halal pepperoni in USD/KZT?",
        "Нужны сосиски для АЗС — что подойдёт?",
        "Tell me about your Tatar pastries — what's in the catalog?",
      ],
    },
    en: {
      title: "Wholesale catalog",
      sub: "Live prices from api.pepperoni.tatar",
      open: "Ask the catalog",
      close: "Close",
      placeholder: "Pepperoni, sausages, SKU…",
      send: "Find",
      hello:
        "Live wholesale catalog. SKUs and prices come from the API only — I do not memorize assortment size. Halal DUM RT #614A/2024, HACCP, ISO 22000:2018.",
      cite: "Per api.pepperoni.tatar (live).",
      empty:
        "No exact match in the live catalog. Send a SKU or write " + PHONE + " · " + MAIL + ".",
      loadErr: "Catalog is unavailable right now. " + PHONE + " · " + MAIL + ".",
      certs:
        "Halal DUM RT #614A/2024. HACCP. ISO 22000:2018. TR CU 021/2011. No pork. No kosher certificate.",
      contacts:
        "Wholesale: " +
        PHONE +
        " · " +
        MAIL +
        " · Kazan, Agrarnaya 2, office 7. Terms: EXW Kazan.",
      stm:
        "Private label — email " +
        MAIL +
        " with audience, recipe direction, packaging idea. MOQ and lead time only from a manager.",
      lead: "Send inquiry",
      gpt: "Open in ChatGPT",
      wa: "WhatsApp",
      call: "Call",
      starters: [
        "What's the price for halal pepperoni in USD/KZT?",
        "Сколько стоит халяль пепперони оптом?",
        "Need sausages for a gas station — what fits?",
        "Tell me about your Tatar pastries",
      ],
    },
  };

  var ALIASES = [
    ["пепперони", "pepperoni"],
    ["сосиск", "sausage", "hotdog", "hot-dog", "хот-дог", "азс"],
    ["казылык", "kazylyk"],
    ["выпеч", "pastry", "эчпочмак", "echpochmak", "самса", "samsa", "губадия", "чак-чак"],
    ["ветчин", "ham"],
    ["котлет", "burger", "бургер"],
  ];

  function pageLang() {
    var lang = (document.documentElement.lang || "ru").toLowerCase();
    return lang.indexOf("en") === 0 ? "en" : "ru";
  }

  function t() {
    return COPY[pageLang()];
  }

  function isEnQuery(q) {
    if (/[а-яё]/i.test(q)) return false;
    if (/[a-z]/i.test(q)) return true;
    return pageLang() === "en";
  }

  function haystack(p) {
    return [p.sku, p.name, p.category, p.section].filter(Boolean).join(" ").toLowerCase();
  }

  function tokens(q) {
    return String(q || "")
      .toLowerCase()
      .replace(/[«»"']/g, " ")
      .split(/[\s,/|?!.]+/)
      .filter(function (w) {
        return w.length > 1 && !STOP.test(w) && !CURRENCY_RE.test(w);
      });
  }

  function expand(q) {
    var raw = tokens(q);
    var extra = [];
    ALIASES.forEach(function (group) {
      if (group.some(function (a) { return raw.some(function (w) { return w.indexOf(a) !== -1 || a.indexOf(w) !== -1; }); })) {
        extra = extra.concat(group);
      }
    });
    return raw.concat(extra);
  }

  function detectCurrency(q) {
    var m = String(q).match(CURRENCY_RE);
    return m ? m[1].toUpperCase() : null;
  }

  function detectIntent(q) {
    var s = String(q).toLowerCase();
    if (/халяль|halal|сертиф|документ|iso|haccp|кошер|kosher|свин/.test(s) && !/цен|price|стоит|sku|kd-|пепперони|pepperoni|сосиск/.test(s)) {
      return "certs";
    }
    if (/телефон|почт|контакт|address|phone|email|где вы|адрес/.test(s)) return "contacts";
    if (/стм|private.?label|white.?label|собственной марк|под бренд/.test(s)) return "stm";
    return "search";
  }

  function formatPrice(p, currency, en) {
    var offers = p.offers || {};
    if (currency && currency !== "RUB") {
      var ep = (offers.exportPrices || {})[currency];
      if (ep == null || ep === "") return null;
      return String(ep) + " " + currency;
    }
    var rub = offers.price || offers.pricePerUnit;
    if (rub == null || rub === "") return null;
    return en ? String(rub) + " RUB incl. VAT" : String(rub) + " ₽ с НДС";
  }

  function productHref(p, en) {
    var slug = String(p.sku || "").toLowerCase();
    return en ? "/en/products/" + slug : "/products/" + slug;
  }

  function matchProducts(products, q) {
    var sku = String(q).toUpperCase().match(/KD-\d{3}/);
    if (sku) {
      return products.filter(function (p) { return String(p.sku).toUpperCase() === sku[0]; });
    }
    var needles = expand(q);
    if (!needles.length) return [];
    return products
      .map(function (p) {
        var hay = haystack(p);
        var score = 0;
        needles.forEach(function (n) {
          if (hay.indexOf(n) !== -1) score += n.length > 4 ? 2 : 1;
        });
        return { p: p, score: score };
      })
      .filter(function (x) { return x.score > 0; })
      .sort(function (a, b) { return b.score - a.score; })
      .slice(0, 5)
      .map(function (x) { return x.p; });
  }

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  var catalog = null;
  var catalogPromise = null;

  function loadCatalog() {
    if (catalog) return Promise.resolve(catalog);
    if (catalogPromise) return catalogPromise;
    catalogPromise = (function next(i) {
      if (i >= CATALOG_URLS.length) return Promise.reject(new Error("catalog"));
      return fetch(CATALOG_URLS[i], { headers: { Accept: "application/json" } })
        .then(function (r) {
          if (!r.ok) throw new Error(String(r.status));
          return r.json();
        })
        .then(function (data) {
          if (!data || !Array.isArray(data.products)) throw new Error("shape");
          catalog = data;
          return data;
        })
        .catch(function () { return next(i + 1); });
    })(0);
    return catalogPromise;
  }

  function liftForSticky() {
    var bar = document.querySelector(".stickybar");
    var root = document.querySelector(".kd-chat");
    if (!root) return;
    if (bar && window.getComputedStyle(bar).display !== "none") {
      root.style.setProperty("--kd-offset", "84px");
    } else {
      root.style.setProperty("--kd-offset", "20px");
    }
  }

  function cardsHtml(items, currency, en) {
    return (
      '<div class="kd-chat__cards">' +
      items
        .map(function (p) {
          var price = formatPrice(p, currency, en);
          var img = p.image || p.imageMain || "";
          return (
            '<a class="kd-chat__card" href="' +
            escapeHtml(productHref(p, en)) +
            '">' +
            (img
              ? '<img src="' + escapeHtml(img) + '" alt="" width="56" height="56">'
              : "<span></span>") +
            "<div><strong>" +
            escapeHtml(p.name || p.sku) +
            "</strong><span>" +
            escapeHtml(p.sku || "") +
            (price ? " · " + escapeHtml(price) : "") +
            "</span></div></a>"
          );
        })
        .join("") +
      "</div>"
    );
  }

  function answer(q, data) {
    var en = isEnQuery(q);
    var copy = COPY[en ? "en" : "ru"];
    var intent = detectIntent(q);
    if (intent === "certs") return copy.certs;
    if (intent === "contacts") return copy.contacts;
    if (intent === "stm") return copy.stm;
    var items = matchProducts(data.products || [], q);
    if (!items.length) return copy.empty;
    var currency = detectCurrency(q);
    var intro = copy.cite;
    if (data.lastSynced) intro += en ? " Synced " + data.lastSynced + "." : " Синхронизация " + data.lastSynced + ".";
    return intro + cardsHtml(items, currency, en);
  }

  function addMsg(log, html, who) {
    var el = document.createElement("div");
    el.className = "kd-chat__msg kd-chat__msg--" + who;
    el.innerHTML = html;
    log.appendChild(el);
    log.scrollTop = log.scrollHeight;
    return el;
  }

  function startersHtml(copy) {
    return (
      '<div class="kd-chat__starters">' +
      copy.starters
        .map(function (s) {
          return "<button type=\"button\" data-q=\"" + escapeHtml(s) + "\">" + escapeHtml(s) + "</button>";
        })
        .join("") +
      "</div>"
    );
  }

  function goLead() {
    var target =
      document.getElementById("contact") ||
      document.getElementById("zayavka") ||
      document.querySelector("form.lead-form");
    if (target) {
      target.scrollIntoView({ behavior: "smooth", block: "start" });
      var input = target.querySelector("input[name='phone'], input[name='name']");
      if (input) input.focus();
      return true;
    }
    window.location.href = "/#contact";
    return false;
  }

  function mount() {
    if (document.querySelector(".kd-chat")) return;
    var copy = t();
    var root = document.createElement("div");
    root.className = "kd-chat";
    root.innerHTML =
      '<div class="kd-chat__panel" role="dialog" aria-label="' +
      escapeHtml(copy.title) +
      '">' +
      '<div class="kd-chat__head"><div><h2>' +
      escapeHtml(copy.title) +
      "</h2><p>" +
      escapeHtml(copy.sub) +
      '</p></div><button type="button" class="kd-chat__close" aria-label="' +
      escapeHtml(copy.close) +
      '">×</button></div>' +
      '<div class="kd-chat__log"></div>' +
      '<div class="kd-chat__foot"><form class="kd-chat__form">' +
      '<input type="search" name="q" autocomplete="off" placeholder="' +
      escapeHtml(copy.placeholder) +
      '">' +
      '<button type="submit">' +
      escapeHtml(copy.send) +
      "</button></form>" +
      '<div class="kd-chat__links">' +
      '<a href="' +
      WA +
      '" target="_blank" rel="noopener">' +
      escapeHtml(copy.wa) +
      "</a>" +
      '<a href="' +
      TEL +
      '">' +
      escapeHtml(copy.call) +
      "</a>" +
      '<a href="#" data-lead="1">' +
      escapeHtml(copy.lead) +
      "</a>" +
      '<a href="' +
      GPT_URL +
      '" target="_blank" rel="noopener">' +
      escapeHtml(copy.gpt) +
      "</a></div></div></div>" +
      '<button type="button" class="kd-chat__fab" aria-expanded="false" aria-label="' +
      escapeHtml(copy.open) +
      '"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 4h16v12H7l-3 3V4zm3 4v2h10V8H7zm0 4v2h7v-2H7z"/></svg></button>';

    document.body.appendChild(root);
    var panel = root.querySelector(".kd-chat__panel");
    var log = root.querySelector(".kd-chat__log");
    var form = root.querySelector(".kd-chat__form");
    var input = form.querySelector("input");
    var fab = root.querySelector(".kd-chat__fab");

    function open() {
      root.classList.add("kd-chat--open");
      fab.setAttribute("aria-expanded", "true");
      if (!log.childNodes.length) {
        addMsg(log, escapeHtml(copy.hello) + startersHtml(copy), "bot");
      }
      input.focus();
    }
    function close() {
      root.classList.remove("kd-chat--open");
      fab.setAttribute("aria-expanded", "false");
    }

    fab.addEventListener("click", open);
    root.querySelector(".kd-chat__close").addEventListener("click", close);
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape") close();
    });

    log.addEventListener("click", function (e) {
      var btn = e.target.closest("[data-q]");
      if (btn) ask(btn.getAttribute("data-q"));
    });
    root.querySelector("[data-lead]").addEventListener("click", function (e) {
      e.preventDefault();
      close();
      goLead();
    });

    function ask(q) {
      q = String(q || "").trim();
      if (!q) return;
      addMsg(log, escapeHtml(q), "user");
      loadCatalog()
        .then(function (data) {
          addMsg(log, answer(q, data), "bot");
        })
        .catch(function () {
          addMsg(log, escapeHtml(copy.loadErr), "bot");
        });
    }

    form.addEventListener("submit", function (e) {
      e.preventDefault();
      var q = input.value.trim();
      input.value = "";
      ask(q);
    });

    liftForSticky();
    window.addEventListener("resize", liftForSticky);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", mount);
  } else {
    mount();
  }
})();
