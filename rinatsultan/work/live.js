
document.documentElement.classList.add("js");
const MONTHS = "января февраля марта апреля мая июня июля августа сентября октября ноября декабря".split(" ");
function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (ch) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  }[ch]));
}
function ruDay(iso) {
  if (!iso) return "дата не отмечена";
  const [y, m, d] = iso.slice(0, 10).split("-").map(Number);
  if (!y || !m || !d) return "дата не отмечена";
  return d + " " + MONTHS[m - 1] + " " + y;
}
function ledger(items) {
  if (!items.length) {
    return "<article class='card'><h3>Сейчас тихий период</h3><p>За последние три недели новых правок в публичном контуре нет.</p></article>";
  }
  return items.map((item, i) => (
    "<article class='card'>" +
    "<p class='when'>" + String(i + 1).padStart(2, "0") + " · " + esc(ruDay(item.seen)) + "</p>" +
    "<h3>" + esc(item.title) + "</h3><p>" + esc(item.note) + "</p></article>"
  )).join("");
}
function chapters(items) {
  if (!items.length) {
    return "<article class='chapter'><div><h3>Пока нет опубликованных кейсов</h3><p>Когда решение начинает открываться, оно появляется здесь.</p></div></article>";
  }
  return items.map((item, i) => {
    const pills = ["<span class='pill'>" + esc(item.state) + "</span>"];
    if (item.fresh) pills.push("<span class='pill pill-live'>сейчас дорабатывается</span>");
    const facts = (item.points || []).map((point) => "<li>" + esc(point) + "</li>").join("");
    const body = item.body ? "<p>" + esc(item.body) + "</p>" : "";
    return "<article class='chapter'><p class='num'>" + String(i + 1).padStart(2, "0") + "</p><div>" +
      "<div class='pills'>" + pills.join("") + "</div><h3>" + esc(item.title) + "</h3>" +
      "<p class='lead-in'>" + esc(item.summary) + "</p>" + body +
      "<ul class='facts'>" + facts + "</ul></div></article>";
  }).join("");
}
function tokenLabel(value) {
  const n = Number(value) || 0;
  if (n >= 1e9) return (n / 1e9).toFixed(1) + "B";
  if (n >= 1e6) return (n / 1e6).toFixed(1) + "M";
  return String(Math.round(n));
}
function hoursLabel(seconds) {
  const minutes = Math.floor((Number(seconds) || 0) / 60);
  const h = Math.floor(minutes / 60);
  const m = String(minutes % 60).padStart(2, "0");
  return h + " ч " + m + " мин";
}
function cursorBoard(cursor) {
  if (!cursor) return "";
  const series = cursor.series || [];
  const max = Math.max.apply(null, series.map((point) => point.count).concat([1]));
  const points = series.map((point, index) => {
    const x = series.length === 1 ? 0 : (index / (series.length - 1)) * 100;
    const y = 100 - (point.count / max) * 100;
    return x.toFixed(2) + "," + y.toFixed(2);
  }).join(" ");
  const spark = points
    ? '<svg class="spark" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true"><polyline points="' + points + '" fill="none" stroke="#e4c56a" stroke-width="1.6" vector-effect="non-scaling-stroke"/></svg>'
    : "";
  const heat = (cursor.heat || []).map((cell) => (
    '<i class="heat h' + cell.level + '" title="' + esc(cell.date) + ": " + tokenLabel(cell.count) + '"></i>'
  )).join("");
  return '<div class="cursor-board">' +
    '<p class="eyebrow">cursor.com/@' + esc(cursor.handle) + " · публичный профиль</p>" +
    '<div class="token-row"><b class="token" data-tokens="' + cursor.window_tokens + '">' + tokenLabel(cursor.window_tokens) + '</b><span>токенов с 29 августа</span></div>' +
    spark +
    '<div class="mini">' +
    "<div><b>" + cursor.agents + "</b><span>агентов · " + cursor.agents_local + " локально · " + cursor.agents_cloud + " в облаке</span></div>" +
    "<div><b>" + cursor.current_streak + "</b><span>дней подряд · рекорд " + cursor.longest_streak + "</span></div>" +
    "<div><b>" + hoursLabel(cursor.longest_agent_seconds) + "</b><span>самый долгий агент</span></div>" +
    "<div><b>" + tokenLabel(cursor.today_tokens) + "</b><span>токенов за последний день профиля</span></div>" +
    "<div><b>" + tokenLabel(cursor.all_tokens) + "</b><span>токенов с января</span></div>" +
    "</div>" +
    '<div class="heat-row" aria-hidden="true">' + heat + "</div></div>";
}
function countUp(node) {
  const target = Number(node.getAttribute("data-tokens")) || 0;
  const started = performance.now();
  function frame(now) {
    const t = Math.min(1, (now - started) / 1200);
    const eased = 1 - Math.pow(1 - t, 3);
    node.textContent = tokenLabel(Math.round(target * eased));
    if (t < 1) requestAnimationFrame(frame);
  }
  requestAnimationFrame(frame);
}
function paint(data) {
  const cases = data.cases || [];
  const active = data.active || [];
  const countCases = document.getElementById("count-cases");
  const countActive = document.getElementById("count-active");
  if (countCases) countCases.textContent = String(cases.length).padStart(2, "0");
  if (countActive) countActive.textContent = String(active.length).padStart(2, "0");
  const ledgerRoot = document.querySelector(".ledger-list");
  const chapterRoot = document.querySelector(".chapters");
  if (ledgerRoot) ledgerRoot.innerHTML = ledger(active);
  if (chapterRoot) chapterRoot.innerHTML = chapters(cases);
  const panel = document.getElementById("cursor-panel");
  if (panel && data.cursor) {
    const previous = panel.querySelector(".token");
    const previousValue = previous ? previous.getAttribute("data-tokens") : "";
    panel.innerHTML = cursorBoard(data.cursor);
    const token = panel.querySelector(".token");
    if (token && token.getAttribute("data-tokens") !== previousValue) countUp(token);
  }
  watch();
}
function watch() {
  const nodes = document.querySelectorAll(".reveal:not(.is-in)");
  if (!("IntersectionObserver" in window)) {
    nodes.forEach((node) => node.classList.add("is-in"));
    return;
  }
  const io = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        entry.target.classList.add("is-in");
        io.unobserve(entry.target);
      }
    });
  }, { threshold: 0.18 });
  nodes.forEach((node) => io.observe(node));
}
let stamp = "";
async function tick() {
  const node = document.getElementById("live");
  const label = node && node.querySelector("span");
  try {
    const response = await fetch("/work/work.json?t=" + Date.now(), { cache: "no-store" });
    if (!response.ok) throw new Error(String(response.status));
    const data = await response.json();
    if (data.generated_at !== stamp) {
      stamp = data.generated_at || "";
      paint(data);
    }
    const serverDate = new Date(response.headers.get("date") || Date.now());
    const clock = serverDate.toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
    const ru = document.documentElement.lang !== "en";
    if (node) node.dataset.state = "up";
    if (label) label.textContent = (ru ? "сервер на связи · " : "server connected · ") + clock;
  } catch (error) {
    const ru = document.documentElement.lang !== "en";
    if (node) node.dataset.state = "down";
    if (label) label.textContent = ru ? "сервер не ответил" : "server did not answer";
  }
}
tick();
setInterval(tick, 15000);
