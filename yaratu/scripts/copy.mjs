export const LOCALES = ["ru", "en", "tt"];

export const LANG_NAME = {
  ru: "Русский",
  en: "English",
  tt: "Татарча"
};

export const ui = {
  ru: {
    home: "Главная", products: "Продукты", retail: "Для закупщиков", ingredients: "Раскрытый состав",
    nitrite: "Без нитрита", hero: "Любовь начинается со вкуса",
    lead: "Пять мясных продуктов из Казани с раскрытым составом, без нитрита натрия и с пищевой ценностью, которую можно прочитать до покупки.",
    range: "Пять продуктов. Состав без сокращений.", see: "Смотреть продукт", calculated: "Расчётные КБЖУ",
    halal: "Халяль подтверждён", noHalal: "Халяль не заявлен", weight: "Масса нетто",
    composition: "Состав", allergens: "Аллергены", nutrition: "КБЖУ на 100 г",
    nutritionNote: "Расчётный ориентир на 100 г сырьевой массы; не лабораторное значение.",
    kcal: "ккал", protein: "белки", fat: "жиры", carbs: "углеводы",
    contact: "Запросить спецификации", footer: "бренд ООО «Казанские Деликатесы»",
    status: "Статус данных", evidence: "Рецептура и состав проверены по внутренним документам.",
    advantages: "Преимущества", quality: "Контроль качества",
    contacts: "Контакты", connect: "Связаться", seeNutrition: "Посмотреть пищевую ценность",
    menu: "Меню", mobileMenu: "Мобильное меню", skip: "К содержанию", privacy: "Политика ПДн",
    languages: "Язык", qrCaption: "Этикетка на других языках",
    qrLead: "QR на упаковке откроет эту страницу — пищевую ценность можно прочитать по-русски, по-английски и по-татарски."
  },
  en: {
    home: "Home", products: "Products", retail: "For retailers", ingredients: "Disclosed ingredients",
    nitrite: "Without nitrite", hero: "Love begins with taste",
    lead: "Five meat products from Kazan with disclosed ingredients, no sodium nitrite and nutrition you can read before you buy.",
    range: "Five products. No ingredient-list shortcuts.", see: "View product", calculated: "Calculated nutrition",
    halal: "Halal verified", noHalal: "No halal claim", weight: "Net weight",
    composition: "Ingredients", allergens: "Allergens", nutrition: "Nutrition per 100 g",
    nutritionNote: "Calculated estimate per 100 g of raw recipe; not a laboratory value.",
    kcal: "kcal", protein: "protein", fat: "fat", carbs: "carbohydrate",
    contact: "Request specifications", footer: "a brand of Kazan Delicacies LLC",
    status: "Data status", evidence: "Recipe and composition reviewed against internal documents.",
    advantages: "Why Yaratu", quality: "Quality control",
    contacts: "Contact", connect: "Get in touch", seeNutrition: "View nutrition facts",
    menu: "Menu", mobileMenu: "Mobile menu", skip: "Skip to content", privacy: "Privacy",
    languages: "Language", qrCaption: "Label in other languages",
    qrLead: "The pack QR opens this page so the nutrition label can be read in Russian, English and Tatar."
  },
  tt: {
    home: "Баш бит", products: "Продуктлар", retail: "Сатып алучылар өчен", ingredients: "Ачык состав",
    nitrite: "Натрий нитритысыз", hero: "Мәхәббәт тәмдән башлана",
    lead: "Казанда җитештерелгән биш төр ит продукты: составы тулысынча күрсәтелгән, рецептураларында натрий нитриты кулланылмый, туклану кыйммәте турындагы мәгълүматны сатып алганчы ук укып була.",
    range: "Биш продукт. Составы тулысынча күрсәтелгән.", see: "Продуктны карарга", calculated: "Исәпләп чыгарылган туклану кыйммәте",
    halal: "Хәләллеге расланган", noHalal: "Хәләллеге күрсәтелмәгән", weight: "Нетто массасы",
    composition: "Состав", allergens: "Аллергеннар", nutrition: "100 граммга туклану кыйммәте",
    nutritionNote: "100 г чимал массасына исәпләп чыгарылган якынча күрсәткеч; лабораториядә билгеләнгән күрсәткеч түгел.",
    kcal: "ккал", protein: "аксым", fat: "май", carbs: "углевод",
    contact: "Спецификацияләрне сорарга", footer: "«Казанские Деликатесы» ҖЧҖнең бренды",
    status: "Мәгълүматның статусы", evidence: "Рецептура һәм состав эчке документлар буенча тикшерелгән.",
    advantages: "Нигә Ярату", quality: "Сыйфат контроле",
    contacts: "Элемтә", connect: "Элемтәгә чыгу", seeNutrition: "Туклану кыйммәтен карарга",
    menu: "Меню", mobileMenu: "Мобиль меню", skip: "Эчтәлеккә күчү", privacy: "Шәхси мәгълүматларны эшкәртү сәясәте",
    languages: "Тел", qrCaption: "Башка телләрдәге этикетка",
    qrLead: "Төргәктәге QR-код шушы битне ача: туклану кыйммәте турындагы мәгълүматны рус, инглиз һәм татар телләрендә укып була."
  }
};

