(function () {
  var tools = [
    {
      name: "search_products",
      description: "Search Kazan Delicacies halal catalog by name, SKU, or meat type",
      inputSchema: {
        type: "object",
        properties: { q: { type: "string", description: "Query, e.g. pepperoni" } },
        required: ["q"]
      },
      execute: function (args) {
        var q = (args && args.q) || "";
        return fetch("https://api.pepperoni.tatar/api/products?search=" + encodeURIComponent(q) + "&limit=10").then(function (r) { return r.json(); });
      }
    },
    {
      name: "get_product",
      description: "Full product card by SKU (KD-NNN)",
      inputSchema: {
        type: "object",
        properties: { sku: { type: "string" } },
        required: ["sku"]
      },
      execute: function (args) {
        return fetch("https://api.pepperoni.tatar/api/product/" + encodeURIComponent((args && args.sku) || "")).then(function (r) { return r.json(); });
      }
    },
    {
      name: "open_inquiry",
      description: "Open WhatsApp wholesale inquiry to +7 987 217-02-02",
      inputSchema: { type: "object", properties: {} },
      execute: function () {
        location.href = "https://wa.me/79872170202";
        return { ok: true };
      }
    }
  ];

  function attach(mc) {
    if (!mc) return;
    var i;
    if (typeof mc.registerTool === "function") {
      for (i = 0; i < tools.length; i++) mc.registerTool(tools[i]);
    }
    if (typeof mc.provideContext === "function") {
      mc.provideContext({ tools: tools });
    }
  }

  function boot() {
    try { attach(navigator.modelContext); } catch (e) {}
  }

  boot();
  if (document.addEventListener) {
    document.addEventListener("DOMContentLoaded", boot);
  }
})();
