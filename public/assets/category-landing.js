/* Category B2B landing runtime: personalization, calc, shortlist, table, saga */
(function () {
  "use strict";

  var raw = document.getElementById("cl-runtime");
  if (!raw) return;
  var DATA;
  try {
    DATA = JSON.parse(raw.textContent || "{}");
  } catch (e) {
    return;
  }

  var SKUS = DATA.skus || [];
  var BY_SKU = {};
  SKUS.forEach(function (s) { BY_SKU[s.sku] = s; });

  function track(name, payload) {
    try {
      window.dataLayer = window.dataLayer || [];
      window.dataLayer.push(Object.assign({ event: name, page: location.pathname }, payload || {}));
      if (typeof window.gtag === "function") {
        window.gtag("event", name, payload || {});
      }
    } catch (err) {}
  }

  function money(n) {
    var v = Math.round(n);
    return v.toLocaleString("ru-RU") + " ₽";
  }

  function money2(n) {
    return (Math.round(n * 100) / 100).toLocaleString("ru-RU", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }) + " ₽";
  }

  /* —— A. Personalization —— */
  function sanitizeParam(v) {
    if (v == null) return "";
    var s = String(v);
    s = s.replace(/[<>&"']/g, "");
    if (s.length > 80) s = s.slice(0, 80);
    return s.trim();
  }

  var params = new URLSearchParams(location.search);
  var to = sanitizeParam(params.get("to"));
  var mgr = sanitizeParam(params.get("mgr")).toLowerCase();
  var city = sanitizeParam(params.get("city"));

  var personal = document.querySelector("[data-cl-personal]");
  var personalLine = document.querySelector("[data-cl-personal-line]");
  var mgrBox = document.querySelector("[data-cl-mgr]");
  var managersRoot = DATA.managers || {};
  var managers = managersRoot.managers || {};
  var manager = mgr ? managers[mgr] : null;

  if (to || manager || city) {
    if (personal) personal.hidden = false;
    if (personalLine) {
      var bits = [];
      if (to) bits.push("Подготовлено для " + to);
      bits.push("Прайс от " + (DATA.priceDate || ""));
      personalLine.textContent = bits.join(" · ");
    }
  }

  if (manager && mgrBox) {
    mgrBox.hidden = false;
    var photo = mgrBox.querySelector("[data-cl-mgr-photo]");
    var nameEl = mgrBox.querySelector("[data-cl-mgr-name]");
    var roleEl = mgrBox.querySelector("[data-cl-mgr-role]");
    var telA = mgrBox.querySelector("[data-cl-mgr-tel]");
    var waA = mgrBox.querySelector("[data-cl-mgr-wa]");
    var tgA = mgrBox.querySelector("[data-cl-mgr-tg]");
    if (photo) {
      photo.src = manager.photo || "/images/icon-180.png";
      photo.alt = manager.name || "";
    }
    if (nameEl) nameEl.textContent = manager.name || "";
    if (roleEl) roleEl.textContent = manager.role || "";
    if (telA) {
      telA.href = "tel:" + (manager.tel || managersRoot.default_tel || "+79872170202");
      telA.textContent = manager.phone || managersRoot.default_phone || "+7 987 217-02-02";
    }
    if (waA) waA.href = manager.whatsapp || managersRoot.default_whatsapp || "#";
    if (tgA) tgA.href = manager.telegram || managersRoot.default_telegram || "#";

    var phoneNav = document.querySelector("[data-cl-phone]");
    if (phoneNav && manager.phone) {
      phoneNav.textContent = manager.phone;
      phoneNav.href = "tel:" + (manager.tel || "").replace(/\s/g, "");
    }
  }

  var logistics = document.querySelector("[data-cl-logistics]");
  if (logistics) {
    logistics.textContent = city
      ? "Отгрузка EXW Казань · доставка до " + city + " — уточните у менеджера"
      : "Отгрузка EXW Казань";
  }

  document.querySelectorAll('[data-cl-field="to"]').forEach(function (el) { el.value = to; });
  document.querySelectorAll('[data-cl-field="mgr"]').forEach(function (el) { el.value = mgr; });
  document.querySelectorAll('[data-cl-field="city"]').forEach(function (el) { el.value = city; });

  /* —— B. Calculator —— */
  var calcRoot = document.querySelector("[data-cl-calc]");
  var calcSnapshot = null;
  var calcUsed = false;

  function currentSku() {
    var sel = calcRoot && calcRoot.querySelector("[data-calc-sku]");
    return BY_SKU[(sel && sel.value) || (DATA.calcDefaults || {}).sku] || SKUS[0];
  }

  function readCalcInputs() {
    var s = currentSku();
    var portions = Number((calcRoot.querySelector("[data-calc-portions]") || {}).value || 60);
    var sell = Number((calcRoot.querySelector("[data-calc-sell]") || {}).value || 180);
    var extras = Number((calcRoot.querySelector("[data-calc-extras]") || {}).value || 25);
    return { sku: s, portions: portions, sell: sell, extras: extras };
  }

  function renderCalc() {
    if (!calcRoot || !SKUS.length) return;
    var inp = readCalcInputs();
    var s = inp.sku;
    var cost = s.pricePerPiece + inp.extras;
    var marginUnit = inp.sell - cost;
    var marginDay = marginUnit * inp.portions;
    var marginMonth = marginDay * 30;
    var packsMonth = (inp.portions * 30) / s.pieces;
    var buyMonth = packsMonth * s.price;

    var unitEl = calcRoot.querySelector("[data-calc-margin-unit]");
    var monthEl = calcRoot.querySelector("[data-calc-margin-month]");
    var costEl = calcRoot.querySelector("[data-calc-cost]");
    var dayEl = calcRoot.querySelector("[data-calc-margin-day]");
    var packsEl = calcRoot.querySelector("[data-calc-packs]");
    var buyEl = calcRoot.querySelector("[data-calc-buy]");
    var pLabel = calcRoot.querySelector("[data-calc-portions-label]");
    var sLabel = calcRoot.querySelector("[data-calc-sell-label]");

    if (unitEl) unitEl.textContent = money(marginUnit);
    if (monthEl) monthEl.textContent = money(marginMonth);
    if (costEl) costEl.textContent = money2(cost);
    if (dayEl) dayEl.textContent = money(marginDay);
    if (packsEl) packsEl.textContent = (Math.round(packsMonth * 10) / 10).toLocaleString("ru-RU");
    if (buyEl) buyEl.textContent = money(buyMonth);
    if (pLabel) pLabel.textContent = String(inp.portions);
    if (sLabel) sLabel.textContent = String(inp.sell);

    calcSnapshot = {
      sku: s.sku,
      portions_per_day: inp.portions,
      sell_price: inp.sell,
      extras: inp.extras,
      price_per_piece: s.price,
      pricePerPiece: s.pricePerPiece,
      pieces: s.pieces,
      cost_per_portion: Math.round(cost * 100) / 100,
      margin_unit: Math.round(marginUnit * 100) / 100,
      margin_day: Math.round(marginDay),
      margin_month: Math.round(marginMonth),
      packs_month: Math.round(packsMonth * 10) / 10,
      buy_month: Math.round(buyMonth),
    };

    var snapField = document.querySelector('[data-cl-field="calc_snapshot"]');
    if (snapField) snapField.value = JSON.stringify(calcSnapshot);
  }

  if (calcRoot) {
    calcRoot.addEventListener("input", function () {
      renderCalc();
      if (!calcUsed) {
        calcUsed = true;
        track("calc_used", { sku: (calcSnapshot && calcSnapshot.sku) || "" });
      }
    });
    renderCalc();
  }

  /* —— C. Shortlist —— */
  var storageKey = DATA.shortlistStorageKey || "kd_shortlist";
  var selected = {};
  try {
    var saved = JSON.parse(localStorage.getItem(storageKey) || "[]");
    if (Array.isArray(saved)) {
      saved.forEach(function (sku) {
        if (BY_SKU[sku]) selected[sku] = true;
      });
    }
  } catch (e) {}

  var floatBar = document.querySelector("[data-cl-float]");
  var floatText = document.querySelector("[data-cl-float-text]");
  var messageEl = document.querySelector("[data-cl-message]");

  function selectedList() {
    return SKUS.filter(function (s) { return selected[s.sku]; });
  }

  function persist() {
    localStorage.setItem(storageKey, JSON.stringify(selectedList().map(function (s) { return s.sku; })));
  }

  function syncCheckboxes() {
    document.querySelectorAll(".cl-shortlist-cb").forEach(function (cb) {
      var sku = cb.getAttribute("data-sku");
      cb.checked = !!selected[sku];
    });
  }

  function shortlistMessageLines() {
    return selectedList().map(function (s) {
      return s.sku + " " + s.name + " — " + s.minOrder + " уп.";
    });
  }

  function updateFloat() {
    var list = selectedList();
    var field = document.querySelector('[data-cl-field="shortlist"]');
    if (field) field.value = JSON.stringify(list.map(function (s) { return s.sku; }));

    if (!list.length) {
      if (floatBar) floatBar.hidden = true;
      return;
    }
    var packs = 0;
    var kg = 0;
    var rub = 0;
    list.forEach(function (s) {
      packs += s.minOrder;
      kg += s.minOrder * s.weightKg;
      rub += s.minOrder * s.price;
    });
    if (floatText) {
      floatText.textContent =
        "Выбрано " + list.length + " SKU · " +
        packs + " упаковок · " +
        (Math.round(kg * 10) / 10).toLocaleString("ru-RU") + " кг · " +
        money(rub);
    }
    if (floatBar) floatBar.hidden = false;
  }

  function fillMessageFromShortlist() {
    if (!messageEl) return;
    var lines = shortlistMessageLines();
    if (!lines.length) return;
    var block = "Шорт-лист:\n" + lines.join("\n");
    var cur = messageEl.value || "";
    if (/Шорт-лист:/i.test(cur)) {
      messageEl.value = cur.replace(/Шорт-лист:[\s\S]*?(?:\n\n|$)/i, block + "\n\n").trim() + "\n";
    } else {
      messageEl.value = (cur ? cur.replace(/\s+$/, "") + "\n\n" : "") + block + "\n";
    }
  }

  document.addEventListener("change", function (e) {
    var t = e.target;
    if (!t || !t.classList || !t.classList.contains("cl-shortlist-cb")) return;
    var sku = t.getAttribute("data-sku");
    if (!BY_SKU[sku]) return;
    if (t.checked) {
      selected[sku] = true;
      track("shortlist_add", { sku: sku });
    } else {
      delete selected[sku];
    }
    syncCheckboxes();
    persist();
    updateFloat();
    fillMessageFromShortlist();
  });

  var floatCta = document.querySelector("[data-cl-float-cta]");
  if (floatCta) {
    floatCta.addEventListener("click", function () {
      fillMessageFromShortlist();
      track("shortlist_submit", { count: selectedList().length });
    });
  }

  syncCheckboxes();
  updateFloat();
  if (selectedList().length) fillMessageFromShortlist();

  /* Enrich lead payload before submit */
  document.querySelectorAll("form.lead-form").forEach(function (form) {
    form.addEventListener("submit", function () {
      fillMessageFromShortlist();
      if (calcSnapshot) {
        var snapField = form.querySelector('[name="calc_snapshot"]');
        if (snapField) snapField.value = JSON.stringify(calcSnapshot);
        var msg = form.querySelector('[name="message"]');
        if (msg && calcSnapshot) {
          var line =
            "Калькулятор: " + calcSnapshot.sku +
            ", " + calcSnapshot.portions_per_day + " порц/день" +
            ", продажа " + calcSnapshot.sell_price + " ₽" +
            ", маржа/мес ~" + calcSnapshot.margin_month + " ₽";
          if (msg.value.indexOf("Калькулятор:") === -1) {
            msg.value = (msg.value ? msg.value.replace(/\s+$/, "") + "\n" : "") + line;
          }
        }
      }
      if (to || mgr || city) {
        var msg2 = form.querySelector('[name="message"]');
        if (msg2) {
          var attr = [];
          if (to) attr.push("для: " + to);
          if (mgr) attr.push("mgr: " + mgr);
          if (city) attr.push("город: " + city);
          var attrLine = "Ссылка: " + attr.join(", ");
          if (msg2.value.indexOf("Ссылка:") === -1) {
            msg2.value = (msg2.value ? msg2.value.replace(/\s+$/, "") + "\n" : "") + attrLine;
          }
        }
      }
    }, true);
  });

  /* —— D. Table / view toggle —— */
  var sortState = { key: null, dir: 1 };
  document.querySelectorAll("[data-view]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var view = btn.getAttribute("data-view");
      document.querySelectorAll("[data-view]").forEach(function (b) {
        b.classList.toggle("is-active", b === btn);
      });
      document.querySelectorAll("[data-view-panel]").forEach(function (panel) {
        panel.hidden = panel.getAttribute("data-view-panel") !== view;
      });
      if (view === "table") track("table_view");
    });
  });

  document.querySelectorAll("[data-sort]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var key = btn.getAttribute("data-sort");
      var tbody = document.querySelector("[data-cl-table] tbody");
      if (!tbody) return;
      if (sortState.key === key) sortState.dir *= -1;
      else { sortState.key = key; sortState.dir = 1; }
      var rows = Array.prototype.slice.call(tbody.querySelectorAll("tr"));
      rows.sort(function (a, b) {
        var av = Number(a.getAttribute("data-" + key) || 0);
        var bv = Number(b.getAttribute("data-" + key) || 0);
        return (av - bv) * sortState.dir;
      });
      rows.forEach(function (r) { tbody.appendChild(r); });
    });
  });

  /* PDF track */
  document.querySelectorAll('[data-track="pdf_download"]').forEach(function (a) {
    a.addEventListener("click", function () { track("pdf_download"); });
  });

  /* —— Saga (desktop pin + crossfade; mobile = swipe gallery) —— */
  function initSaga() {
    var saga = document.querySelector("[data-cl-saga]");
    if (!saga || saga.dataset.sagaReady === "1") return;
    var pin = saga.querySelector("[data-saga-pin]");
    var slides = pin ? Array.prototype.slice.call(pin.querySelectorAll("[data-saga-slide]")) : [];
    if (!pin || !slides.length) return;

    var reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    var desktop = window.matchMedia("(min-width: 768px)").matches;

    // Always show first slide so desktop never looks empty before GSAP boots.
    slides.forEach(function (s, i) {
      s.classList.toggle("is-on", i === 0);
    });

    if (reduce || !desktop) return;

    var gsap = window.gsap;
    var ScrollTrigger = window.ScrollTrigger;
    if (!gsap || !ScrollTrigger) return false;

    saga.dataset.sagaReady = "1";
    gsap.registerPlugin(ScrollTrigger);

    var endPct = Number(saga.getAttribute("data-end-percent") || DATA.sagaEndPercent || 300);
    var completed = false;
    var lastIdx = 0;

    ScrollTrigger.create({
      trigger: saga,
      start: "top top",
      end: "+=" + endPct + "%",
      pin: true,
      pinSpacing: true,
      scrub: 0.35,
      anticipatePin: 1,
      onToggle: function (self) {
        saga.classList.toggle("is-pinned", self.isActive);
      },
      onUpdate: function (self) {
        var idx = Math.min(
          slides.length - 1,
          Math.floor(self.progress * slides.length + 0.0001)
        );
        if (idx !== lastIdx) {
          lastIdx = idx;
          slides.forEach(function (s, i) {
            s.classList.toggle("is-on", i === idx);
          });
        }
        if (self.progress > 0.92 && !completed) {
          completed = true;
          track("saga_complete");
        }
      },
    });
    return true;
  }

  function bootSaga(attempts) {
    var left = typeof attempts === "number" ? attempts : 40;
    var ok = initSaga();
    if (ok === false && left > 0) {
      setTimeout(function () { bootSaga(left - 1); }, 50);
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () { bootSaga(40); });
  } else {
    bootSaga(40);
  }
  window.addEventListener("load", function () { bootSaga(10); });
})();