export const nf = {
  ru: {
    label: "Пищевая ценность",
    per: "на 100 г",
    net: "Масса нетто",
    energy: "Калорийность / Энергетическая ценность",
    kcal: "ккал",
    kj: "кДж",
    calories: "Калории",
    dv: "% от суточной нормы*",
    protein: (p, g) => `Белки ≥ ${p} ${g}`,
    fat: (p, g) => `Всего жиров ≤ ${p} ${g}`,
    sat: (p, g) => `Насыщенные жиры ${p} ${g}`,
    carbs: (p, g) => `Углеводы ≤ ${p} ${g}`,
    foot: "* % от рекомендуемого уровня суточного потребления по ТР ТС 022/2011. 2500 ккал для общих рекомендаций. Расчёт по текущей рецептуре, не лабораторный протокол.",
    ingredients: "Состав",
    ingredientsPref: "Состав:",
    contains: "Содержит:"
  },
  en: {
    label: "Nutrition Facts",
    per: "Per 100 g",
    net: "Net Wt.",
    energy: "Calories / Energy",
    kcal: "kcal",
    kj: "kJ",
    calories: "Calories",
    dv: "% Daily Value*",
    protein: (p, g) => `Protein ${p} ${g}`,
    fat: (p, g) => `Total Fat ${p} ${g}`,
    sat: (p, g) => `Saturated Fat ${p} ${g}`,
    carbs: (p, g) => `Total Carbohydrate ${p} ${g}`,
    foot: "* Percent of the recommended daily intake under TR CU 022/2011. 2500 kcal general reference. Calculated from the current recipe, not laboratory-tested.",
    ingredients: "Ingredients",
    ingredientsPref: "Ingredients:",
    contains: "Contains:"
  },
  tt: {
    label: "Туклану кыйммәте",
    per: "100 граммга",
    net: "Нетто массасы",
    energy: "Калориялелек / Энергетик кыйммәт",
    kcal: "ккал",
    kj: "кДж",
    calories: "Калорияләр",
    dv: "Тәүлеклек нормадан өлеш, %*",
    protein: (p, g) => `Аксым ≥ ${p} ${g}`,
    fat: (p, g) => `Майның гомуми күләме ≤ ${p} ${g}`,
    sat: (p, g) => `Туенган майлар ${p} ${g}`,
    carbs: (p, g) => `Углевод ≤ ${p} ${g}`,
    foot: "* ТР ТС 022/2011 нигезендә тәкъдим ителгән тәүлеклек куллану нормасыннан өлеш. Гомуми исәп өчен нигез — 2500 ккал. Күрсәткечләр гамәлдәге рецептура буенча исәпләп чыгарылган; бу лаборатория сынаулары беркетмәсе түгел.",
    ingredients: "Ингредиентлар",
    ingredientsPref: "Ингредиентлар:",
    contains: "Аллергеннар:"
  }
};

export const positioning = {
  vetchina: {
    ru: ["Самая лёгкая в линейке", "125 ккал и 16,7 г белка на 100 г — минимальная калорийность и максимальное содержание белка среди пяти текущих продуктов."],
    en: ["The lightest in the range", "At 125 kcal and 16.7 g protein per 100 g, it has the lowest calories and highest protein among the five current products."],
    tt: ["Ассортиментта иң җиңеле", "100 граммга 125 ккал һәм 16,7 г аксым: биш продукт арасында калориялелеге иң түбән, аксым күләме иң югары."]
  },
  mramornaya: {
    ru: ["Выразительный мясной профиль", "Курица и говядина, варёно-копчёный формат и 0,5 г углеводов на 100 г."],
    en: ["A bold meat profile", "Chicken and beef in a cooked-smoked format, with 0.5 g carbohydrate per 100 g."],
    tt: ["Ачык сизелә торган ит тәме", "Тавык һәм сыер итеннән пешереп ысланган колбаса; 100 граммга 0,5 г углевод."]
  },
  brokkoli: {
    ru: ["Брокколи в раскрытом составе", "Курица и говядина с брокколи; 13 г белка и 1,5 г углеводов на 100 г."],
    en: ["Broccoli in the disclosed recipe", "Chicken and beef with broccoli; 13 g protein and 1.5 g carbohydrate per 100 g."],
    tt: ["Ачык составта брокколи", "Тавык һәм сыер итеннән, брокколи кушып ясалган сосискалар; 100 граммга 13 г аксым һәм 1,5 г углевод."]
  },
  molochnye: {
    ru: ["Мягкий классический вкус", "Молочный белок, сухое молоко и пряности раскрыты в составе; 13,5 г белка на 100 г."],
    en: ["A mild classic taste", "Milk protein, milk powder and spices are disclosed in full; 13.5 g protein per 100 g."],
    tt: ["Йомшак классик тәм", "Сөт аксымы, коры сөт һәм тәмләткечләр составта тулысынча күрсәтелгән; 100 граммга 13,5 г аксым."]
  },
  slivochnaya: {
    ru: ["Нежный сливочный профиль", "14,4 г белка и 0,7 г углеводов на 100 г — с полностью раскрытым составом."],
    en: ["A gentle creamy profile", "14.4 g protein and 0.7 g carbohydrate per 100 g, with the full ingredient list disclosed."],
    tt: ["Нәфис каймаклы тәм", "100 граммга 14,4 г аксым һәм 0,7 г углевод; составы тулысынча күрсәтелгән."]
  }
};

