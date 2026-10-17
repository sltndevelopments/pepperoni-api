/* Lazy-load /assets/lead-form.js on the LCP hubs.
 * Inject once on: first focusin/pointerdown/touchstart inside form.lead-form,
 * or when the form is within 600px of the viewport, or ≥3s after `load`
 * (requestIdleCallback). Exposes __peppInjectLeadForm for unit tests.
 */
(function (root) {
  var SRC = (root.document && root.document.currentScript &&
    root.document.currentScript.getAttribute("data-src")) || "/assets/lead-form.js";
  var injected = false;
  var pendingSubmit = null;

  function inject(cb) {
    if (injected) {
      if (typeof cb === "function") cb();
      return false;
    }
    injected = true;
    var doc = root.document;
    var s = doc.createElement("script");
    s.src = SRC;
    s.async = true;
    s.onload = function () {
      if (typeof cb === "function") cb();
    };
    s.onerror = function () {
      if (pendingSubmit && pendingSubmit.action) {
        pendingSubmit.submit();
      }
      if (typeof cb === "function") cb();
    };
    (doc.head || doc.documentElement).appendChild(s);
    return true;
  }

  function formOf(el) {
    if (!el) return null;
    if (el.matches && el.matches("form.lead-form")) return el;
    return el.closest ? el.closest("form.lead-form") : null;
  }

  function replay(form, type) {
    if (!form) return;
    if (type === "focusin") {
      form.dispatchEvent(new root.Event("focusin", { bubbles: true }));
      return;
    }
    if (type === "submit") {
      if (typeof form.requestSubmit === "function") form.requestSubmit();
      else form.dispatchEvent(new root.Event("submit", { bubbles: true, cancelable: true }));
    }
  }

  function onInteract(e) {
    var form = formOf(e.target);
    if (!form) return;
    if (e.type === "submit") {
      if (root.__leadFormJs) return;
      e.preventDefault();
      pendingSubmit = form;
    }
    inject(function () {
      replay(form, e.type === "submit" ? "submit" : e.type === "focusin" ? "focusin" : "");
    });
  }

  function arm() {
    var doc = root.document;
    ["focusin", "pointerdown", "touchstart"].forEach(function (ev) {
      doc.addEventListener(ev, function (e) {
        if (formOf(e.target)) onInteract(e);
      }, true);
    });
    doc.addEventListener("submit", function (e) {
      if (formOf(e.target)) onInteract(e);
    }, true);

    var forms = doc.querySelectorAll("form.lead-form");
    if (root.IntersectionObserver && forms.length) {
      var io = new root.IntersectionObserver(function (entries) {
        for (var i = 0; i < entries.length; i++) {
          if (entries[i].isIntersecting) {
            inject();
            io.disconnect();
            break;
          }
        }
      }, { rootMargin: "600px 0px" });
      for (var j = 0; j < forms.length; j++) io.observe(forms[j]);
    }

    function idleInject() {
      var ric = root.requestIdleCallback || function (cb) { return root.setTimeout(cb, 1); };
      ric(function () { inject(); }, { timeout: 3000 });
    }
    function afterLoad() {
      root.setTimeout(idleInject, 3000);
    }
    if (doc.readyState === "complete") afterLoad();
    else root.addEventListener("load", afterLoad);
  }

  root.__peppInjectLeadForm = inject;
  root.__peppArmLeadFormLazy = arm;
  if (!root.__peppLeadFormLazyTest) arm();
})(typeof window !== "undefined" ? window : globalThis);
