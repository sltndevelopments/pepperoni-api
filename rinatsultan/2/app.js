/* rinatsultan.com/2 — Barajatr Edition JS */

(() => {
  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* --- Tape Timecode Ticker --- */
  const timeEl = document.getElementById("tapeTime");
  const spoolEl = document.getElementById("spoolIcon");
  
  if (timeEl) {
    let seconds = 0;
    setInterval(() => {
      seconds++;
      const m = String(Math.floor(seconds / 60)).padStart(2, "0");
      const s = String(seconds % 60).padStart(2, "0");
      timeEl.textContent = `${m}:${s}`;
    }, 1000);
  }

  /* --- Scroll reveal --- */
  const io = new IntersectionObserver(
    (entries) => {
      for (const e of entries) {
        if (e.isIntersecting) {
          e.target.classList.add("in");
          io.unobserve(e.target);
        }
      }
    },
    { threshold: 0.08, rootMargin: "0px 0px -4% 0px" }
  );
  document.querySelectorAll(".reveal").forEach((el) => io.observe(el));

  /* --- Spool acceleration on scroll --- */
  if (spoolEl && !reduced) {
    let scrollTimeout;
    window.addEventListener("scroll", () => {
      spoolEl.style.animationDuration = "1.2s";
      clearTimeout(scrollTimeout);
      scrollTimeout = setTimeout(() => {
        spoolEl.style.animationDuration = "6s";
      }, 150);
    }, { passive: true });
  }

  /* --- WebMCP Tool Registration (for agent discovery parity) --- */
  if (navigator.modelContext && typeof navigator.modelContext.registerTool === "function") {
    navigator.modelContext.registerTool({
      name: "rinat_profile_barajatr",
      description: "Get canonical facts about Rinat Sultanov, his manufacturing AI practice, and direct contact line.",
      inputSchema: {
        type: "object",
        properties: {
          topic: { type: "string", description: "profile, method, case, or contact" }
        }
      },
      execute: async ({ topic }) => ({
        name: "Rinat Sultanov",
        role: "Director of Development, Kazan Delicacies",
        positioning: "Architect of AI transformation for manufacturing companies",
        site: "https://rinatsultan.com/2",
        mcp: "https://rinatsultan.com/mcp",
        case: "https://rinatsultan.com/cases/ai-sales-agent/",
        telegram: "https://t.me/TochnoRtutAloe",
        email: "995620@gmail.com",
        topic: topic || "profile"
      })
    });
  }
})();