export const homeCopy = {
  ru: {
    title: "Ярату — раскрытый состав, без нитрита натрия",
    overline: "Мясные продукты · Казань",
    explore: "Смотреть ассортимент",
    badges: "5 продуктов",
    usp: "Особенность",
    faqTitle: "Короткие ответы",
    faqLead: "Цены и оферта на сайте не публикуются.",
    contactTitle: "Поговорим о поставке?",
    contactLead: "Запросите актуальные спецификации, фасовки, документы и условия напрямую у производителя.",
    address: "Казань, ул. Аграрная, 2, оф. 7",
    productLabel: "Всё важное — на одной этикетке.",
    productStatus: "Состав: recipe-sourced · Халяль: сертификат ДУМ РТ №614А/2024",
    specTitle: "Нужны спецификации?",
    specLead: "Запросите документы, фасовки и условия поставки напрямую у производителя.",
    facts: [
      ["01", "Без нитрита натрия", "Статус относится к пяти проверенным текущим рецептурам."],
      ["02", "Состав без сокращений", "Комплексные смеси раскрыты до входящих ингредиентов."],
      ["03", "Пищевая ценность открыта", "КБЖУ и проценты суточной нормы видны до покупки."]
    ],
    story: {
      eyebrow: "Почему Ярату",
      title: "Вкус начинается с честного выбора.",
      lead: "Мы создали Ярату, чтобы мясной продукт не приходилось выбирать вслепую. На сайте можно увидеть текущий состав, аллергены и расчётную пищевую ценность каждого продукта.",
      quote: "Не обещания на лицевой стороне, а состав и цифры, которые можно проверить."
    },
    production: {
      eyebrow: "Производство",
      title: "Сделано в Казани. Контроль — на каждом уровне.",
      lead: "Ярату — бренд ООО «Казанские Деликатесы», производителя халяльных мясных продуктов в Казани. Производство работает по системе HACCP, стандарту ISO 22000:2018 и требованиям ТР ТС 021/2011.",
      standards: [["HACCP", "Безопасность процессов"], ["ISO 22000:2018", "Система пищевой безопасности"], ["ТР ТС 021/2011", "Требования к пищевой продукции"]]
    },
    quality: {
      eyebrow: "Контроль качества",
      title: "Доверие строится на фактах.",
      lead: "Мы разделяем подтверждённые продуктовые факты и расчётные данные — и прямо показываем статус каждого источника.",
      items: [
        ["01", "HACCP и ISO 22000", "Системы управления безопасностью применяются на производстве ООО «Казанские Деликатесы»."],
        ["02", "Сертификат Халяль", "Все пять текущих продуктов входят в область действия сертификата ДУМ РТ №614А/2024."],
        ["03", "Полное раскрытие", "Комплексные смеси перечислены до отдельных ингредиентов, аллергены вынесены отдельно."],
        ["04", "Честный статус КБЖУ", "Пищевая ценность рассчитана по текущей рецептуре и не выдается за лабораторный протокол."]
      ]
    },
    faqs: [
      ["Что такое Ярату?", "Ярату — мясной бренд ООО «Казанские Деликатесы»: пять варёных продуктов из Казани без нитрита натрия и с составом, раскрытым до ингредиентов."],
      ["Для кого эта линейка?", "Для магазинов, дистрибьюторов и покупателей, которым нужен проверяемый состав, а не лозунг «чистый продукт»."],
      ["Где цены?", "Публичного потребительского прайса нет. Актуальные спецификации, фасовки и условия поставки запрашивают у производителя."],
      ["Вся линейка халяль?", "Да. Все пять текущих продуктов входят в область действия сертификата Халяль ДУМ РТ №614А/2024."],
      ["КБЖУ лабораторные?", "Нет. Это расчёт по текущей рецептуре на 100 г сырьевой массы, не протокол испытаний."],
      ["Как запросить поставку?", "Напишите на info@kazandelikates.tatar или позвоните +7 987 217-02-02. Производитель в Казани, ул. Аграрная, 2, оф. 7."]
    ],
    halalLine: "Все пять продуктов входят в область действия сертификата Халяль ДУМ РТ №614А/2024.",
    retailTitle: "Yaratu для магазинов и дистрибьюторов",
    retailAnswer: "Запросите актуальные спецификации, фасовки, документы и условия поставки напрямую у производителя.",
    retailAddress: "г. Казань, ул. Аграрная, д. 2, оф. 7",
    company: "ООО «Казанские Деликатесы»"
  },
  en: {
    title: "Yaratu — disclosed ingredients, no sodium nitrite",
    overline: "Meat products · Kazan",
    explore: "Explore the range",
    badges: "5 products",
    usp: "What sets it apart",
    faqTitle: "Short answers",
    faqLead: "No prices or offers are published on this site.",
    contactTitle: "Let’s talk supply.",
    contactLead: "Request current specifications, pack formats, documents and supply terms directly from the manufacturer.",
    address: "2 Agrarnaya Street, office 7, Kazan",
    productLabel: "Everything important, on one label.",
    productStatus: "Ingredients: recipe-sourced · Halal: certificate No. 614A/2024",
    specTitle: "Need specifications?",
    specLead: "Request documents, pack formats and supply terms directly from the manufacturer.",
    facts: [
      ["01", "No sodium nitrite", "The status applies to the five reviewed current recipes."],
      ["02", "No ingredient shortcuts", "Compound mixes are disclosed ingredient by ingredient."],
      ["03", "Nutrition in full view", "Macros and daily-value percentages are visible before purchase."]
    ],
    story: {
      eyebrow: "Why Yaratu",
      title: "Taste begins with an informed choice.",
      lead: "We created Yaratu so a meat product would not have to be chosen blindly. The current ingredients, allergens and calculated nutrition for every product are visible here.",
      quote: "Not front-of-pack promises, but ingredients and figures you can check."
    },
    production: {
      eyebrow: "Production",
      title: "Made in Kazan. Controlled at every level.",
      lead: "Yaratu is a brand of Kazan Delicacies, a halal meat-products manufacturer in Kazan. Production operates under HACCP, ISO 22000:2018 and TR CU 021/2011 requirements.",
      standards: [["HACCP", "Process safety"], ["ISO 22000:2018", "Food-safety management"], ["TR CU 021/2011", "Food-product requirements"]]
    },
    quality: {
      eyebrow: "Quality control",
      title: "Trust is built on facts.",
      lead: "We separate verified product facts from calculated data and make the status of each source explicit.",
      items: [
        ["01", "HACCP and ISO 22000", "Food-safety management systems are applied at Kazan Delicacies production."],
        ["02", "Halal certificate", "All five current products are covered by certificate No. 614A/2024 issued by the Spiritual Administration of Muslims of Tatarstan."],
        ["03", "Full disclosure", "Compound mixes are listed ingredient by ingredient, with allergens called out separately."],
        ["04", "Honest nutrition status", "Nutrition is calculated from the current recipe and is not presented as a laboratory report."]
      ]
    },
    faqs: [
      ["What is Yaratu?", "Yaratu is the meat brand of Kazan Delicacies: five cooked products from Kazan without sodium nitrite and with compound mixes listed ingredient by ingredient."],
      ["Who is it for?", "Retailers, distributors and shoppers who need a checkable recipe rather than a clean-label slogan."],
      ["Where is the pricing?", "There is no public consumer price list. Specifications, pack formats and supply terms are provided by the manufacturer on request."],
      ["Is the whole range halal?", "Yes. All five current products are covered by Halal certificate No. 614A/2024 issued by the Spiritual Administration of Muslims of the Republic of Tatarstan."],
      ["Is nutrition laboratory-tested?", "No. Figures are calculated from the current recipe per 100 g of raw mass, not a lab protocol."],
      ["How do I request supply?", "Email info@kazandelikates.tatar or call +7 987 217-02-02. The manufacturer is in Kazan, 2 Agrarnaya Street, office 7."]
    ],
    halalLine: "All five products are covered by Halal certificate No. 614A/2024 issued by the Spiritual Administration of Muslims of the Republic of Tatarstan.",
    retailTitle: "Yaratu for retailers and distributors",
    retailAnswer: "Request current specifications, pack formats, documents and supply terms directly from the manufacturer.",
    retailAddress: "2 Agrarnaya Street, office 7, Kazan, Russia",
    company: "Kazan Delicacies LLC"
  },
  tt: {
    title: "Ярату — ачык состав, натрий нитритысыз",
    overline: "Ит продуктлары · Казан",
    explore: "Ассортиментны карау",
    badges: "5 продукт",
    usp: "Үзенчәлек",
    faqTitle: "Кыска җаваплар",
    faqLead: "Сайтта бәяләр һәм ачык оферта урнаштырылмый.",
    contactTitle: "Тәэминат турында сөйләшәбезме?",
    contactLead: "Гамәлдәге спецификацияләрне, төргәк вариантларын, документларны һәм тәэмин итү шартларын турыдан-туры җитештерүчедән сорагыз.",
    address: "Казан, Аграрная урамы, 2 нче йорт, 7 нче офис",
    productLabel: "Барлык мөһим мәгълүмат — бер этикеткада.",
    productStatus: "Состав чыганагы: гамәлдәге рецептура · Хәләл: ДУМ РТ биргән №614А/2024 сертификат",
    specTitle: "Спецификацияләр кирәкме?",
    specLead: "Документларны, фасовкаларны һәм тәэминат шартларын турыдан-туры җитештерүчедән сорагыз.",
    facts: [
      ["01", "Натрий нитриты юк", "Бу мәгълүмат тикшерелгән гамәлдәге биш рецептурага кагыла."],
      ["02", "Состав тулысынча күрсәтелгән", "Комплекслы кушылмалар һәр ингредиентына кадәр күрсәтелгән."],
      ["03", "Туклану кыйммәте ачык", "Калория, аксым, май һәм углеводлар, шулай ук тәүлеклек норманың процентлары сатып алуга кадәр күрсәтелә."]
    ],
    story: {
      eyebrow: "Нигә Ярату",
      title: "Тәм аңлы сайлаудан башлана.",
      lead: "«Ярату»ны ит продуктын мәгълүматсыз сайларга туры килмәсен өчен булдырдык. Сайтта һәр продуктның гамәлдәге составы, аллергеннары һәм исәпләп чыгарылган туклану кыйммәте бар.",
      quote: "Төргәкнең алгы ягындагы вәгъдәләр түгел, ә тикшереп була торган состав һәм саннар."
    },
    production: {
      eyebrow: "Җитештерү",
      title: "Казанда җитештерелгән. Контроль — һәр дәрәҗәдә.",
      lead: "Ярату — Казанда хәләл ит продуктлары җитештерүче «Казанские Деликатесы» ҖЧҖнең бренды. Җитештерү HACCP системасы, ISO 22000:2018 стандарты һәм ТР ТС 021/2011 таләпләре буенча эшли.",
      standards: [["HACCP", "Процессларның куркынычсызлыгы"], ["ISO 22000:2018", "Азык-төлек иминлеге белән идарә итү системасы"], ["ТР ТС 021/2011", "Азык-төлек продукциясенә таләпләр"]]
    },
    quality: {
      eyebrow: "Сыйфат контроле",
      title: "Ышаныч фактларга корыла.",
      lead: "Расланган продукт фактларын исәпләнгән мәгълүматтан аерабыз һәм һәр чыганакның статусын ачык күрсәтәбез.",
      items: [
        ["01", "HACCP һәм ISO 22000", "Азык-төлек куркынычсызлыгы белән идарә итү системалары «Казанские Деликатесы» ҖЧҖ җитештерүендә кулланыла."],
        ["02", "Хәләл сертификаты", "Гамәлдәге биш продукт та ДУМ РТ №614А/2024 сертификатының гамәл өлкәсенә керә."],
        ["03", "Тулы ачыклык", "Комплекслы кушылмалар аерым ингредиентларга кадәр санап чыгарылган, аллергеннар аерым күрсәтелгән."],
        ["04", "Туклану кыйммәтенең статусы ачык күрсәтелгән", "Туклану кыйммәте гамәлдәге рецептура буенча исәпләп чыгарылган һәм лаборатория сынавы беркетмәсе дип күрсәтелми."]
      ]
    },
    faqs: [
      ["Ярату нәрсә ул?", "Ярату — «Казанские Деликатесы» ҖЧҖнең ит бренды: Казанда җитештерелгән биш продуктта натрий нитриты кулланылмый, ә составы һәр ингредиентына кадәр ачык күрсәтелгән."],
      ["Бу продуктлар кем өчен?", "Кибетләр, дистрибьюторлар һәм «чиста продукт» дигән шигарьгә түгел, тикшереп була торган составка өстенлек бирүче сатып алучылар өчен."],
      ["Бәяләр кайда?", "Кулланучылар өчен ачык бәяләр исемлеге юк. Гамәлдәге спецификацияләрне, төргәк вариантларын һәм тәэмин итү шартларын җитештерүчедән соратып алырга мөмкин."],
      ["Барлык продуктлар да хәләлме?", "Әйе. ДУМ РТ биргән №614А/2024 «Хәләл» сертификаты гамәлдәге биш продуктның барысына да кагыла."],
      ["Туклану кыйммәте лабораториядә тикшерелгәнме?", "Юк. Бу — гамәлдәге рецептура буенча 100 г чимал массасына исәпләп чыгарылган күрсәткеч; сынау беркетмәсе түгел."],
      ["Тәэмин итү турында ничек белешергә?", "info@kazandelikates.tatar адресына языгыз яки +7 987 217-02-02 номерына шалтыратыгыз. Җитештерүче Казанда, Аграрная урамы, 2 нче йорт, 7 нче офис."]
    ],
    halalLine: "Биш продукт та ДУМ РТ №614А/2024 «Хәләл» сертификатының гамәл өлкәсенә керә.",
    retailTitle: "Ярату кибетләр һәм дистрибьюторлар өчен",
    retailAnswer: "Гамәлдәге спецификацияләрне, төргәк вариантларын, документларны һәм тәэмин итү шартларын турыдан-туры җитештерүчедән сорагыз.",
    retailAddress: "Казан шәһәре, Аграрная урамы, 2 нче йорт, 7 нче офис",
    company: "«Казанские Деликатесы» ҖЧҖ"
  }
};

