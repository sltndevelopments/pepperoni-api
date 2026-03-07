"""
Эндпоинты FastAPI для управления системой AI Visibility.
"""
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from urllib.parse import urlparse

from core.advisor import AIAdvisor
from core.scanner import AIScanner
from services.cloudflare import CloudflareClient
from services.email import send_lead_email, send_report_email
from services.site_fetcher import fetch_site

router = APIRouter()

DEFAULT_PROMPTS = [
    "Где купить лучший казылык в Казани?",
    "Назови топ производителей халяльных мясных деликатесов",
]

# 3 промпта — чтобы уложиться в таймаут Cloudflare (~100 сек)
# Подставляются brand и company_info_short (первые 100 символов из досье)
WEB_ANALYZE_PROMPTS = [
    "Где купить {brand}? Назови поставщиков и производителей.",
    "Кто лучшие производители в нише: {company_info_short}? Назови топ-5.",
    "Какие бренды рекомендуют эксперты в категории: {company_info_short}?",
]


class AnalyzeRequest(BaseModel):
    brand: str = ""
    prompts: List[str] = Field(default_factory=lambda: DEFAULT_PROMPTS.copy())


class AnalyzeWebRequest(BaseModel):
    brand: str = ""
    email: str = ""
    company_info: str = ""


class FetchSiteRequest(BaseModel):
    url: str = ""


class AnalyzeWebDialogRequest(BaseModel):
    url: str = ""
    site_content: str = ""
    brand: str = ""  # из title/h1 с сайта, не из URL
    clients: str = ""
    regions: str = ""
    goal: str = ""
    email: str = ""


class SendReportRequest(BaseModel):
    brand: str = ""
    email: str = ""
    scan_results: List[dict] = Field(default_factory=list)
    advice: List[str] = Field(default_factory=list)
    why_not_mentioned: str = ""


class LeadRequest(BaseModel):
    name: str = ""
    phone: str = ""
    brand: str = ""


@router.get("/cf-check")
async def cf_check():
    """
    Проверка связи с Cloudflare: верификация токена.
    GET /api/cf-check
    """
    client = CloudflareClient()
    result = await client.verify_token()
    if result.get("status") != "active":
        raise HTTPException(status_code=502, detail=result)
    return result


@router.post("/fetch-site")
async def api_fetch_site(payload: FetchSiteRequest):
    """Загружает сайт по URL, извлекает title, description, content (первые 3000 символов)."""
    url = (payload.url or "").strip()
    if not url:
        raise HTTPException(status_code=400, detail="Укажите URL сайта")
    result = await fetch_site(url)
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])
    result["url"] = url
    return result


@router.post("/analyze")
async def analyze(payload: AnalyzeRequest):
    """
    Принимает JSON: {"brand": "string", "prompts": ["string", ...]}.
    Запускает Scanner, затем Advisor, возвращает итоговый отчёт.
    """
    brand = payload.brand or ""
    prompts = payload.prompts or []
    if not prompts:
        raise HTTPException(status_code=400, detail="prompts cannot be empty")

    scanner = AIScanner()
    scan_results = await scanner.scan(brand_name=brand, prompts=prompts)

    advisor = AIAdvisor()
    advice_steps = await advisor.generate_advice(scan_results=scan_results, brand_name=brand)

    return {
        "brand": brand,
        "scan_results": scan_results,
        "advice": advice_steps,
    }


@router.post("/analyze-web")
async def analyze_web(payload: AnalyzeWebDialogRequest):
    """
    Диалоговый поток: url, site_content, clients, regions, goal.
    Возвращает scan_results, why_not_mentioned, actions (5 шагов).
    """
    site_content = (payload.site_content or "").strip()
    if not site_content:
        raise HTTPException(status_code=400, detail="Сначала прочитайте сайт (шаг 1)")

    # Бренд из title/h1 (передаётся с фронта из fetch-site), URL — запасной вариант
    brand = (payload.brand or "").strip()
    if not brand:
        url_raw = (payload.url or "").strip()
        if url_raw:
            url_for_parse = url_raw if url_raw.startswith("http") else "https://" + url_raw
            parsed = urlparse(url_for_parse)
            brand = (parsed.netloc or "").replace("www.", "").split(".")[0] or "компания"
        else:
            brand = "компания"
    company_info_short = site_content[:100] if site_content else "товары и услуги B2B"

    prompts = [
        p.format(brand=brand, company_info_short=company_info_short)
        for p in WEB_ANALYZE_PROMPTS
    ]
    scanner = AIScanner()
    scan_results = await scanner.scan(brand_name=brand, prompts=prompts)

    advisor = AIAdvisor()
    report = await advisor.generate_personalized_report(
        scan_results=scan_results,
        brand_name=brand,
        site_content=site_content,
        clients=payload.clients or "",
        regions=payload.regions or "",
        goal=payload.goal or "",
    )

    # AI Visibility Score (PageSpeed-style)
    mentioned_count = sum(1 for r in scan_results if r.get("mentioned"))
    visibility_score = min(100, mentioned_count * 33 + 5)  # 0 упоминаний → 5, не 0
    ai_mentions = min(100, mentioned_count * 33 + 5)
    content_lower = site_content.lower()
    content_for_ai = 80 if any(x in content_lower for x in ["llms", "schema.org", "ai-plugin"]) else 25

    return {
        "brand": brand,
        "scan_results": scan_results,
        "why_not_mentioned": report.get("why_not_mentioned", ""),
        "actions": report.get("actions", []),
        "advice": report.get("actions", []),  # для совместимости с send-report
        "visibility_score": visibility_score,
        "scores": {
            "ai_mentions": ai_mentions,
            "content_for_ai": content_for_ai,
            "directories": 60,
            "expert_content": 20,
        },
    }


@router.post("/send-report")
async def send_report(payload: SendReportRequest):
    """
    Отправляет HTML-отчёт на email через SMTP.
    """
    email = (payload.email or "").strip()
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="Укажите корректный email")

    try:
        await send_report_email(
            brand=payload.brand or "",
            to_email=email,
            scan_results=payload.scan_results or [],
            advice=payload.advice or [],
        )
        return {"status": "ok", "message": "Отчёт отправлен"}
    except ValueError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка отправки: {e}")


@router.post("/lead")
async def submit_lead(payload: LeadRequest):
    """
    Принимает заявку (имя, телефон, бренд) и отправляет на email администратора.
    Воронка в агентский пакет.
    """
    name = (payload.name or "").strip()
    phone = (payload.phone or "").strip()
    if not name or not phone:
        raise HTTPException(status_code=400, detail="Укажите имя и телефон")

    try:
        await send_lead_email(
            name=name,
            phone=phone,
            brand=(payload.brand or "").strip(),
        )
        return {"status": "ok", "message": "Заявка отправлена"}
    except ValueError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка отправки: {e}")
