"""
AI Visibility SaaS — точка входа.
Запросы принимаются только через Cloudflare (проверка заголовков).
"""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader

from api.routes import router as api_router
from core.cloudflare_middleware import CloudflareGuardMiddleware

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
STATIC_DIR = Path(__file__).resolve().parent / "static"

env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Загрузка настроек при старте."""
    yield


app = FastAPI(
    title="Saidsultan AI Visibility Core",
    lifespan=lifespan,
)

# Middleware: только трафик через Cloudflare (запрет прямого доступа по IP)
app.add_middleware(CloudflareGuardMiddleware)

app.include_router(api_router, prefix="/api", tags=["api"])

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Главная страница — веб-интерфейс платформы."""
    template = env.get_template("index.html")
    return template.render()
