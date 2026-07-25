/* Google Marketing Platform instrumentation for the /pepperoni export landings.
 *
 * Integration surface is the dataLayer: every signal below is pushed as a named
 * event so GTM (GTM-W2Q5S8HF) maps it to Google Ads conversions / GA4 without
 * touching this file again. Conversions are deliberately NOT fired with gtag()
 * here — lead-form.js already fires the Ads lead conversion, and firing again
 * from GTM would double-count.
 *
 * Reads its context from <body data-lang data-country data-sku data-value
 * data-currency>. Requires no consent gate itself: Consent Mode v2 defaults are
 * set inline in <head> before the tag loads.
 */
(function () {
  "use strict";

  var body = document.body;
  var CTX = {
    lang: body.getAttribute("data-lang") || document.documentElement.lang || "ru",
    country: body.getAttribute("data-country") || "",
    sku: body.getAttribute("data-sku") || "",
    value: parseFloat(body.getAttribute("data-value") || "0") || 0,
    currency: body.getAttribute("data-currency") || "RUB",
  };

  window.dataLayer = window.dataLayer || [];

  function push(event, extra) {
    var payload = {
      event: event,
      page_lang: CTX.lang,
      page_country: CTX.country,
      product_sku: CTX.sku,
      page_type: "export_landing",
    };
    if (extra) {
      Object.keys(extra).forEach(function (k) {
        payload[k] = extra[k];
      });
    }
    window.dataLayer.push(payload);
  }

  /* ---------------------------------------------------------------- attribution
   * Ad click ids must survive the whole session: a B2B buyer often lands from the
   * ad, leaves, and submits later from a direct visit. Persisting them lets the
   * lead be imported back into Google Ads as an offline conversion.
   */
  var ATTR_KEY = "pepp_attr_v1";
  var ATTR_TTL = 90 * 24 * 60 * 60 * 1000;
  var TRACKED_PARAMS = [
    "gclid", "gbraid", "wbraid", "gad_source", "gad_campaignid", "gclsrc",
    "utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term", "utm_id",
    "campaignid", "adgroupid", "creative", "keyword", "matchtype", "network",
    "device", "placement", "loc_physical_ms", "yclid", "fbclid",
  ];

  function readStored() {
    try {
      var raw = window.localStorage.getItem(ATTR_KEY);
      if (!raw) return null;
      var parsed = JSON.parse(raw);
      if (!parsed || !parsed.t || Date.now() - parsed.t > ATTR_TTL) return null;
      return parsed;
    } catch (e) {
      return null;
    }
  }

  function captureAttribution() {
    var qs = new URLSearchParams(window.location.search);
    var fresh = {};
    TRACKED_PARAMS.forEach(function (p) {
      var v = qs.get(p);
      if (v) fresh[p] = v.slice(0, 200);
    });

    var stored = readStored();
    // A new ad click overwrites the stored attribution; otherwise keep the first
    // touch so a later direct visit is still credited to the campaign.
    var isNewClick = fresh.gclid || fresh.gbraid || fresh.wbraid || fresh.utm_source;
    var data = isNewClick || !stored ? fresh : stored.d || {};

    if (!data.landing_page) data.landing_page = window.location.pathname;
    if (!data.first_seen) data.first_seen = new Date().toISOString().slice(0, 10);
    if (!data.referrer && document.referrer && document.referrer.indexOf(location.host) === -1) {
      data.referrer = document.referrer.slice(0, 200);
    }

    try {
      window.localStorage.setItem(ATTR_KEY, JSON.stringify({ t: Date.now(), d: data }));
    } catch (e) {}
    return data;
  }

  var attribution = captureAttribution();

  // Contract consumed by lead-form.js so the sales team and Google Ads offline
  // import both see where the lead came from.
  window.peppAttribution = function () {
    return JSON.parse(JSON.stringify(attribution));
  };
  window.peppAttributionLine = function () {
    var order = ["utm_source", "utm_medium", "utm_campaign", "campaignid", "keyword", "gclid"];
    var parts = [];
    order.forEach(function (k) {
      if (attribution[k]) parts.push(k.replace("utm_", "") + "=" + attribution[k]);
    });
    parts.push("lang=" + CTX.lang);
    if (CTX.country) parts.push("geo=" + CTX.country);
    return parts.join(" ");
  };

  // Mirror the ad click id into every lead form so it is posted with the lead.
  document.querySelectorAll("form.lead-form").forEach(function (form) {
    ["gclid", "utm_source", "utm_campaign"].forEach(function (key) {
      if (!attribution[key] || form.querySelector('[name="' + key + '"]')) return;
      var input = document.createElement("input");
      input.type = "hidden";
      input.name = key;
      input.value = attribution[key];
      form.appendChild(input);
    });
  });

  /* --------------------------------------------------------------- landing view
   * ecomm_* keys are the Google Ads dynamic remarketing parameters, so Display
   * and Demand Gen campaigns can build product-aware audiences from this page.
   */
  push("landing_view", {
    ecomm_prodid: CTX.sku,
    ecomm_pagetype: "product",
    ecomm_totalvalue: CTX.value,
    currency: CTX.currency,
    attribution_source: attribution.utm_source || (attribution.gclid ? "google" : "direct"),
  });

  /* -------------------------------------------------------------- scroll depth */
  var depthsSeen = {};
  var DEPTHS = [25, 50, 75, 90];
  function onScroll() {
    var doc = document.documentElement;
    var scrollable = doc.scrollHeight - window.innerHeight;
    if (scrollable <= 0) return;
    var pct = ((window.scrollY || doc.scrollTop) / scrollable) * 100;
    DEPTHS.forEach(function (d) {
      if (pct >= d && !depthsSeen[d]) {
        depthsSeen[d] = true;
        push("scroll_depth", { percent_scrolled: d });
      }
    });
    if (depthsSeen[90]) window.removeEventListener("scroll", onScroll);
  }
  window.addEventListener("scroll", onScroll, { passive: true });

  /* ---------------------------------------------------------------- time on page
   * 30s+ on a B2B spec page is a real reading session — useful as a soft
   * conversion to feed Smart Bidding while hard leads are still scarce.
   */
  [15, 30, 60, 120].forEach(function (sec) {
    window.setTimeout(function () {
      if (document.visibilityState === "visible") {
        push("engaged_time", { engagement_seconds: sec });
      }
    }, sec * 1000);
  });

  /* ------------------------------------------------------------- section views */
  if ("IntersectionObserver" in window) {
    var sectionObserver = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (!entry.isIntersecting) return;
          push("section_view", { section_name: entry.target.getAttribute("data-track-section") });
          sectionObserver.unobserve(entry.target);
        });
      },
      { threshold: 0.4 }
    );
    document.querySelectorAll("[data-track-section]").forEach(function (el) {
      sectionObserver.observe(el);
    });
  }

  /* ------------------------------------------------------------ country switch */
  document.addEventListener("click", function (e) {
    var el = e.target.closest("[data-country-code]");
    if (!el) return;
    push("select_country", {
      selected_country: el.getAttribute("data-country-code"),
      selected_language: el.getAttribute("data-country-lang") || "",
    });
  });

  /* ---------------------------------------------------------------------- video
   * The poster is a same-origin JPEG and the iframe is only created on click:
   * YouTube costs nothing on first paint, and the page still renders where
   * youtube.com itself is slow.
   */
  var ytApiRequested = false;
  var pendingPlayers = [];

  function requestYouTubeApi() {
    if (ytApiRequested) return;
    ytApiRequested = true;
    var s = document.createElement("script");
    s.src = "https://www.youtube.com/iframe_api";
    s.async = true;
    document.head.appendChild(s);
  }

  window.onYouTubeIframeAPIReady = function () {
    while (pendingPlayers.length) pendingPlayers.shift()();
  };

  function attachPlayer(iframe, videoId, title) {
    var milestonesSeen = {};
    var poll = null;

    function build() {
      /* global YT */
      new YT.Player(iframe, {
        events: {
          onStateChange: function (event) {
            var player = event.target;
            if (event.data === YT.PlayerState.PLAYING) {
              push("video_start", { video_title: title, video_id: videoId });
              window.clearInterval(poll);
              poll = window.setInterval(function () {
                var duration = player.getDuration();
                if (!duration) return;
                var pct = (player.getCurrentTime() / duration) * 100;
                [25, 50, 75].forEach(function (m) {
                  if (pct >= m && !milestonesSeen[m]) {
                    milestonesSeen[m] = true;
                    push("video_progress", {
                      video_title: title,
                      video_id: videoId,
                      video_percent: m,
                    });
                  }
                });
              }, 1000);
            } else if (event.data === YT.PlayerState.ENDED) {
              window.clearInterval(poll);
              if (!milestonesSeen.done) {
                milestonesSeen.done = true;
                push("video_complete", { video_title: title, video_id: videoId });
              }
            } else if (event.data === YT.PlayerState.PAUSED) {
              window.clearInterval(poll);
            }
          },
        },
      });
    }

    if (window.YT && window.YT.Player) build();
    else {
      pendingPlayers.push(build);
      requestYouTubeApi();
    }
  }

  document.querySelectorAll("[data-video-id]").forEach(function (facade) {
    facade.addEventListener("click", function () {
      if (facade.getAttribute("data-loaded") === "1") return;
      facade.setAttribute("data-loaded", "1");

      var videoId = facade.getAttribute("data-video-id");
      var title = facade.getAttribute("data-video-title") || videoId;
      var isShort = facade.getAttribute("data-video-short") === "1";

      var iframe = document.createElement("iframe");
      iframe.src =
        "https://www.youtube-nocookie.com/embed/" +
        encodeURIComponent(videoId) +
        "?autoplay=1&rel=0&modestbranding=1&playsinline=1&enablejsapi=1&origin=" +
        encodeURIComponent(window.location.origin) +
        (isShort ? "&loop=1&playlist=" + encodeURIComponent(videoId) : "");
      iframe.title = title;
      iframe.allow =
        "accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share";
      iframe.allowFullscreen = true;
      iframe.loading = "eager";
      iframe.setAttribute("frameborder", "0");

      facade.innerHTML = "";
      facade.appendChild(iframe);
      push("video_open", { video_title: title, video_id: videoId });
      attachPlayer(iframe, videoId, title);
    });
  });
})();
