# Файлы для kazandelikates.tatar

Эти файлы нужно разместить на основном сайте `kazandelikates.tatar`:

## Что и куда

| Файл | Куда разместить | Зачем |
|------|----------------|-------|
| `llms.txt` | `https://kazandelikates.tatar/llms.txt` | Чтобы AI-боты (ChatGPT, Claude, Gemini, Perplexity) находили информацию о компании через основной домен |
| `robots.txt` | `https://kazandelikates.tatar/robots.txt` | Правила для поисковых роботов (если ещё нет) |

## Что добавить в HTML основного сайта

В `<head>` каждой страницы `kazandelikates.tatar` добавить:

```html
<!-- Для AI-ботов -->
<link rel="llms" href="/llms.txt" type="text/plain" title="LLM instructions">

<!-- Связь с API -->
<link rel="api" href="https://api.pepperoni.tatar/openapi.yaml" type="application/x-yaml">

<!-- Schema.org связь между доменами -->
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "Organization",
  "name": "Казанские Деликатесы",
  "url": "https://kazandelikates.tatar",
  "sameAs": [
    "https://pepperoni.tatar",
    "https://api.pepperoni.tatar"
  ],
  "hasOfferCatalog": {
    "@type": "OfferCatalog",
    "name": "Каталог продукции",
    "url": "https://api.pepperoni.tatar/products.json"
  }
}
</script>
```
