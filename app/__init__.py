from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from app.config import settings
from app.database import init_db

BASE_DIR = Path(__file__).resolve().parent

templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


def create_app() -> FastAPI:
    app = FastAPI(title=settings.APP_NAME, debug=settings.DEBUG)

    app.add_middleware(SessionMiddleware, secret_key=settings.SECRET_KEY)

    app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

    settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    from app.auth import router as auth_router
    from app.routers.admin_api import router as admin_router
    from app.routers.pages import router as pages_router
    from app.routers.queue_api import router as queue_router
    from app.routers.upload import router as upload_router

    app.include_router(auth_router)
    app.include_router(pages_router)
    app.include_router(queue_router)
    app.include_router(admin_router)
    app.include_router(upload_router)

    @app.on_event("startup")
    def on_startup():
        init_db()

    return app
