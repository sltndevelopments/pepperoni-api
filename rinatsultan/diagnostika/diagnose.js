/* Owner-language diagnosis from the public contour only. */

(() => {
  const form = document.getElementById("diagnoseForm");
  if (!form) return;

  const urlInput = document.getElementById("dxUrl");
  const nameInput = document.getElementById("dxName");
  const note = document.getElementById("dxNote");
  const out = document.getElementById("result");
  const hostEl = document.getElementById("dxHost");
  const titleEl = document.getElementById("dxTitle");
  const subEl = document.getElementById("dxSub");
  const cardsEl = document.getElementById("dxCards");
  const demo = document.getElementById("dxDemo");

  const normalize = (raw) => {
    let v = (raw || "").trim();
    if (!v) return "";
    if (!/^https?:\/\//i.test(v)) v = "https://" + v;
    try {
      return new URL(v).href;
    } catch {
      return "";
    }
  };

  const hostOf = (url) => {
    try {
      return new URL(url).hostname.replace(/^www\./, "");
    } catch {
      return url;
    }
  };

  const flatten = (data) => {
    const rows = [];
    const checks = data && data.checks;
    if (!checks || typeof checks !== "object") return rows;
    for (const group of Object.values(checks)) {
      if (!group || typeof group !== "object") continue;
      for (const item of Object.values(group)) {
        if (!item || !item.status) continue;
        rows.push({
          status: String(item.status).toLowerCase(),
          text: String(item.message || item.name || item.id || ""),
        });
      }
    }
    return rows;
  };

  const blob = (rows) => rows.map((r) => r.text).join("\n");

  const match = (rows, re) => rows.filter((r) => re.test(r.text));

  const translateFail = (text) => {
    const rules = [
      [/dnssec|authenticated data|ad=false/i, "DNS не подписан. Машина не может подтвердить, что записи о домене настоящие."],
      [/llms\.txt/i, "Нет слоя llms.txt — нейросети не получают короткий, однозначный текст о компании."],
      [/markdown/i, "Нет текстовой версии страниц. Агент читает вёрстку, а не факты."],
      [/robots/i, "Правила для роботов закрывают или путают вход. Часть систем вас просто не читает."],
      [/mcp/i, "Нет программного входа для агентов. Человек открывает сайт, машина упирается."],
      [/sitemap/i, "Карта сайта слабая или отсутствует. Поиск и агенты хуже находят страницы."],
      [/oauth|well-known/i, "Нет стандартных адресов, по которым агент понимает, как к вам подключиться."],
      [/content-signal|ai-train/i, "Нет явного сигнала, что машинам можно опираться на этот текст."],
    ];
    for (const [re, line] of rules) {
      if (re.test(text)) return line;
    }
    return null;
  };

  const machineLines = (rows) => {
    const fails = rows.filter((r) => r.status === "fail" || r.status === "warn" || r.status === "warning");
    const seen = new Set();
    const lines = [];
    for (const row of fails) {
      const line = translateFail(row.text);
      if (!line || seen.has(line)) continue;
      seen.add(line);
      lines.push(line);
    }
    if (!lines.length && rows.length) {
      return ["По открытым проверкам грубых дыр не видно. Это не значит, что контур собран: виден только фасад."];
    }
    if (!lines.length) {
      return ["Публичный контур прочитать не удалось. Ниже — только метод, без претензии, что я видел ваш сайт."];
    }
    return lines.slice(0, 4);
  };

  const firstTouch = (host, rows) => {
    const text = blob(rows).toLowerCase();
    const h = host.toLowerCase();
    if (/wildberries|ozon|avito|market\.yandex/.test(h)) {
      return "Первичка, скорее всего, сидит в кабинетах маркетплейсов и в переписке менеджеров — не в одном контуре.";
    }
    if (/bitrix|1c-bitrix|tilda|wix|insales/.test(text + h)) {
      return "С улицы это витрина на типовой платформе. Первое касание, скорее всего, общая форма или почта, которую разбирают руками.";
    }
    if (rows.some((r) => /mcp|llms\.txt/i.test(r.text) && r.status === "pass")) {
      return "Сайт уже можно прочитать машиной. Первичка всё равно почти наверняка на людях: найти компанию, понять, подходит ли, написать первое письмо.";
    }
    return "С улицы компания выглядит как витрина. Поиск клиента, квалификация и первое письмо, скорее всего, до сих пор делают менеджеры — по часам, не по контуру.";
  };

  const reversible = (host) => {
    const food = /meat|halal|milk|food|meat|мяс|халял|молоч|хлеб|птиц|деликатес|pepperoni/.test(host.toLowerCase());
    const extra = food
      ? " По открытому ассортименту агент может собрать досье покупателя. По цеху — нет."
      : "";
    return "Отдать можно только обратимое: найти компанию, собрать досье, написать черновик первого письма. Это можно остановить. Человеку остаются переговоры и цена." + extra;
  };

  const boundary = (host) => {
    const food = /meat|halal|milk|food|мяс|халял|молоч|хлеб|птиц|деликатес|pepperoni/.test(host.toLowerCase());
    if (food) {
      return "Нельзя отдавать отгрузку, сертификат, рецептуру и требования сети. В пищевом контуре ошибка стоит партии, а не письма. Граница чертится до автоматизации.";
    }
    return "Нельзя отдавать отгрузку, деньги, сертификаты и то, что нельзя откатить. Письмо останавливается. Фура и подпись — нет.";
  };

  const pilot = (rows) => {
    const fails = rows.filter((r) => r.status === "fail");
    const blind = fails.some((r) => /llms|markdown|robots|mcp/i.test(r.text));
    const sales = "Один пилот на 90 дней: первичная работа отдела продаж. До старта фиксируем «как есть». Через 90 дней смотрим часы и ответы, не слайды. У нас на заводе контур написал 655 первых писем и вернул менеджерам около 200 часов.";
    if (blind) {
      return sales + " Параллельно имеет смысл починить фасад: чтобы компанию одинаково находили в поиске и в ответах нейросетей. Это не замена пилоту продаж.";
    }
    return sales;
  };

  const render = ({ url, name, rows, scanned }) => {
    const host = hostOf(url);
    const who = (name || "").trim() || host;
    hostEl.textContent = scanned ? host + " · открытый контур" : host + " · контур не прочитан";
    titleEl.textContent = "Как это выглядит для «" + who + "»";
    subEl.textContent = scanned
      ? "Пять строк ниже: что видно с улицы и какой порядок я бы держал. Это не диагноз цеха."
      : "Скан фасада не прошёл. Порядок всё равно тот же — без выдуманных фактов о вашей компании.";

    const items = [
      { n: "01", h: "Где сидит первичка", p: firstTouch(host, rows) },
      { n: "02", h: "Что можно отдать агенту", p: reversible(host) },
      { n: "03", h: "Чего нельзя ломать", p: boundary(host) },
      { n: "04", h: "Один пилот на 90 дней", p: pilot(rows) },
      { n: "05", h: "Что машины уже видят криво", p: machineLines(rows).join(" ") },
    ];

    cardsEl.replaceChildren();
    for (const item of items) {
      const li = document.createElement("li");
      li.className = "dx-card";
      const n = document.createElement("span");
      n.className = "dx-n mono";
      n.textContent = item.n;
      const h = document.createElement("h3");
      h.textContent = item.h;
      const p = document.createElement("p");
      p.textContent = item.p;
      li.append(n, h, p);
      cardsEl.appendChild(li);
    }

    out.hidden = false;
    out.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  const run = async (url, name) => {
    note.textContent = "Смотрю открытый контур…";
    let rows = [];
    let scanned = false;
    try {
      const res = await fetch("https://isitagentready.com/api/scan", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url }),
      });
      const data = await res.json();
      if (res.ok && !data.error) {
        rows = flatten(data);
        scanned = rows.length > 0;
      }
    } catch {
      scanned = false;
    }
    render({ url, name, rows, scanned });
    note.textContent = scanned
      ? "Готово. Это разбор фасада, не смета."
      : "Фасад прочитать не удалось — оставил только метод, без выдумок.";
  };

  form.addEventListener("submit", (e) => {
    e.preventDefault();
    const url = normalize(urlInput.value);
    if (!url) {
      note.textContent = "Нужен адрес сайта, с протоколом или без.";
      return;
    }
    urlInput.value = url;
    run(url, nameInput.value);
  });

  demo.addEventListener("click", () => {
    urlInput.value = "https://pepperoni.tatar/";
    nameInput.value = "Казанские Деликатесы";
    form.requestSubmit();
  });
})();