export const answers = {
  ingredients: {
    ru: {
      title: "Что значит раскрытый состав?",
      answer: "Раскрытый состав перечисляет не только название комплексной смеси, но и входящие в неё ингредиенты.",
      detail: "На страницах пяти продуктов приведён текущий состав из рецептуры и спецификаций. Статус состава — recipe-sourced; маркировка партии остаётся приоритетным источником для покупателя.",
      q: "Где проверить состав конкретного продукта?",
      a: "На отдельной странице продукта и на его фактической упаковке."
    },
    en: {
      title: "What does a disclosed ingredient list mean?",
      answer: "A disclosed list names the ingredients inside compound mixes instead of showing only a trade name.",
      detail: "Each of the five product pages shows the current recipe-based ingredient list. It is marked as recipe-derived; the label on the actual pack remains the primary source for a purchased batch.",
      q: "Where can I check a specific product?",
      a: "Use its dedicated product page and check the physical pack."
    },
    tt: {
      title: "«Ачык состав» нәрсәне аңлата?",
      answer: "Ачык состав комплекслы кушылманың исемен генә түгел, аңа кергән ингредиентларны да санап чыгара.",
      detail: "Биш продуктның һәркайсының битендә гамәлдәге рецептура һәм спецификацияләр нигезендәге состав китерелгән. Состав гамәлдәге рецептура нигезендә бирелгән; сатып алучы өчен партия маркировкасы төп чыганак булып кала.",
      q: "Билгеле бер продукт составын кайда тикшерергә?",
      a: "Продуктның аерым битендә һәм сатып алынган продуктның кабында."
    }
  },
  nitrite: {
    ru: {
      title: "Что значит «без нитрита натрия»?",
      answer: "В текущих рецептурах пяти продуктов Yaratu нитрит натрия E250 не используется.",
      detail: "Утверждение относится к проверенным текущим рецептурам. Оно не означает отсутствие любых солей, специй или технологической обработки.",
      q: "Это лабораторное утверждение?",
      a: "Нет. Источник статуса — текущие рецептуры и спецификации; КБЖУ также остаются расчётными."
    },
    en: {
      title: "What does “without sodium nitrite” mean?",
      answer: "Sodium nitrite E250 is not used in the current recipes of the five Yaratu products.",
      detail: "The statement applies to the reviewed current recipes. It does not mean the products contain no salt, spices or processing.",
      q: "Is this a laboratory claim?",
      a: "No. The status comes from current recipes and specifications; nutrition figures are calculated too."
    },
    tt: {
      title: "«Натрий нитритысыз» нәрсәне аңлата?",
      answer: "Яратуның биш продуктының гамәлдәге рецептураларында натрий нитриты E250 кулланылмый.",
      detail: "Бу мәгълүмат тикшерелгән гамәлдәге рецептураларга кагыла. Бу тоз, тәмләткечләр яки технологик эшкәртү юк дигән сүз түгел.",
      q: "Бу лабораториядә расланганмы?",
      a: "Юк. Бу мәгълүмат гамәлдәге рецептуралардан һәм спецификацияләрдән алынган; туклану кыйммәте күрсәткечләре дә исәпләп чыгарылган."
    }
  }
};

