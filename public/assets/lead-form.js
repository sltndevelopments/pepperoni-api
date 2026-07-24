/* Lead-capture form handler for pepperoni.tatar
 * Posts to same-origin /lead-submit (nginx -> Flask lead-intake -> leads group).
 * Works for any <form class="lead-form"> on the page. Attribution: the current
 * pathname is sent as `page`; an optional data-experiment-id sets `experiment_id`.
 * 152-ФЗ: submission is blocked client-side unless the consent box is checked;
 * the server also re-checks consent.
 */
(function () {
  "use strict";
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
              window.dataLayer = window.dataLayer || [];
              window.dataLayer.push({
                event: "generate_lead",
                event_category: "lead",
                event_action: "submit",
                page: window.location.pathname
              });
              if (typeof gtag === "function") {
                gtag("event", "generate_lead", {
                  event_category: "lead",
                  event_label: window.location.pathname
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
})();
