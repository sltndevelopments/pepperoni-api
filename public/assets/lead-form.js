/* Lead-capture form handler for pepperoni.tatar
 * Posts to same-origin /lead-submit (nginx -> Flask lead-intake -> leads group).
 * Works for any <form class="lead-form"> on the page. Attribution: the current
 * pathname is sent as `page`; an optional data-experiment-id sets `experiment_id`.
 * 152-ФЗ: submission is blocked client-side unless the consent box is checked;
 * the server also re-checks consent.
 */
(function () {
  "use strict";

  // Google Ads lead conversion.
  // Primary path: googleadservices.com pixels (works when googletagmanager.com
  // DNS is blocked — common on RU ISPs / filters). gtag/GTM is optional bonus.
  var ADS_CONV_ID = "18346189266";
  var ADS_CONV_LABEL = "dznsCLar19UcENLDkqxE";
  var ADS_SEND_TO = "AW-18346189266/" + ADS_CONV_LABEL;

  function loadScriptOnce(src, flag) {
    if (window[flag]) return;
    window[flag] = true;
    var s = document.createElement("script");
    s.async = true;
    s.src = src;
    document.head.appendChild(s);
  }

  if (!window.__gtagAdsLoaded) {
    window.__gtagAdsLoaded = true;
    window.dataLayer = window.dataLayer || [];
    if (typeof window.gtag !== "function") {
      window.gtag = function () { window.dataLayer.push(arguments); };
    }
    window.gtag("js", new Date());
    window.gtag("config", "AW-18346189266");
    // Optional — may fail with ERR_NAME_NOT_RESOLVED; conversion still fires below.
    loadScriptOnce(
      "https://www.googletagmanager.com/gtag/js?id=AW-18346189266",
      "__gtagJsRequested"
    );
    // Classic async conversion lib — hosted on googleadservices, not GTM.
    loadScriptOnce(
      "https://www.googleadservices.com/pagead/conversion_async.js",
      "__adsConvAsyncRequested"
    );
  }

  function fireAdsLeadConversion(userData, leadId) {
    var qs =
      "?label=" +
      encodeURIComponent(ADS_CONV_LABEL) +
      "&guid=ON&script=0&value=1.0&currency_code=USD&t=" +
      Date.now();
    var urls = [
      "https://www.googleadservices.com/pagead/conversion/" + ADS_CONV_ID + "/" + qs,
      "https://www.google.com/pagead/1p-conversion/" + ADS_CONV_ID + "/" + qs,
    ];
    urls.forEach(function (u) {
      try {
        var img = new Image(1, 1);
        img.referrerPolicy = "no-referrer-when-downgrade";
        img.src = u;
      } catch (e1) {}
      try {
        if (typeof fetch === "function") {
          fetch(u, { mode: "no-cors", credentials: "omit", keepalive: true }).catch(function () {});
        }
      } catch (e2) {}
    });

    if (typeof window.google_trackConversion === "function") {
      try {
        window.google_trackConversion({
          google_conversion_id: Number(ADS_CONV_ID),
          google_conversion_label: ADS_CONV_LABEL,
          google_conversion_value: 1.0,
          google_conversion_currency: "USD",
          google_remarketing_only: false,
        });
      } catch (e3) {}
    }

    if (typeof window.gtag === "function") {
      try {
        if (userData && Object.keys(userData).length > 0) {
          window.gtag("set", "user_data", userData);
        }
        window.gtag("event", "conversion", {
          send_to: ADS_SEND_TO,
          value: 1.0,
          currency: "USD",
          transaction_id: leadId || undefined,
          user_data: userData || {},
        });
      } catch (e4) {}
    }
  }

  // Expose for Tag Assistant / manual diagnostics.
  window.peppFireAdsLeadConversion = fireAdsLeadConversion;

  var forms = document.querySelectorAll("form.lead-form");
  if (!forms.length) return;

  // Status strings default to Russian and can be overridden per form with
  // data-msg-* attributes, so the localised export landings answer the visitor
  // in their own language without a second copy of this handler.
  var FALLBACK_MSG = {
    sending: "Отправляем…",
    ok: "Спасибо! Заявка отправлена — мы свяжемся с вами.",
    "err-phone": "Укажите телефон.",
    "err-phone-invalid": "Проверьте номер телефона.",
    "err-consent": "Необходимо согласие на обработку данных.",
    "err-rate": "Слишком много попыток. Попробуйте позже.",
    "err-generic": "Не удалось отправить. Позвоните нам: +7 987 217-02-02.",
    "err-network": "Сеть недоступна. Позвоните нам: +7 987 217-02-02.",
  };

  forms.forEach(function (form) {
    var statusEl = form.querySelector(".lead-form__status");
    var btn = form.querySelector('button[type="submit"]');

    function msg(key) {
      return form.getAttribute("data-msg-" + key) || FALLBACK_MSG[key];
    }

    function setStatus(msg, kind) {
      if (!statusEl) return;
      statusEl.textContent = msg;
      statusEl.style.color =
        kind === "error" ? "#c0392b" : kind === "ok" ? "#1b7a3d" : "#666";
    }

    // Measurement (2026-09-09): form_start once per form fill, and a client
    // reference that lets the server and the analytics layer de-duplicate the
    // same lead if the visitor double-clicks, retries after a network error,
    // or reloads the page after sending.
    function newRef() {
      if (window.crypto && window.crypto.randomUUID) return window.crypto.randomUUID();
      return "r" + Date.now().toString(36) + Math.random().toString(36).slice(2, 10);
    }
    form.addEventListener("focusin", function () {
      if (form.dataset.started) return;
      form.dataset.started = "1";
      form.dataset.clientRef = form.dataset.clientRef || newRef();
      window.dataLayer = window.dataLayer || [];
      window.dataLayer.push({ event: "form_start", page: window.location.pathname,
        form_id: form.id || form.getAttribute("data-experiment-id") || "lead-form" });
      if (typeof ym === "function") ym(107064141, "reachGoal", "form_start");
    });

    form.addEventListener("submit", function (e) {
      e.preventDefault();

      var phone = (form.querySelector('[name="phone"]') || {}).value || "";
      var consent = form.querySelector('[name="consent"]');
      if (!phone.trim()) {
        setStatus(msg("err-phone"), "error");
        return;
      }
      if (consent && !consent.checked) {
        setStatus(msg("err-consent"), "error");
        return;
      }

      var message = (form.querySelector('[name="message"]') || {}).value || "";
      // Carry the ad click attribution into the lead card itself: the intake
      // server forwards `message` verbatim to the sales group, so the person who
      // calls back can see which campaign and country the buyer came from.
      if (typeof window.peppAttributionLine === "function") {
        var attrLine = window.peppAttributionLine();
        if (attrLine) message = (message ? message + "\n" : "") + "— " + attrLine;
      }

      var payload = {
        name: (form.querySelector('[name="name"]') || {}).value || "",
        phone: phone,
        message: message.slice(0, 1000),
        company: (form.querySelector('[name="company"]') || {}).value || "", // honeypot
        consent: consent ? consent.checked : false,
        page: window.location.pathname,
        experiment_id: form.getAttribute("data-experiment-id") || "",
        client_ref: form.dataset.clientRef || (form.dataset.clientRef = newRef()),
      };

      // Optional B2B category-landing fields (ignored by older intake builds;
      // also folded into `message` by category-landing.js for the sales group).
      ["category", "to", "mgr", "city", "shortlist", "calc_snapshot"].forEach(function (key) {
        var el = form.querySelector('[name="' + key + '"]');
        if (!el || !el.value) return;
        var val = el.value;
        if (key === "shortlist" || key === "calc_snapshot") {
          try {
            payload[key] = JSON.parse(val);
          } catch (err) {
            payload[key] = val;
          }
        } else {
          payload[key] = String(val).slice(0, 200);
        }
      });

      if (btn) {
        btn.disabled = true;
        btn.dataset.label = btn.textContent;
        btn.textContent = msg("sending");
      }
      setStatus(msg("sending"), "info");

      fetch("/lead-submit", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      })
        .then(function (r) {
          return r.json().then(function (data) {
            return { ok: r.ok, data: data };
          });
        })
        .then(function (res) {
          if (res.ok && res.data && res.data.ok) {
            form.reset();
            delete form.dataset.started;
            delete form.dataset.clientRef;
            setStatus(msg("ok"), "ok");
            try {
              // lead_submit_success is counted only when the server confirms
              // acceptance with a lead_id (honeypot hits and duplicates return
              // ok without one), and only once per lead_id in this session.
              var leadId = res.data.lead_id || "";
              var fired = [];
              try { fired = JSON.parse(sessionStorage.getItem("pepp_leads_fired") || "[]"); } catch (e0) {}
              if (leadId && !res.data.duplicate && fired.indexOf(leadId) === -1) {
                fired.push(leadId);
                try { sessionStorage.setItem("pepp_leads_fired", JSON.stringify(fired.slice(-20))); } catch (e1) {}

                // Google Ads enhanced conversions (hashed by gtag before sending);
                // this is the Ads path only — nothing personal enters the GA4 event below.
                var userData = {};
                if (payload.phone) {
                  var cleanPhone = payload.phone.replace(/[^\d+]/g, "");
                  if (cleanPhone.indexOf("+") !== 0) {
                    if (cleanPhone.length === 11 && cleanPhone.indexOf("7") === 0) {
                      cleanPhone = "+" + cleanPhone;
                    } else if (cleanPhone.length === 11 && cleanPhone.indexOf("8") === 0) {
                      cleanPhone = "+7" + cleanPhone.substring(1);
                    } else if (cleanPhone.length === 10) {
                      cleanPhone = "+7" + cleanPhone;
                    }
                  }
                  if (cleanPhone.length >= 10) {
                    userData.phone_number = cleanPhone;
                  }
                }
                if (payload.name) {
                  var nameParts = payload.name.trim().split(/\s+/);
                  if (nameParts[0]) userData.first_name = nameParts[0];
                  if (nameParts[1]) userData.last_name = nameParts[1];
                }

                window.dataLayer = window.dataLayer || [];
                var leadEvent = {
                  event: "generate_lead",
                  event_category: "lead",
                  event_action: "submit",
                  lead_id: leadId,
                  page: window.location.pathname,
                  page_lang: document.body.getAttribute("data-lang") || document.documentElement.lang || "",
                  page_country: document.body.getAttribute("data-country") || ""
                };
                if (typeof window.peppAttribution === "function") {
                  leadEvent.attribution = window.peppAttribution();
                }
                window.dataLayer.push(leadEvent);
                if (typeof ym === "function") ym(107064141, "reachGoal", "lead_submit_success");
                fireAdsLeadConversion(userData, leadId);
              }
            } catch (err) {}
          } else {
            var err = (res.data && res.data.error) || "unknown";
            var key =
              err === "invalid_phone"
                ? "err-phone-invalid"
                : err === "consent_required"
                ? "err-consent"
                : err === "rate_limited"
                ? "err-rate"
                : "err-generic";
            setStatus(msg(key), "error");
          }
        })
        .catch(function () {
          setStatus(msg("err-network"), "error");
        })
        .finally(function () {
          if (btn) {
            btn.disabled = false;
            if (btn.dataset.label) btn.textContent = btn.dataset.label;
          }
        });
    });
  });

  // Global interaction tracking for tel:, mailto:, messengers, and price downloads
  if (!window.__interactionTrackerLoaded) {
    window.__interactionTrackerLoaded = true;
    document.addEventListener("click", function (e) {
      var link = e.target.closest("a");
      if (!link) return;
      var href = link.getAttribute("href") || "";
      var text = link.textContent || "";
      var sendEvt = function (eventName, cat) {
        if (typeof ym === "function") ym(107064141, "reachGoal", eventName);
        window.dataLayer = window.dataLayer || [];
        window.dataLayer.push({
          event: eventName,
          event_category: cat || "interaction",
          event_label: href,
          page: window.location.pathname
        });
        if (typeof window.gtag === "function") {
          window.gtag("event", eventName, {
            event_category: cat || "interaction",
            event_label: href,
            page: window.location.pathname
          });
        }
      };
      if (href.indexOf("tel:") === 0) sendEvt("click_phone", "contact");
      if (href.indexOf("mailto:") === 0) sendEvt("click_email", "contact");
      if (/wa\.me|whatsapp|t\.me\//i.test(href)) sendEvt("click_messenger", "contact");
      if (/прайс|price|\.(pdf|xlsx?|csv)(\?|$)/i.test(href) || /прайс|price/i.test(text)) sendEvt("download_price", "engagement");
    });
  }
})();