export const markdownPages = {
  retail: {
    ru: `# Yaratu для магазинов и дистрибьюторов\n\nЗапросите актуальные спецификации, фасовки, документы и условия поставки напрямую у производителя.\n\n- ООО «Казанские Деликатесы»\n- г. Казань, ул. Аграрная, д. 2, оф. 7\n- +7 987 217-02-02\n- info@kazandelikates.tatar\n`,
    en: `# Yaratu for retailers and distributors\n\nRequest current specifications, pack formats, documents and supply terms directly from the manufacturer.\n\n- Kazan Delicacies LLC\n- 2 Agrarnaya Street, office 7, Kazan, Russia\n- +7 987 217-02-02\n- info@kazandelikates.tatar\n`,
    tt: `# Ярату кибетләр һәм дистрибьюторлар өчен\n\nГамәлдәге спецификацияләрне, төргәк вариантларын, документларны һәм тәэмин итү шартларын турыдан-туры җитештерүчедән сорагыз.\n\n- «Казанские Деликатесы» ҖЧҖ\n- Казан шәһәре, Аграрная урамы, 2 нче йорт, 7 нче офис\n- +7 987 217-02-02\n- info@kazandelikates.tatar\n`
  },
  ingredients: {
    ru: `# Что значит раскрытый состав?\n\nРаскрытый состав перечисляет не только название комплексной смеси, но и входящие в неё ингредиенты. Статус состава — recipe-sourced; маркировка партии остаётся приоритетным источником.\n`,
    en: `# What does a disclosed ingredient list mean?\n\nA disclosed list names the ingredients inside compound mixes instead of showing only a trade name. The pack label remains the primary source for a purchased batch.\n`,
    tt: `# «Ачык состав» нәрсәне аңлата?\n\nАчык состав комплекслы кушылманың исемен генә түгел, аңа кергән ингредиентларны да санап чыгара. Состав гамәлдәге рецептура нигезендә бирелгән; партия маркировкасы төп чыганак булып кала.\n`
  },
  nitrite: {
    ru: `# Что значит «без нитрита натрия»?\n\nВ текущих рецептурах пяти продуктов Yaratu нитрит натрия E250 не используется. Это статус рецептуры, не лабораторное утверждение.\n`,
    en: `# What does “without sodium nitrite” mean?\n\nSodium nitrite E250 is not used in the current recipes of the five Yaratu products. Nutrition figures are calculated, not laboratory-tested.\n`,
    tt: `# «Натрий нитритысыз» нәрсәне аңлата?\n\nЯратуның биш продуктының гамәлдәге рецептураларында натрий нитриты E250 кулланылмый. Бу мәгълүмат рецептурага нигезләнгән, лабораториядә расланмаган.\n`
  }
};

