from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app import templates
from app.database import get_db
from app.dependencies import get_current_user, get_optional_user, require_admin
from app.models import Location, PrintJob, User

router = APIRouter(tags=["pages"])


@router.get("/")
async def index(request: Request, user: User | None = Depends(get_optional_user)):
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)
    if user.is_admin:
        return RedirectResponse(url="/queue", status_code=302)
    return RedirectResponse(url="/upload", status_code=302)


@router.get("/auth/login")
async def login_page(request: Request):
    error = request.query_params.get("error")
    return templates.TemplateResponse("login.html", {"request": request, "user": None, "error": error})


@router.get("/upload")
async def upload_page(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    locations = db.query(Location).filter(Location.is_active).order_by(Location.name).all()
    preferred_location = request.session.get("preferred_location")
    return templates.TemplateResponse(
        "student/upload.html",
        {"request": request, "user": user, "locations": locations, "preferred_location": preferred_location},
    )


@router.get("/my-jobs")
async def my_jobs_page(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    jobs = (
        db.query(PrintJob)
        .filter(PrintJob.user_id == user.id)
        .order_by(PrintJob.created_at.desc())
        .all()
    )
    return templates.TemplateResponse(
        "student/my_jobs.html", {"request": request, "user": user, "jobs": jobs}
    )


@router.get("/queue")
async def queue_page(
    request: Request,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    jobs = (
        db.query(PrintJob)
        .filter(PrintJob.status.in_(PrintJob.ACTIVE_STATUSES))
        .order_by(PrintJob.position.asc())
        .all()
    )
    locations = db.query(Location).filter(Location.is_active).order_by(Location.name).all()
    return templates.TemplateResponse(
        "admin/queue.html", {"request": request, "user": user, "jobs": jobs, "locations": locations}
    )


@router.get("/completed")
async def completed_page(
    request: Request,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    jobs = (
        db.query(PrintJob)
        .filter(PrintJob.status.in_(PrintJob.COMPLETED_STATUSES))
        .order_by(PrintJob.updated_at.desc())
        .all()
    )
    locations = db.query(Location).filter(Location.is_active).order_by(Location.name).all()
    return templates.TemplateResponse(
        "admin/completed.html", {"request": request, "user": user, "jobs": jobs, "locations": locations}
    )


@router.get("/locations")
async def locations_page(
    request: Request,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    locations = db.query(Location).order_by(Location.name).all()
    return templates.TemplateResponse(
        "admin/locations.html", {"request": request, "user": user, "locations": locations}
    )
