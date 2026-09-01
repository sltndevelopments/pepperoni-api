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
    nitrite: "Нитритсыз", hero: "Мәхәббәт тәмдән башлана",
    lead: "Казаннан биш ит продукты: состав ачык, натрий нитриты юк, туклану кыйммәтен сатып алуга кадәр укырга була.",
    range: "Биш продукт. Состав кыскартылмый.", see: "Продуктны карау", calculated: "Исәпләнгән КБҖУ",
    halal: "Хәләл расланган", noHalal: "Хәләл белдерелмәгән", weight: "Нетто авырлыгы",
    composition: "Состав", allergens: "Аллергеннар", nutrition: "100 г өчен КБҖУ",
    nutritionNote: "Чимал массасының 100 г өчен исәпләнгән күрсәткеч; лаборатор кыйммәт түгел.",
    kcal: "ккал", protein: "аксымнар", fat: "майлар", carbs: "углеводлар",
    contact: "Спецификацияләр сорау", footer: "«Казанские Деликатесы» ҖЧҖ бренды",
    status: "Мәгълүмат статусы", evidence: "Рецептура һәм состав эчке документлар буенча тикшерелгән.",
    advantages: "Нигә Ярату", quality: "Сыйфат контроле",
    contacts: "Элемтә", connect: "Элемтәгә керергә", seeNutrition: "Туклану кыйммәтен карау",
    menu: "Меню", mobileMenu: "Кесә менюсы", skip: "Эчтәлеккә", privacy: "Шәхси мәгълүматлар",
    languages: "Тел", qrCaption: "Этикетка башка телләрдә",
    qrLead: "Упаковкадагы QR шушы битне ача: туклану кыйммәтен рус, инглиз һәм татар телләрендә укырга була."
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
    per: "100 г өчен",
    net: "Нетто авырлыгы",
    energy: "Калориялелек / Энергетик кыйммәт",
    kcal: "ккал",
    kj: "кДж",
    calories: "Калорияләр",
    dv: "тәүлек нормасыннан %*",
    protein: (p, g) => `Аксымнар ≥ ${p} ${g}`,
    fat: (p, g) => `Майлар барлыгы ≤ ${p} ${g}`,
    sat: (p, g) => `Туендырылган майлар ${p} ${g}`,
    carbs: (p, g) => `Углеводлар ≤ ${p} ${g}`,
    foot: "* ТР ТС 022/2011 буенча тәүлек нормасыннан %. Гомуми тәкъдим өчен 2500 ккал. Хәзерге рецептура буенча исәп, лаборатор протокол түгел.",
    ingredients: "Состав",
    ingredientsPref: "Состав:",
    contains: "Эчендә:"
  }
};

