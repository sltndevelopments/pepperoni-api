/* Lead-capture form handler for pepperoni.tatar
 * Posts to same-origin /lead-submit (nginx -> Flask lead-intake -> leads group).
 * Works for any <form class="lead-form"> on the page. Attribution: the current
 * pathname is sent as `page`; an optional data-experiment-id sets `experiment_id`.
 * 152-ФЗ: submission is blocked client-side unless the consent box is checked;
 * the server also re-checks consent.
 */
(function () {
  "use strict";

  // Google Tag (AW-18346189266) for Google Ads conversion tracking
  if (!window.__gtagAdsLoaded) {
    window.__gtagAdsLoaded = true;
    window.dataLayer = window.dataLayer || [];
    if (typeof window.gtag !== "function") {
      window.gtag = function () { window.dataLayer.push(arguments); };
    }
    window.gtag("js", new Date());
    window.gtag("config", "AW-18346189266");

    var gScript = document.createElement("script");
    gScript.async = true;
    gScript.src = "https://www.googletagmanager.com/gtag/js?id=AW-18346189266";
    document.head.appendChild(gScript);
  }

  var forms = document.querySelectorAll("form.lead-form");
  if (!forms.length) return;

  forms.forEach(function (form) {
    var statusEl = form.querySelector(".lead-form__status");
    var btn = form.querySelector('button[type="submit"]');

    function setStatus(msg, kind) {
      if (!statusEl) return;
      statusEl.textContent = msg;
      statusEl.style.color =
        kind === "error" ? "#c0392b" : kind === "ok" ? "#1b7a3d" : "#666";
    }

    form.addEventListener("submit", function (e) {
      e.preventDefault();

      var phone = (form.querySelector('[name="phone"]') || {}).value || "";
      var consent = form.querySelector('[name="consent"]');
      if (!phone.trim()) {
        setStatus("Укажите телефон.", "error");
        return;
      }
      if (consent && !consent.checked) {
        setStatus("Необходимо согласие на обработку данных.", "error");
        return;
      }

      var payload = {
        name: (form.querySelector('[name="name"]') || {}).value || "",
        phone: phone,
        message: (form.querySelector('[name="message"]') || {}).value || "",
        company: (form.querySelector('[name="company"]') || {}).value || "", // honeypot
        consent: consent ? consent.checked : false,
        page: window.location.pathname,
        experiment_id: form.getAttribute("data-experiment-id") || "",
      };

      if (btn) {
        btn.disabled = true;
        btn.dataset.label = btn.textContent;
        btn.textContent = "Отправляем…";
      }
      setStatus("Отправляем…", "info");

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
            setStatus("Спасибо! Заявка отправлена — мы свяжемся с вами.", "ok");
            try {
              // Enhanced Conversions: prepare user_data
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
              window.dataLayer.push({
                event: "generate_lead",
                event_category: "lead",
                event_action: "submit",
                page: window.location.pathname,
                user_data: userData
              });
              if (typeof window.gtag === "function") {
                if (Object.keys(userData).length > 0) {
                  window.gtag("set", "user_data", userData);
                }
                window.gtag("event", "conversion", {
                  send_to: "AW-18346189266",
                  user_data: userData
                });
                window.gtag("event", "generate_lead", {
                  event_category: "lead",
                  event_label: window.location.pathname,
                  user_data: userData
                });
              }
            } catch (err) {}
          } else {
            var err = (res.data && res.data.error) || "unknown";
            var msg =
              err === "invalid_phone"
                ? "Проверьте номер телефона."
                : err === "consent_required"
                ? "Необходимо согласие на обработку данных."
                : err === "rate_limited"
                ? "Слишком много попыток. Попробуйте позже."
                : "Не удалось отправить. Позвоните нам: +7 987 217-02-02.";
            setStatus(msg, "error");
          }
        })
        .catch(function () {
          setStatus(
            "Сеть недоступна. Позвоните нам: +7 987 217-02-02.",
            "error"
          );
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
