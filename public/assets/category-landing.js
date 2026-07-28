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
      price_per_piece: s.pricePerPiece,
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

  /* Product photo → pack shot: hover on desktop, first tap on touch. */
  if (window.matchMedia("(hover: none)").matches) {
    document.querySelectorAll(".cl-card").forEach(function (card) {
      var media = card.querySelector(".cl-card__media");
      var hint = card.querySelector(".cl-card__hint");
      if (hint) hint.textContent = "Тап · Пачка";
      if (!media) return;
      media.addEventListener("click", function (e) {
        if (!card.classList.contains("is-flipped")) {
          e.preventDefault();
          document.querySelectorAll(".cl-card.is-flipped").forEach(function (other) {
            if (other !== card) other.classList.remove("is-flipped");
          });
          card.classList.add("is-flipped");
        }
      });
    });
  }

  /* PDF track */
  document.querySelectorAll('[data-track="pdf_download"]').forEach(function (a) {
    a.addEventListener("click", function () { track("pdf_download"); });
  });

  /* —— Saga: test1-style bubble wipe + whip slides (3 chapters / ~300%) —— */
  function initSagaWow() {
    var saga = document.querySelector("[data-cl-saga]");
    if (!saga || saga.dataset.sagaReady === "1") return true;
    var pin = saga.querySelector("[data-saga-pin]");
    var stage = saga.querySelector("[data-saga-stage]");
    var bg = saga.querySelector("[data-saga-bg]");
    var veil = saga.querySelector("[data-saga-veil]");
    var flash = saga.querySelector("[data-saga-flash]");
    var marquee = saga.querySelector("[data-saga-marquee]");
    var bar = saga.querySelector("[data-saga-bar]");
    var hint = saga.querySelector("[data-saga-hint]");
    var chapters = saga.querySelectorAll(".cl-saga__chapter");
    var imgs = saga.querySelectorAll(".cl-saga__img");
    var dots = saga.querySelectorAll("[data-saga-dots] .cl-saga__dot");
    if (!pin || !stage || !chapters.length || !imgs.length) return true;

    var reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    var desktop = window.matchMedia("(min-width: 768px)").matches;
    if (reduce || !desktop) return true;

    var gsap = window.gsap;
    var ScrollTrigger = window.ScrollTrigger;
    if (!gsap || !ScrollTrigger) return false;

    saga.dataset.sagaReady = "1";
    gsap.registerPlugin(ScrollTrigger);

    function attachLenis() {
      if (!window.Lenis || window.__clLenis) return !!window.__clLenis;
      document.documentElement.classList.add("lenis");
      var lenis = new Lenis({
        duration: 1.2,
        easing: function (t) { return Math.min(1, 1.001 - Math.pow(2, -10 * t)); },
        smoothWheel: true,
        touchMultiplier: 1.05,
      });
      lenis.on("scroll", ScrollTrigger.update);
      gsap.ticker.add(function (time) { lenis.raf(time * 1000); });
      gsap.ticker.lagSmoothing(0);
      window.__clLenis = lenis;
      return true;
    }
    attachLenis();

    var CREAM = "#f4e7a4";
    var DARK = "#12070a";
    var endPct = Number(saga.getAttribute("data-end-percent") || DATA.sagaEndPercent || 300);
    var completed = false;

    function setChapter(i) {
      chapters.forEach(function (c, idx) {
        var on = idx === i;
        c.classList.toggle("is-on", on);
        if (!on) gsap.set(c, { opacity: 0, visibility: "hidden" });
      });
      dots.forEach(function (d, idx) { d.classList.toggle("is-on", idx === i); });
      var tone = chapters[i].getAttribute("data-tone") === "cream" ? "cream" : "dark";
      saga.setAttribute("data-tone", tone);
      document.body.setAttribute("data-saga-tone", tone === "cream" ? "light" : "dark");
    }

    function wordsOf(ch) {
      return ch.querySelectorAll(".word");
    }

    function enterChapter(tl, i, at, opts) {
      var ch = chapters[i];
      var w = wordsOf(ch);
      var kicker = ch.querySelector(".cl-saga__kicker");
      var sub = ch.querySelector(".cl-saga__sub");
      tl.call(setChapter, [i], at);
      tl.set(ch, { visibility: "visible", opacity: 1 }, at);
      if (opts && opts.instant) {
        tl.set(w, { y: "0%", opacity: 1 }, at);
        if (kicker) tl.set(kicker, { opacity: 0.75, y: 0 }, at);
        if (sub) tl.set(sub, { opacity: 0.92, y: 0 }, at);
        return;
      }
      tl.fromTo(w, { y: "45%", opacity: 0 }, {
        y: "0%", opacity: 1, duration: 0.4, stagger: 0.045, ease: "power3.out",
      }, at);
      if (kicker) tl.fromTo(kicker, { opacity: 0, y: 8 }, { opacity: 0.75, y: 0, duration: 0.28 }, at);
      if (sub) tl.fromTo(sub, { opacity: 0, y: 10 }, { opacity: 0.92, y: 0, duration: 0.32 }, at + 0.08);
    }

    function exitChapter(tl, i, at) {
      var ch = chapters[i];
      var w = wordsOf(ch);
      tl.to(w, { y: "-28%", opacity: 0, duration: 0.22, stagger: 0.02, ease: "power2.in" }, at);
      tl.to([ch.querySelector(".cl-saga__kicker"), ch.querySelector(".cl-saga__sub")], {
        opacity: 0, duration: 0.18,
      }, at);
      tl.set(ch, { visibility: "hidden", opacity: 0 }, at + 0.22);
    }

    function punchFlash(tl, at) {
      if (!flash) return;
      tl.fromTo(flash, { opacity: 0 }, { opacity: 0.7, duration: 0.06, ease: "none" }, at);
      tl.to(flash, { opacity: 0, duration: 0.4, ease: "power2.out" }, at + 0.06);
    }

    gsap.set(chapters, { opacity: 0, visibility: "hidden" });
    gsap.set(imgs, { opacity: 0, scale: 1.25, x: 0, rotate: 0, filter: "blur(0px)" });
    if (veil) gsap.set(veil, { opacity: 0 });
    gsap.set(stage, { clipPath: "circle(0% at 50% 55%)" });
    if (marquee) gsap.set(marquee, { opacity: 0, x: 0 });
    if (bg) gsap.set(bg, { backgroundColor: CREAM });

    var tl = gsap.timeline({
      scrollTrigger: {
        trigger: pin,
        start: "top top",
        end: "+=" + endPct + "%",
        pin: true,
        scrub: 0.65,
        anticipatePin: 1,
        invalidateOnRefresh: true,
        onUpdate: function (self) {
          if (bar) bar.style.width = (self.progress * 100).toFixed(1) + "%";
          if (hint) gsap.set(hint, { autoAlpha: self.progress < 0.04 ? 0.55 : 0 });
          if (self.progress > 0.92 && !completed) {
            completed = true;
            track("saga_complete");
          }
        },
        onToggle: function (self) {
          document.body.classList.toggle("cl-saga-on", self.isActive);
        },
      },
    });

    /* 0 — cream opener + chapter 0 + marquee */
    enterChapter(tl, 0, 0, { instant: true });
    if (marquee) {
      tl.to(marquee, { opacity: 1, duration: 0.35 }, 0.08);
      tl.to(marquee, { x: "-16%", duration: 1.15, ease: "none" }, 0.08);
    }
    tl.to({}, { duration: 0.2 });

    /* Bubble explode → photo 0, chapter 0 becomes dark over image */
    punchFlash(tl, ">");
    if (marquee) tl.to(marquee, { opacity: 0, duration: 0.28 }, "<");
    if (bg) tl.to(bg, { backgroundColor: DARK, duration: 0.4 }, "<");
    tl.call(function () {
      chapters[0].setAttribute("data-tone", "dark");
      setChapter(0);
    }, null, "<");
    tl.set(imgs[0], { opacity: 1, scale: 1.2 }, "<");
    tl.to(stage, {
      clipPath: "circle(160% at 50% 55%)",
      duration: 1.15,
      ease: "power3.inOut",
    }, "<0.05");
    if (veil) tl.to(veil, { opacity: 1, duration: 0.45 }, "<0.25");
    tl.to(imgs[0], { scale: 1.06, duration: 0.95, ease: "none" });
    tl.to(imgs[0], { scale: 1.12, x: "2%", duration: 0.65, ease: "none" });

    /* Whip → photo 1 + chapter 1 */
    if (imgs[1] && chapters[1]) {
      punchFlash(tl, ">");
      tl.to(imgs[0], { opacity: 0, x: "-12%", scale: 1.22, duration: 0.5, ease: "power2.in" }, "<");
      tl.fromTo(imgs[1], { opacity: 0, x: "16%", scale: 1.24, rotate: 2 }, {
        opacity: 1, x: "0%", scale: 1.06, rotate: 0, duration: 0.7, ease: "power2.out",
      }, "<0.12");
      enterChapter(tl, 1, "<0.1");
      exitChapter(tl, 0, "<");
      tl.to(imgs[1], { scale: 1.13, duration: 0.85, ease: "none" });
    }

    /* Zoom punch → photo 2 + chapter 2 */
    if (imgs[2] && chapters[2]) {
      tl.to(imgs[1], {
        opacity: 0, scale: 1.32, filter: "blur(6px)", duration: 0.5, ease: "power2.in",
      }, ">");
      tl.fromTo(imgs[2], { opacity: 0, scale: 1.4, filter: "blur(8px)" }, {
        opacity: 1, scale: 1.05, filter: "blur(0px)", duration: 0.7, ease: "power3.out",
      }, "<0.1");
      enterChapter(tl, 2, "<0.1");
      exitChapter(tl, 1, "<");
      tl.to(imgs[2], { scale: 1.12, duration: 0.85, ease: "none" });
    }

    tl.to({}, { duration: 0.4 });
    return true;
  }

  function bootSaga(attempts) {
    var left = typeof attempts === "number" ? attempts : 50;
    var ok = initSagaWow();
    if (ok === false && left > 0) {
      setTimeout(function () { bootSaga(left - 1); }, 40);
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () { bootSaga(50); });
  } else {
    bootSaga(50);
  }
  window.addEventListener("load", function () {
    bootSaga(12);
    if (window.ScrollTrigger) window.ScrollTrigger.refresh();
  });
})();