export const editorial = {
  en: {
    htmlLang: "en",
    title: "Yaratu — meat products with no secrets",
    description: "Five meat products from Kazan with disclosed ingredients, no sodium nitrite and nutrition you can read before you buy.",
    skip: "Skip to content",
    navAria: "Yaratu — home",
    nav: ["Facts", "Range", "Control", "Contacts"],
    menu: "Menu",
    mobileMenu: "Mobile menu",
    retail: "For buyers",
    langAria: "Language",
    heroMeta: ["Meat brand · Kazan", "Halal · SAM RT No. 614A/2024"],
    heroKicker: "meat products with no secrets",
    heroTitle: "Yaratu",
    heroLedeA: "Five chicken and beef products —",
    heroLedeEm: "ingredients disclosed",
    heroLedeB: "down to every single one.",
    heroSub: "No sodium nitrite. Nutrition is published before purchase and honestly marked as calculated. Production — Kazan Delicacies LLC, Kazan.",
    heroCtaRange: "View the range",
    heroCtaContact: "Get in touch",
    badgeText: "NO SODIUM NITRITE · HALAL SAM RT · INGREDIENTS DISCLOSED ·",
    ticker: ["No sodium nitrite", "Ingredients disclosed in full", "Halal · SAM RT No. 614A/2024", "HACCP · ISO 22000:2018", "TR CU 021/2011", "Batch traceability"],
    factsEyebrow: "No. 01 — What is verified",
    factsTitle: "Verified facts",
    facts: [
      ["01", "No sodium nitrite", "Sodium nitrite (E250) is not used in any of the five current recipes."],
      ["02", "Ingredients disclosed", "Compound additives are listed down to individual ingredients — no hidden trade names."],
      ["03", "Halal", "All five products are covered by Halal certificate SAM RT No. 614A/2024."]
    ],
    productsEyebrow: "No. 02 — Range",
    productsTitleA: "Five products.",
    productsTitleEm: "Zero secrets.",
    productsLead: "Every card has a “Show the label” button: full nutrition, honestly marked as calculated from the raw recipe, compound ingredients and allergens.",
    toc: ["Chicken fillet ham", "Mramornaya c/s sausage", "Sausages with broccoli", "Molochnye sausages", "Slivochnaya cooked sausage"],
    dealTeaser: "Nutrition · ingredients · allergens",
    dealShow: "Show the label",
    dealHide: "Hide the label",
    labelCaption: "Full-ingredient label · calculated from the recipe · QR for other languages",
    qrLink: "Русский · English · Татарча",
    qualityEyebrow: "No. 03 — Quality control",
    qualityTitleA: "Every batch —",
    qualityTitleEm: "with a number.",
    qualityLead: "Yaratu is a brand of Kazan Delicacies LLC. Production in Kazan operates under HACCP and ISO 22000:2018; products comply with TR CU 021/2011 and are covered by Halal certificate SAM RT No. 614A/2024.",
    qualityList: [
      ["Halal", "Certificate SAM RT No. 614A/2024 — all five products covered"],
      ["HACCP", "Food-safety management system in production"],
      ["ISO 22000:2018", "International food-safety management standard"],
      ["TR CU 021/2011", "Technical regulation “On food safety”"],
      ["Batch", "Batch number on the label — every pack is traceable"],
      ["Allergens", "Ingredient and allergen specifications on request"]
    ],
    faqEyebrow: "No. 04 — Short answers",
    faqTitleA: "No",
    faqTitleEm: "fine print.",
    faqLead: "Why Yaratu: ingredients and figures can be checked before purchase. No prices or offers are published on this site.",
    faqs: [
      ["What is Yaratu?", "Yaratu is the meat brand of Kazan Delicacies LLC: five cooked products from Kazan without sodium nitrite and with compound mixes listed ingredient by ingredient."],
      ["Who is it for?", "Retailers, distributors and shoppers who need a checkable recipe rather than a clean-label slogan."],
      ["Where is the pricing?", "There is no public consumer price list. Specifications, pack formats and supply terms are provided by the manufacturer on request."],
      ["Is the whole range halal?", "Yes. All five current products are covered by Halal certificate No. 614A/2024 issued by the Spiritual Administration of Muslims of the Republic of Tatarstan."],
      ["Is nutrition laboratory-tested?", "No. Figures are calculated from the current recipe per 100 g of raw mass, not a lab protocol."],
      ["How do I request supply?", "Email info@kazandelikates.tatar or call +7 987 217-02-02. The manufacturer is in Kazan, 2 Agrarnaya Street, office 7."]
    ],
    contactEyebrow: "No. 05 — Contacts",
    contactTitleA: "Let’s talk",
    contactTitleEm: "supply?",
    contactLead: "We will send current ingredients, pack formats, certificates and supply terms. There is no public consumer price list. Calculated nutrition is always marked separately from laboratory values.",
    contactCta: "Request specifications",
    mailSubject: "Yaratu / specification request",
    contactLabels: ["Manufacturer", "Address", "Contact", "Registration"],
    contactValues: ["Kazan Delicacies LLC", "2 Agrarnaya Street, office 7, Kazan 420061", "", "INN 1686021074 · KPP 168601001 · OGRN 1221600096893"],
    footerAria: "Documents",
    privacy: "Privacy policy",
    footerTag: "meat products with no secrets"
  },
  tt: {
    htmlLang: "tt",
    title: "Ярату — серсез ит продуктлары",
    description: "Казанда җитештерелгән биш төр ит продукты: составы тулысынча күрсәтелгән, рецептураларында натрий нитриты кулланылмый, туклану кыйммәте турындагы мәгълүматны сатып алганчы ук укып була.",
    skip: "Эчтәлеккә күчү",
    navAria: "Ярату — баш бит",
    nav: ["Фактлар", "Ассортимент", "Контроль", "Элемтә"],
    menu: "Меню",
    mobileMenu: "Мобиль меню",
    retail: "Сатып алучылар өчен",
    langAria: "Тел",
    heroMeta: ["Ит бренды · Казан", "Хәләл · ДУМ РТ №614А/2024"],
    heroKicker: "серсез ит продуктлары",
    heroTitle: "Ярату",
    heroLedeA: "Тавык һәм сыер итеннән ясалган биш продуктның",
    heroLedeEm: "составы",
    heroLedeB: "һәр ингредиентына кадәр ачык күрсәтелгән.",
    heroSub: "Натрий нитриты кулланылмый. Туклану кыйммәте сатып алуга кадәр күрсәтелә һәм аның исәпләп чыгарылуы ачык билгеләнә. Җитештерүче — «Казанские Деликатесы» ҖЧҖ, Казан.",
    heroCtaRange: "Ассортиментны карау",
    heroCtaContact: "Элемтәгә чыгу",
    badgeText: "НАТРИЙ НИТРИТЫСЫЗ · ХӘЛӘЛ ДУМ РТ · СОСТАВЫ АЧЫК ·",
    ticker: ["Натрий нитритысыз", "Составы һәр ингредиентына кадәр ачык", "Хәләл · ДУМ РТ №614А/2024", "HACCP · ISO 22000:2018", "ТР ТС 021/2011", "Партияне күзәтеп бару мөмкинлеге"],
    factsEyebrow: "№ 01 — Нәрсә расланган",
    factsTitle: "Расланган фактлар",
    facts: [
      ["01", "Натрий нитриты юк", "Натрий нитриты (E250) гамәлдәге биш рецептураның берсендә дә кулланылмый."],
      ["02", "Состав ачык", "Комплекслы кушылмалар аерым ингредиентларга кадәр санап чыгарылган — яшерен сәүдә исемнәре юк."],
      ["03", "Хәләл", "Биш продукт та ДУМ РТ №614А/2024 «Хәләл» сертификатының гамәл өлкәсенә керә."]
    ],
    productsEyebrow: "№ 02 — Ассортимент",
    productsTitleA: "Биш продукт.",
    productsTitleEm: "Бер сер дә юк.",
    productsLead: "Һәр карточкада «Этикетканы күрсәтү» төймәсе бар. Анда туклану кыйммәте тулысынча бирелгән һәм аның чимал рецептурасы буенча исәпләп чыгарылганы ачык күрсәтелгән; комплекслы катнашмаларның составы һәм аллергеннар да күрсәтелгән.",
    toc: ["Тавык филесыннан ветчина", "Пешереп ысланган «Мраморная» колбасасы", "Брокколи кушылган сосискалар", "«Молочные» сосискалары", "Пешкән «Сливочная» колбасасы"],
    dealTeaser: "Туклану кыйммәте · состав · аллергеннар",
    dealShow: "Этикетканы күрсәтү",
    dealHide: "Этикетканы яшерү",
    labelCaption: "Тулы ингредиентлар исемлеге · рецептура буенча исәпләнгән · башка телләр өчен QR-код",
    qrLink: "Русский · English · Татарча",
    qualityEyebrow: "№ 03 — Сыйфат контроле",
    qualityTitleA: "Һәр партиянең",
    qualityTitleEm: "үз номеры бар.",
    qualityLead: "Ярату — «Казанские Деликатесы» ҖЧҖнең бренды. Казандагы җитештерү HACCP системасы һәм ISO 22000:2018 стандарты буенча эшли; продукция ТР ТС 021/2011 таләпләренә туры килә һәм ДУМ РТ №614А/2024 «Хәләл» сертификатының гамәл өлкәсенә керә.",
    qualityList: [
      ["Хәләл", "ДУМ РТ №614А/2024 сертификатының гамәл өлкәсе биш продуктны да үз эченә ала"],
      ["HACCP", "Җитештерүдә азык-төлек куркынычсызлыгы белән идарә итү системасы"],
      ["ISO 22000:2018", "Азык-төлек куркынычсызлыгы белән идарә итүнең халыкара стандарты"],
      ["ТР ТС 021/2011", "«Азык-төлек продукциясенең куркынычсызлыгы турында» техник регламент"],
      ["Партия", "Этикеткада партия номеры бар — һәр төргәкнең юлын күзәтеп була"],
      ["Аллергеннар", "Ингредиентлар һәм аллергеннар буенча спецификацияләрне соратып алырга мөмкин"]
    ],
    faqEyebrow: "№ 04 — Кыска җаваплар",
    faqTitleA: "Вак",
    faqTitleEm: "хәрефсез.",
    faqLead: "Нигә Ярату: составны һәм саннарны сатып алганчы ук тикшереп була. Сайтта бәяләр һәм ачык оферта урнаштырылмый.",
    faqs: [
      ["Ярату нәрсә ул?", "Ярату — «Казанские Деликатесы» ҖЧҖнең ит бренды: Казанда җитештерелгән биш продуктта натрий нитриты кулланылмый, ә составы һәр ингредиентына кадәр ачык күрсәтелгән."],
      ["Бу продуктлар кем өчен?", "Кибетләр, дистрибьюторлар һәм «чиста продукт» дигән шигарьгә түгел, тикшереп була торган составка өстенлек бирүче сатып алучылар өчен."],
      ["Бәяләр кайда?", "Кулланучылар өчен ачык бәяләр исемлеге юк. Гамәлдәге спецификацияләрне, төргәк вариантларын һәм тәэмин итү шартларын җитештерүчедән соратып алырга мөмкин."],
      ["Барлык продуктлар да хәләлме?", "Әйе. ДУМ РТ биргән №614А/2024 «Хәләл» сертификаты гамәлдәге биш продуктның барысына да кагыла."],
      ["Туклану кыйммәте лабораториядә тикшерелгәнме?", "Юк. Бу — гамәлдәге рецептура буенча 100 г чимал массасына исәпләп чыгарылган күрсәткеч; сынау беркетмәсе түгел."],
      ["Тәэмин итү турында ничек белешергә?", "info@kazandelikates.tatar адресына языгыз яки +7 987 217-02-02 номерына шалтыратыгыз. Җитештерүче Казанда, Аграрная урамы, 2 нче йорт, 7 нче офис."]
    ],
    contactEyebrow: "№ 05 — Элемтә",
    contactTitleA: "Тәэминат турында",
    contactTitleEm: "сөйләшәбезме?",
    contactLead: "Гамәлдәге составларны, төргәк вариантларын, сертификатларны һәм тәэмин итү шартларын җибәрәбез. Кулланучылар өчен ачык бәяләр исемлеге юк. Исәпләп чыгарылган туклану кыйммәте һәрвакыт лаборатория нәтиҗәләреннән аерым билгеләнә.",
    contactCta: "Спецификацияләрне сорарга",
    mailSubject: "Ярату / спецификация сорауы",
    contactLabels: ["Җитештерүче", "Адрес", "Элемтә", "Реквизитлар"],
    contactValues: ["«Казанские Деликатесы» ҖЧҖ", "420061, Казан ш., Аграрная ур., 2, 7 нче офис", "", "ИНН 1686021074 · КПП 168601001 · ОГРН 1221600096893"],
    footerAria: "Документлар",
    privacy: "Шәхси мәгълүматларны эшкәртү сәясәте",
    footerTag: "серсез ит продуктлары"
  }
};

