# Cursor: Architect → Worker

Автономия здесь = **задача + исполнитель + механический гейт + лимит итераций + эскалация**.
Не «Opus и Sonnet болтают без тебя».

## Файлы

| Файл | Кто | Зачем |
|------|-----|-------|
| `CLAUDE.md` | человек | Рельсы исполнителя (Claude Code + Cursor) |
| `instructions/next-task.md` | Architect → Worker | Один Current step |
| `AGENTS.md` | человек | Правда о проекте |
| SEO-мозг на VPS | cron | Настоящая автономия: invariants + page_reviewer + budget cap |

## Цикл

### 1. Architect (Chat, Cmd+L) — Opus 4.8

```
Architect: обнови instructions/next-task.md — Goal, один Current step, Backlog. Код не меняй.
```

### 2. Worker (Agent, Cmd+I) — Sonnet (`claude-sonnet-4-6`)

```
@instructions/next-task.md @CLAUDE.md
Выполни Current step. В Log — хеш коммита + grep/тесты, не «готово». Остановись.
```

Diff-approval оставь для необратимого (prod, delete, deploy).

### 3. Architect читает Log → следующий Current step

## Где настоящая автономия уже есть

GEO-конвейер на VPS: `generate_geo_bulk` → `page_reviewer` → `invariants` →
`deploy_check` → дневной budget cap. Там можно отпускать — гейт механический.

Где гейта нет (архитектурные решения, claim'ы, пороги) — эскалация человеку.

## Модели (актуально)

- Architect: **Opus 4.8**
- Worker: **Sonnet** (`claude-sonnet-4-6`)

## Устарело

- `instruction_next.md` → перенесено в `instructions/next-task.md`
- Копипаст промтов между Claude Desktop и Cursor — заменён файлом handoff
