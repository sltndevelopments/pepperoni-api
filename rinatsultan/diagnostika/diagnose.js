/* Owner-language diagnosis. Factory copy only when the facade looks like a plant. */

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
  const caveat = document.getElementById("dxCaveat");
  const method = document.getElementById("dxMethod");
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

  const translateFail = (text) => {
    const rules = [
      [/robots\.txt not found|robots\.txt.*404/i, "Нет файла robots.txt — нет явной инструкции, как роботам читать сайт."],
      [/disallow|blocked|robots\.txt/i, "В robots.txt вход роботам закрыт или запутан."],
      [/sitemap.*not found|sitemap\.xml not found/i, "Нет карты сайта. Поиск и агенты хуже находят страницы."],
      [/dnssec|authenticated data|ad=false/i, "DNS не подписан. Машина не может подтвердить, что записи о домене настоящие."],
      [/llms\.txt/i, "Нет llms.txt — нейросети не получают короткий однозначный текст."],
      [/markdown/i, "Нет текстовой версии страниц. Агент читает вёрстку, а не факты."],
      [/mcp/i, "Нет программного входа для агентов."],
      [/oauth|well-known/i, "Нет стандартных адресов, по которым агент понимает, как подключиться."],
      [/content-signal|ai-train/i, "Нет явного сигнала, что на этот текст можно опираться."],
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
      return ["Публичный контур прочитать не удалось — без претензии, что я видел страницы сайта."];
    }
    return lines.slice(0, 5);
  };

  const stripHtml = (html) =>
    String(html)
      .replace(/<script[\s\S]*?<\/script>/gi, " ")
      .replace(/<style[\s\S]*?<\/style>/gi, " ")
      .replace(/<[^>]+>/g, " ")
      .replace(/\s+/g, " ")
      .trim()
      .slice(0, 6000);

  const readFacade = async (url) => {
    const ctrl = new AbortController();
    const t = setTimeout(() => ctrl.abort(), 5000);
    try {
      const res = await fetch(url, { signal: ctrl.signal, mode: "cors", redirect: "follow" });
      if (!res.ok) return "";
      const ctype = res.headers.get("content-type") || "";
      if (!/html|xml|text/i.test(ctype)) return "";
      return stripHtml(await res.text());
    } catch {
      return "";
    } finally {
      clearTimeout(t);
    }
  };

  const classify = (host, name, pageText) => {
    const t = `${pageText} ${name} ${host}`.toLowerCase();
    if (/pepperoni\.tatar|казанск|деликатес|производств|комбинат|завод|халял|fmcg|мясоперераб|оптовая|дистрибуц/.test(t)) {
      return "plant";
    }
    if (
      /personal page|i am a |portfolio|резюме|о себе|backend|systems engineer|freelance|based in|личный сайт|обо мне/.test(t)
    ) {
      return "person";
    }
    return "unknown";
  };

  const copy = {
    plant: {
      first:
        "С улицы это витрина производственной компании. Поиск клиента, квалификация и первое письмо, скорее всего, до сих пор на людях — по часам, не по контуру.",
      give: "Отдать можно только обратимое: найти компанию, собрать досье, написать черновик первого письма. Это можно остановить. Человеку остаются переговоры и цена. Цех и отгрузка — нет.",
      bound:
        "Нельзя отдавать отгрузку, сертификат, рецептуру и требования сети. В пищевом и заводском контуре ошибка стоит партии, а не письма.",
      pilot:
        "Один пилот на 90 дней: первичная работа отдела продаж. До старта фиксируем «как есть». Через 90 дней — часы и ответы, не слайды. У нас контур написал 655 первых писем и вернул около 200 часов.",
      caveat:
        "Это разбор фасада, не цеха. Если узнаёте свою компанию — напишите. Беру не больше двух–трёх производств одновременно.",
    },
    person: {
      first:
        "С улицы это личная страница человека, не контур предприятия. Первичка здесь — «напишите задачу», а не отдел продаж с досье и холодными письмами.",
      give: "Коммерческую первичку завода здесь забирать не из чего. Имеет смысл только ясный текст о человеке, который машины читают без вранья. Это не мой рабочий контур.",
      bound:
        "Не фура и не сертификат. Граница для такой страницы — не выдумывать клиентов, стек и заслуги. Заводской шаблон сюда нельзя натягивать.",
      pilot:
        "Пилот «655 писем с комбината» сюда не клеится. Я работаю со средними и крупными производствами. Если вы руководитель завода — вставьте сайт предприятия, не личную страницу.",
      caveat: "Честный вывод: по этому адресу мы, скорее всего, не пара. Нужен сайт компании, которой вы управляете.",
    },
    unknown: {
      first:
        "По открытому сайту не видно ни отдела продаж, ни производства. Не буду назначать вам менеджеров и «первичку» — этого с улицы не доказано.",
      give: "В принципе агенту отдают только обратимое: поиск, досье, черновик письма. Без понятного процесса компании это совет в пустоту, а не план работ.",
      bound:
        "Нельзя автоматизировать то, чего не описали, и нельзя применять заводской пилот к сайту, который не выглядит как комбинат. Сначала понять, что это за организация.",
      pilot:
        "Мой формат — производственные компании и FMCG. Если это вы — пилот на 90 дней про первичку продаж, с цифрами как в кейсе 655 писем. Если это студия, личный сайт или витрина услуг — скорее всего, нам не стоит начинать.",
      caveat:
        "С улицы я не дорисовываю ваш цех. Пришлите сайт предприятия — или напишите, если это производство и фасад просто молчит.",
    },
  };

  const addCard = (n, title, body, lines) => {
    const li = document.createElement("li");
    li.className = "dx-card";
    const num = document.createElement("span");
    num.className = "dx-n mono";
    num.textContent = n;
    const h = document.createElement("h3");
    h.textContent = title;
    li.append(num, h);
    if (lines && lines.length) {
      const ul = document.createElement("ul");
      ul.className = "dx-bullets";
      for (const line of lines) {
        const item = document.createElement("li");
        item.textContent = line;
        ul.appendChild(item);
      }
      li.appendChild(ul);
    } else {
      const p = document.createElement("p");
      p.textContent = body;
      li.appendChild(p);
    }
    cardsEl.appendChild(li);
  };

  const render = ({ url, name, rows, scanned, pageText }) => {
    const host = hostOf(url);
    const kind = classify(host, name, pageText);
    const pack = copy[kind];
    const who = (name || "").trim() || host;

    hostEl.textContent = scanned
      ? host + " · " + (kind === "plant" ? "похоже на производство" : kind === "person" ? "личная страница" : "тип с улицы неясен")
      : host + " · контур не прочитан";
    titleEl.textContent = "Как это выглядит для «" + who + "»";
    subEl.textContent =
      kind === "plant"
        ? "Пять строк по фасаду и тот порядок, который я держу на заводе. Это не диагноз цеха."
        : kind === "person"
          ? "Фасад не производственный. Ниже — почему заводской разбор сюда не подходит."
          : "Фасад не дал права говорить о вашем отделе продаж. Ниже только то, что можно сказать честно.";
    caveat.textContent = pack.caveat;
    if (method) method.hidden = true;

    cardsEl.replaceChildren();
    addCard("01", "Что это с улицы", pack.first);
    addCard("02", "Что можно отдать", pack.give);
    addCard("03", "Чего нельзя натягивать", pack.bound);
    addCard("04", "Какой следующий шаг честен", pack.pilot);
    addCard("05", "Что машины уже видят криво", "", machineLines(rows));

    out.hidden = false;
    out.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  const run = async (url, name) => {
    note.textContent = "Смотрю открытый контур…";
    let rows = [];
    let scanned = false;
    const pageText = await readFacade(url);
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
    render({ url, name, rows, scanned, pageText });
    note.textContent = scanned ? "Готово. Без домыслов про цех." : "Фасад прочитать не удалось — без выдумок.";
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