export const editorialProducts = {
  vetchina: {
    en: { name: "Chicken fillet ham", nameA: "Chicken fillet", nameEm: "ham", alt: "Yaratu chicken fillet ham — 150 g pack", qrAlt: "QR: ham label in Russian, English and Tatar" },
    tt: { name: "Тавык филесыннан ветчина", nameA: "Тавык филесыннан", nameEm: "ветчина", alt: "«Ярату»ның тавык филесыннан ветчинасы; нетто массасы 150 г", qrAlt: "Ветчина этикеткасының рус, инглиз һәм татар телләрендәге версияләренә QR-код" }
  },
  mramornaya: {
    en: { name: "Mramornaya cooked smoked sausage", nameA: "Cooked smoked sausage", nameEm: "“Mramornaya”", alt: "Yaratu Mramornaya cooked smoked sausage — 500 g pack", qrAlt: "QR: Mramornaya label in Russian, English and Tatar" },
    tt: { name: "Пешереп ысланган «Мраморная» колбасасы", nameA: "Пешереп ысланган", nameEm: "«Мраморная» колбасасы", alt: "«Ярату»ның пешереп ысланган «Мраморная» колбасасы; нетто массасы 500 г", qrAlt: "«Мраморная» колбасасы этикеткасының рус, инглиз һәм татар телләрендәге версияләренә QR-код" }
  },
  brokkoli: {
    en: { name: "Sausages with broccoli", nameA: "Sausages", nameEm: "with broccoli", alt: "Yaratu sausages with broccoli — 400 g pack", qrAlt: "QR: broccoli sausages label in Russian, English and Tatar" },
    tt: { name: "Брокколи кушылган сосискалар", nameA: "Брокколи кушылган", nameEm: "сосискалар", alt: "«Ярату»ның брокколи кушылган сосискалары; нетто массасы 400 г", qrAlt: "Брокколи кушылган сосискалар этикеткасының рус, инглиз һәм татар телләрендәге версияләренә QR-код" }
  },
  molochnye: {
    en: { name: "Molochnye milk sausages", nameA: "Sausages", nameEm: "“Molochnye”", alt: "Yaratu Molochnye milk sausages — 500 g pack", qrAlt: "QR: Molochnye label in Russian, English and Tatar" },
    tt: { name: "«Молочные» сосискалары", nameA: "«Молочные»", nameEm: "сосискалары", alt: "«Ярату»ның «Молочные» сосискалары; нетто массасы 500 г", qrAlt: "«Молочные» сосискалары этикеткасының рус, инглиз һәм татар телләрендәге версияләренә QR-код" }
  },
  slivochnaya: {
    en: { name: "Slivochnaya cooked sausage", nameA: "Cooked sausage", nameEm: "“Slivochnaya”", alt: "Yaratu Slivochnaya cooked sausage — 400 g pack", qrAlt: "QR: Slivochnaya label in Russian, English and Tatar" },
    tt: { name: "Пешкән «Сливочная» колбасасы", nameA: "Пешкән", nameEm: "«Сливочная» колбасасы", alt: "«Ярату»ның пешкән «Сливочная» колбасасы; нетто массасы 400 г", qrAlt: "«Сливочная» колбасасы этикеткасының рус, инглиз һәм татар телләрендәге версияләренә QR-код" }
  }
};

export const packshotDims = {
  vetchina: [1400, 2249],
  mramornaya: [1400, 845],
  brokkoli: [1400, 1337],
  molochnye: [1400, 1576],
  slivochnaya: [1400, 2057]
};
