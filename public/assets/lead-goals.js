/* Metrika/GTM goals for contact clicks on pages that do not load lead-form.js.
 * Same goal names as lead-form.js (shared guard, so never double-fires):
 * micro_phone_click, micro_email_click, micro_messenger_click.
 * The successful-lead goal `lead_form_submit` fires only in lead-form.js after
 * the server confirms the lead (form_submit in page HTML = attempt only). */
(function () {
  "use strict";
  if (window.__interactionTrackerLoaded) return;
  window.__interactionTrackerLoaded = true;
  document.addEventListener("click", function (e) {
    var link = e.target && e.target.closest ? e.target.closest("a") : null;
    if (!link) return;
    var href = link.getAttribute("href") || "";
    var name = href.indexOf("tel:") === 0 ? "micro_phone_click"
      : href.indexOf("mailto:") === 0 ? "micro_email_click"
      : /wa\.me|whatsapp|t\.me\//i.test(href) ? "micro_messenger_click" : "";
    if (!name) return;
    if (typeof ym === "function") ym(107064141, "reachGoal", name);
    window.dataLayer = window.dataLayer || [];
    window.dataLayer.push({ event: name, event_category: "micro", event_label: href, page: location.pathname });
  });
})();
