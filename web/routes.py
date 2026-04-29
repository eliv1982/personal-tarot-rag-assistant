from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from rag_pipeline import RAGPipeline

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent / "templates"))
_pipeline: Optional[RAGPipeline] = None


def _get_pipeline() -> RAGPipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = RAGPipeline()
    return _pipeline


@router.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "question": "",
            "answer": "",
            "context_docs": [],
            "error": "",
            "technical_error": "",
            "show_debug_context": False,
            "from_cache": None,
            "model": "",
            "cached_at": "",
        },
    )


@router.get("/ask")
def ask_get():
    return RedirectResponse(url="/", status_code=303)


@router.post("/ask", response_class=HTMLResponse)
def ask(
    request: Request,
    question: str = Form(default=""),
    show_debug_context: Optional[str] = Form(default=None),
):
    answer = ""
    context_docs: List[Dict[str, Any]] = []
    error = ""
    technical_error = ""
    from_cache = None
    model = ""
    cached_at = ""
    normalized_question = question.strip()
    debug_enabled = bool(show_debug_context)

    if not normalized_question:
        error = "Добавь вопрос или тему расклада."
    else:
        try:
            result = _get_pipeline().query(normalized_question)
            answer = result.get("answer", "")
            if debug_enabled:
                context_docs = result.get("context_docs") or []
            from_cache = result.get("from_cache")
            model = result.get("model", "")
            cached_at = result.get("cached_at", "")
        except Exception as exc:  # noqa: BLE001 - route-level safe message handling
            error = "Не получилось получить интерпретацию. Попробуй ещё раз."
            if debug_enabled:
                technical_error = f"{exc.__class__.__name__}: {exc}"

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "question": normalized_question,
            "answer": answer,
            "context_docs": context_docs,
            "error": error,
            "technical_error": technical_error,
            "show_debug_context": debug_enabled,
            "from_cache": from_cache,
            "model": model,
            "cached_at": cached_at,
        },
    )

