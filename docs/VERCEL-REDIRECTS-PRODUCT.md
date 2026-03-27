# Редиректы для страниц товаров (api → www)

Если ещё не добавлены, добавьте в `vercel.json` в массив `redirects`:

```json
{"source":"/product/:path*","destination":"https://www.pepperoni.tatar/product/:path*","permanent":true,"has":[{"type":"host","value":"api.pepperoni.tatar"}]},
{"source":"/en/product/:path*","destination":"https://www.pepperoni.tatar/en/product/:path*","permanent":true,"has":[{"type":"host","value":"api.pepperoni.tatar"}]}
```

Вставьте перед закрывающей `]` массива redirects (после редиректа `/for-kazandelikates/:path*`).
