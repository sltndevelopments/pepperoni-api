/* rinatsultan.com — motion layer. Vanilla JS, no dependencies. */

(() => {
  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* --- scroll reveal --- */
  const io = new IntersectionObserver(
    (entries) => {
      for (const e of entries) {
        if (e.isIntersecting) {
          e.target.classList.add("in");
          io.unobserve(e.target);
        }
      }
    },
    { threshold: 0.12, rootMargin: "0px 0px -6% 0px" }
  );
  document.querySelectorAll(".reveal").forEach((el) => io.observe(el));

  /* --- number counters --- */
  const animateCount = (el) => {
    const to = parseFloat(el.dataset.to);
    const dec = parseInt(el.dataset.dec || "0", 10);
    if (reduced) {
      el.textContent = to.toFixed(dec).replace(".", ",");
      return;
    }
    const dur = 1600;
    const t0 = performance.now();
    const tick = (t) => {
      const p = Math.min((t - t0) / dur, 1);
      const eased = 1 - Math.pow(1 - p, 4);
      el.textContent = (to * eased).toFixed(dec).replace(".", ",");
      if (p < 1) requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  };
  const cio = new IntersectionObserver(
    (entries) => {
      for (const e of entries) {
        if (e.isIntersecting) {
          animateCount(e.target);
          cio.unobserve(e.target);
        }
      }
    },
    { threshold: 0.6 }
  );
  document.querySelectorAll(".count").forEach((el) => cio.observe(el));

  /* --- reading progress --- */
  const bar = document.getElementById("progressBar");
  const onScroll = () => {
    const h = document.documentElement;
    const max = h.scrollHeight - h.clientHeight;
    bar.style.width = (max > 0 ? (h.scrollTop / max) * 100 : 0) + "%";
  };
  document.addEventListener("scroll", onScroll, { passive: true });
  onScroll();

  if (reduced) return;

  /* --- moon parallax (scroll + pointer) --- */
  const moon = document.querySelector(".moon");
  let mx = 0, my = 0, tx = 0, ty = 0, sy = 0;
  window.addEventListener(
    "pointermove",
    (e) => {
      mx = (e.clientX / window.innerWidth - 0.5) * 2;
      my = (e.clientY / window.innerHeight - 0.5) * 2;
    },
    { passive: true }
  );
  const drift = () => {
    sy += (window.scrollY - sy) * 0.06;
    tx += (mx - tx) * 0.04;
    ty += (my - ty) * 0.04;
    moon.style.transform = `translate3d(${tx * 26}px, ${sy * 0.12 + ty * 20}px, 0)`;
    requestAnimationFrame(drift);
  };
  requestAnimationFrame(drift);

  /* --- magnetic buttons --- */
  document.querySelectorAll(".magnetic").forEach((btn) => {
    const strength = 14;
    btn.addEventListener("pointermove", (e) => {
      const r = btn.getBoundingClientRect();
      const x = ((e.clientX - r.left) / r.width - 0.5) * 2;
      const y = ((e.clientY - r.top) / r.height - 0.5) * 2;
      btn.style.transform = `translate(${x * strength * 0.4}px, ${y * strength * 0.3}px)`;
    });
    btn.addEventListener("pointerleave", () => {
      btn.style.transform = "";
    });
  });
})();

/* --- site checks: isitagentready inline + PageSpeed deep-link --- */
(() => {
  const form = document.getElementById("siteCheck");
  if (!form) return;
  const input = document.getElementById("siteUrl");
  const psi = document.getElementById("psiLink");
  const box = document.getElementById("agentBox");
  const head = document.getElementById("agentHead");
  const list = document.getElementById("agentList");
  const note = document.getElementById("agentNote");
  const en = document.documentElement.lang === "en";

  const normalize = (raw) => {
    let v = (raw || "").trim();
    if (!v) return "";
    if (!/^https?:\/\//i.test(v)) v = "https://" + v;
    return v;
  };

  const setPsi = (url) => {
    psi.href = url
      ? "https://pagespeed.web.dev/analysis?url=" + encodeURIComponent(url)
      : "https://pagespeed.web.dev/";
  };

  input.addEventListener("input", () => setPsi(normalize(input.value)));

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const url = normalize(input.value);
    if (!url) return;
    setPsi(url);
    window.open(psi.href, "_blank", "noopener");
    box.hidden = false;
    list.innerHTML = "";
    head.textContent = en ? "scanning…" : "сканирую…";
    note.textContent = en
      ? "PageSpeed opened in a new tab. Agent scan is running here."
      : "PageSpeed открылся в новой вкладке. Скан для агентов идёт здесь.";
    try {
      const res = await fetch("https://isitagentready.com/api/scan", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url }),
      });
      const data = await res.json();
      if (!res.ok || data.error) throw new Error(data.error || "scan failed");
      const level = data.levelName || data.level;
      head.textContent = (en ? "agent-ready: " : "готовность для агентов: ") + level;
      const rows = [];
      const checks = data.checks || {};
      for (const group of Object.values(checks)) {
        if (!group || typeof group !== "object") continue;
        for (const item of Object.values(group)) {
          if (!item || !item.status) continue;
          rows.push(item);
        }
      }
      const order = { fail: 0, warn: 1, warning: 1, pass: 2 };
      rows.sort((a, b) => (order[a.status] ?? 3) - (order[b.status] ?? 3));
      for (const item of rows.slice(0, 10)) {
        const li = document.createElement("li");
        const mark = item.status === "pass" ? "ok" : item.status === "fail" ? "fail" : "warn";
        li.innerHTML = `<span class="${mark}">${mark === "ok" ? "●" : mark === "fail" ? "✕" : "○"}</span><span>${item.message || item.status}</span>`;
        list.appendChild(li);
      }
    } catch (err) {
      head.textContent = en ? "could not finish the scan here" : "не удалось просканировать здесь";
      const a = document.createElement("a");
      a.href = "https://isitagentready.com/";
      a.target = "_blank";
      a.rel = "noopener";
      a.textContent = en ? "Open isitagentready.com →" : "Открыть isitagentready.com →";
      list.appendChild(Object.assign(document.createElement("li"), { innerHTML: "" }));
      list.lastChild.appendChild(a);
    }
  });

  if (navigator.modelContext && typeof navigator.modelContext.registerTool === "function") {
    navigator.modelContext.registerTool({
      name: "rinat_contact",
      description: "Contact Rinat Sultanov or summarize who he is and how he works with companies.",
      inputSchema: {
        type: "object",
        properties: {
          topic: { type: "string", description: "contact, services, or background" }
        }
      },
      execute: async ({ topic }) => ({
        name: "Rinat Sultanov",
        role: "Director of Development, Kazan Delicacies",
        site: "https://rinatsultan.com/",
        telegram: "https://t.me/TochnoRtutAloe",
        email: "995620@gmail.com",
        topic: topic || "contact"
      })
    });
  }
})();