export const positioning = {
  vetchina: {
    ru: ["Самая лёгкая в линейке", "125 ккал и 16,7 г белка на 100 г — минимальная калорийность и максимальное содержание белка среди пяти текущих продуктов."],
    en: ["The lightest in the range", "At 125 kcal and 16.7 g protein per 100 g, it has the lowest calories and highest protein among the five current products."],
    tt: ["Сызыкта иң җиңеле", "100 г өчен 125 ккал һәм 16,7 г аксым — биш продукт арасында иң түбән калориялелек һәм иң күп аксым."]
  },
  mramornaya: {
    ru: ["Выразительный мясной профиль", "Курица и говядина, варёно-копчёный формат и 0,5 г углеводов на 100 г."],
    en: ["A bold meat profile", "Chicken and beef in a cooked-smoked format, with 0.5 g carbohydrate per 100 g."],
    tt: ["Ачык ит тәме", "Тавык һәм сыер ите, пешерелгән-ысланган формат һәм 100 г өчен 0,5 г углевод."]
  },
  brokkoli: {
    ru: ["Брокколи в раскрытом составе", "Курица и говядина с брокколи; 13 г белка и 1,5 г углеводов на 100 г."],
    en: ["Broccoli in the disclosed recipe", "Chicken and beef with broccoli; 13 g protein and 1.5 g carbohydrate per 100 g."],
    tt: ["Ачык составта брокколи", "Тавык һәм сыер ите брокколи белән; 100 г өчен 13 г аксым һәм 1,5 г углевод."]
  },
  molochnye: {
    ru: ["Мягкий классический вкус", "Молочный белок, сухое молоко и пряности раскрыты в составе; 13,5 г белка на 100 г."],
    en: ["A mild classic taste", "Milk protein, milk powder and spices are disclosed in full; 13.5 g protein per 100 g."],
    tt: ["Йомшак классик тәм", "Сөт аксымы, кипкән сөт һәм тәмләткечләр составта ачылган; 100 г өчен 13,5 г аксым."]
  },
  slivochnaya: {
    ru: ["Нежный сливочный профиль", "14,4 г белка и 0,7 г углеводов на 100 г — с полностью раскрытым составом."],
    en: ["A gentle creamy profile", "14.4 g protein and 0.7 g carbohydrate per 100 g, with the full ingredient list disclosed."],
    tt: ["Нәфис каймак тәме", "100 г өчен 14,4 г аксым һәм 0,7 г углевод — состав тулысынча ачылган."]
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
    faqLead: "Сайтта бәяләр һәм оферта басылмый.",
    contactTitle: "Тәэминат турында сөйләшәбезме?",
    contactLead: "Актуаль спецификацияләрне, фасовкаларны, документларны һәм шартларын турыдан-туры җитештерүчедән сорагыз.",
    address: "Казан, Аграрная ур., 2, 7 нче офис",
    productLabel: "Мөһиме барысы да бер этикеткада.",
    productStatus: "Состав: recipe-sourced · Хәләл: ДУМ РТ №614А/2024 сертификаты",
    specTitle: "Спецификацияләр кирәкме?",
    specLead: "Документларны, фасовкаларны һәм тәэминат шартларын турыдан-туры җитештерүчедән сорагыз.",
    facts: [
      ["01", "Натрий нитриты юк", "Статус тикшерелгән биш хәзерге рецептурага кагыла."],
      ["02", "Состав кыскартылмый", "Комплекс кушылмалар кергән ингредиентларга кадәр ачылган."],
      ["03", "Туклану кыйммәте ачык", "КБҖУ һәм тәүлек нормасы процентлары сатып алуга кадәр күренә."]
    ],
    story: {
      eyebrow: "Нигә Ярату",
      title: "Тәм намуслы сайлаудан башлана.",
      lead: "Яратуны шуның өчен ясадык: ит продуктын күз йомып сайларга туры килмәсен. Сайтта һәр продуктның хәзерге составы, аллергеннары һәм исәпләнгән туклану кыйммәте бар.",
      quote: "Тыш яктагы вәгъдәләр түгел, ә тикшереп булган состав һәм саннар."
    },
    production: {
      eyebrow: "Җитештерү",
      title: "Казанда ясалган. Контроль — һәр дәрәҗәдә.",
      lead: "Ярату — Казанда хәләл ит продуктлары җитештерүче «Казанские Деликатесы» ҖЧҖ бренды. Җитештерү HACCP системасы, ISO 22000:2018 стандарты һәм ТР ТС 021/2011 таләпләре буенча эшли.",
      standards: [["HACCP", "Процесс куркынычсызлыгы"], ["ISO 22000:2018", "Ашамлык куркынычсызлыгы системасы"], ["ТР ТС 021/2011", "Ашамлык продуктларына таләпләр"]]
    },
    quality: {
      eyebrow: "Сыйфат контроле",
      title: "Ышаныч фактларга корыла.",
      lead: "Расланган продукт фактларын исәпләнгән мәгълүматтан аерабыз һәм һәр чыганак статусын ачык күрсәтәбез.",
      items: [
        ["01", "HACCP һәм ISO 22000", "Куркынычсызлык идарәсе системалары «Казанские Деликатесы» ҖЧҖ җитештерүендә кулланыла."],
        ["02", "Хәләл сертификаты", "Биш хәзерге продукт та ДУМ РТ №614А/2024 сертификаты өлкәсенә керә."],
        ["03", "Тулы ачыклык", "Комплекс кушылмалар аерым ингредиентларга кадәр санап чыгарылган, аллергеннар аерым күрсәтелгән."],
        ["04", "КБҖУ статусы намуслы", "Туклану кыйммәте хәзерге рецептура буенча исәпләнгән һәм лаборатор протокол итеп бирелми."]
      ]
    },
    faqs: [
      ["Ярату нәрсә ул?", "Ярату — «Казанские Деликатесы» ҖЧҖ ит бренды: Казаннан биш пешерелгән продукт, натрий нитритысыз һәм ингредиентларга кадәр ачылган состав белән."],
      ["Бу сызык кем өчен?", "Кибетләр, дистрибьюторлар һәм «чиста продукт» лозунгы түгел, ә тикшереп булган состав кирәк булган алучылар өчен."],
      ["Бәяләр кайда?", "Ачык кулланучы прайсы юк. Актуаль спецификацияләрне, фасовкаларны һәм тәэминат шартларын җитештерүчедән сорыйлар."],
      ["Бөтен сызык хәләлме?", "Әйе. Биш хәзерге продукт та Хәләл ДУМ РТ №614А/2024 сертификаты өлкәсенә керә."],
      ["КБҖУ лаборатормы?", "Юк. Бу хәзерге рецептура буенча чимал массасының 100 г өчен исәп, сынау протоколы түгел."],
      ["Тәэминатны ничек сорарга?", "info@kazandelikates.tatar адресына языгыз яки +7 987 217-02-02 номерына шалтыратыгыз. Җитештерүче Казанда, Аграрная ур., 2, 7 нче офис."]
    ],
    halalLine: "Биш продукт та Хәләл ДУМ РТ №614А/2024 сертификаты өлкәсенә керә.",
    retailTitle: "Ярату кибетләр һәм дистрибьюторлар өчен",
    retailAnswer: "Актуаль спецификацияләрне, фасовкаларны, документларны һәм тәэминат шартларын турыдан-туры җитештерүчедән сорагыз.",
    retailAddress: "Казан шәһәре, Аграрная ур., 2, 7 нче офис",
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
      title: "Ачык состав нәрсә аңлата?",
      answer: "Ачык состав комплекс кушылманың исемен генә түгел, аңа кергән ингредиентларны да санап чыгара.",
      detail: "Биш продукт битендә рецептура һәм спецификацияләрдән хәзерге состав китерелгән. Состав статусы — recipe-sourced; сатып алучы өчен партия маркировкасы төп чыганак булып кала.",
      q: "Билгеле бер продукт составын кайда тикшерергә?",
      a: "Продуктның аерым битендә һәм аның чын упаковкасында."
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
      title: "«Натрий нитритысыз» нәрсә аңлата?",
      answer: "Yaratu-ның биш продуктының хәзерге рецептураларында натрий нитриты E250 кулланылмый.",
      detail: "Раслау тикшерелгән хәзерге рецептураларга кагыла. Бу тоз, тәмләткечләр яки технологик эшкәртү юк дигән сүз түгел.",
      q: "Бу лаборатор раслаумы?",
      a: "Юк. Статус чыганагы — хәзерге рецептуралар һәм спецификацияләр; КБҖУ да исәпләнгән булып кала."
    }
  }
};

