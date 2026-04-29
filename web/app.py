import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from web.routes import router

app = FastAPI(title="RAG Assistant Web")
app.include_router(router)
_WEB_DIR = Path(__file__).resolve().parent
app.mount("/static", StaticFiles(directory=str(_WEB_DIR / "static")), name="static")


@app.on_event("startup")
def announce_web_url():
    logger = logging.getLogger("uvicorn.error")
    logger.info("Web interface is available at the uvicorn URL above.")
    for route in app.routes:
        logger.info("Route: %s %s", route.path, getattr(route, "methods", ""))

