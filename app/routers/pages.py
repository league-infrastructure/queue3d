from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app import templates
from app.database import get_db
from app.dependencies import get_current_user, get_optional_user, require_admin
from app.models import Location, PrintJob, SessionPassphrase, User
from app.utils.passphrase import ensure_utc

router = APIRouter(tags=["pages"])


@router.get("/")
async def index(request: Request, user: User | None = Depends(get_optional_user)):
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)
    if not user.is_approved and not user.is_admin:
        return RedirectResponse(url="/pending", status_code=302)
    if user.is_admin:
        return RedirectResponse(url="/queue", status_code=302)
    return RedirectResponse(url="/upload", status_code=302)


@router.get("/auth/login")
async def login_page(request: Request):
    error = request.query_params.get("error")
    return templates.TemplateResponse("login.html", {"request": request, "user": None, "error": error})


@router.get("/pending")
async def pending_page(request: Request, user: User = Depends(get_current_user)):
    if user.is_approved or user.is_admin:
        return RedirectResponse(url="/", status_code=302)
    return templates.TemplateResponse("student/pending.html", {"request": request, "user": user})


@router.get("/upload")
async def upload_page(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not user.is_approved and not user.is_admin:
        return RedirectResponse(url="/pending", status_code=302)
    locations = db.query(Location).filter(Location.is_active).order_by(Location.name).all()
    preferred_location = request.session.get("preferred_location")
    # My Print Jobs is now a section of this page, most recent first.
    jobs = (
        db.query(PrintJob)
        .filter(PrintJob.user_id == user.id)
        .order_by(PrintJob.created_at.desc())
        .all()
    )
    return templates.TemplateResponse(
        "student/upload.html",
        {
            "request": request,
            "user": user,
            "locations": locations,
            "preferred_location": preferred_location,
            "jobs": jobs,
        },
    )


@router.get("/my-jobs")
async def my_jobs_page():
    # My Jobs was merged into the upload page; keep the URL working.
    return RedirectResponse(url="/upload#my-jobs", status_code=302)


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
    pending_count = db.query(User).filter(User.is_approved == False).count()
    active_pp = (
        db.query(SessionPassphrase)
        .filter(SessionPassphrase.is_active == True)
        .order_by(SessionPassphrase.created_at.desc())
        .first()
    )
    return templates.TemplateResponse(
        "admin/queue.html",
        {
            "request": request,
            "user": user,
            "jobs": jobs,
            "locations": locations,
            "pending_count": pending_count,
            "passphrase": active_pp.phrase if active_pp else None,
            "passphrase_expires_at": (
                ensure_utc(active_pp.expires_at).isoformat() if active_pp else None
            ),
        },
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
    pending_count = db.query(User).filter(User.is_approved == False).count()
    return templates.TemplateResponse(
        "admin/completed.html",
        {"request": request, "user": user, "jobs": jobs, "locations": locations, "pending_count": pending_count},
    )


@router.get("/locations")
async def locations_page(
    request: Request,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    locations = db.query(Location).order_by(Location.name).all()
    pending_count = db.query(User).filter(User.is_approved == False).count()
    return templates.TemplateResponse(
        "admin/locations.html",
        {"request": request, "user": user, "locations": locations, "pending_count": pending_count},
    )


@router.get("/users")
async def users_page(
    request: Request,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    pending_users = (
        db.query(User)
        .filter(User.is_approved == False)
        .order_by(User.created_at.desc())
        .all()
    )
    approved_users = (
        db.query(User)
        .filter(User.is_approved == True)
        .order_by(User.display_name.asc())
        .all()
    )
    pending_count = len(pending_users)
    return templates.TemplateResponse(
        "admin/users.html",
        {
            "request": request,
            "user": user,
            "pending_users": pending_users,
            "approved_users": approved_users,
            "pending_count": pending_count,
        },
    )