export const markdownPages = {
  retail: {
    ru: `# Yaratu для магазинов и дистрибьюторов\n\nЗапросите актуальные спецификации, фасовки, документы и условия поставки напрямую у производителя.\n\n- ООО «Казанские Деликатесы»\n- г. Казань, ул. Аграрная, д. 2, оф. 7\n- +7 987 217-02-02\n- info@kazandelikates.tatar\n`,
    en: `# Yaratu for retailers and distributors\n\nRequest current specifications, pack formats, documents and supply terms directly from the manufacturer.\n\n- Kazan Delicacies LLC\n- 2 Agrarnaya Street, office 7, Kazan, Russia\n- +7 987 217-02-02\n- info@kazandelikates.tatar\n`,
    tt: `# Ярату кибетләр һәм дистрибьюторлар өчен\n\nАктуаль спецификацияләрне, фасовкаларны, документларны һәм тәэминат шартларын турыдан-туры җитештерүчедән сорагыз.\n\n- «Казанские Деликатесы» ҖЧҖ\n- Казан шәһәре, Аграрная ур., 2, 7 нче офис\n- +7 987 217-02-02\n- info@kazandelikates.tatar\n`
  },
  ingredients: {
    ru: `# Что значит раскрытый состав?\n\nРаскрытый состав перечисляет не только название комплексной смеси, но и входящие в неё ингредиенты. Статус состава — recipe-sourced; маркировка партии остаётся приоритетным источником.\n`,
    en: `# What does a disclosed ingredient list mean?\n\nA disclosed list names the ingredients inside compound mixes instead of showing only a trade name. The pack label remains the primary source for a purchased batch.\n`,
    tt: `# Ачык состав нәрсә аңлата?\n\nАчык состав комплекс кушылманың исемен генә түгел, аңа кергән ингредиентларны да санап чыгара. Состав статусы — recipe-sourced; партия маркировкасы төп чыганак булып кала.\n`
  },
  nitrite: {
    ru: `# Что значит «без нитрита натрия»?\n\nВ текущих рецептурах пяти продуктов Yaratu нитрит натрия E250 не используется. Это статус рецептуры, не лабораторное утверждение.\n`,
    en: `# What does “without sodium nitrite” mean?\n\nSodium nitrite E250 is not used in the current recipes of the five Yaratu products. Nutrition figures are calculated, not laboratory-tested.\n`,
    tt: `# «Натрий нитритысыз» нәрсә аңлата?\n\nYaratu-ның биш продуктының хәзерге рецептураларында натрий нитриты E250 кулланылмый. Бу рецептура статусы, лаборатор раслау түгел.\n`
  }
};
