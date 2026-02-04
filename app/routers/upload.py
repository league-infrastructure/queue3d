from fastapi import APIRouter, Depends, Form, HTTPException, Request, UploadFile
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import Location, PrintJob, User
from app.utils.stl_validator import validate_stl
from app.utils.storage import save_upload
from app.config import settings

router = APIRouter(prefix="/api", tags=["upload"])


@router.post("/upload")
async def upload_stl(
    request: Request,
    file: UploadFile,
    location_id: int = Form(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not file.filename or not file.filename.lower().endswith(".stl"):
        raise HTTPException(status_code=400, detail="Only .stl files are accepted")

    location = db.query(Location).filter(Location.id == location_id, Location.is_active).first()
    if not location:
        raise HTTPException(status_code=400, detail="Invalid location")

    file_bytes = await file.read()

    is_valid, error = validate_stl(file_bytes, settings.MAX_UPLOAD_SIZE)
    if not is_valid:
        raise HTTPException(status_code=400, detail=error)

    # Get next position (FIFO ordering)
    max_pos = db.query(func.max(PrintJob.position)).scalar() or 0

    job = PrintJob(
        user_id=user.id,
        location_id=location_id,
        filename=file.filename,
        file_path="",  # set after save
        file_size=len(file_bytes),
        position=max_pos + 1,
    )
    db.add(job)
    db.flush()  # get the job.id

    relative_path = save_upload(job.id, file_bytes, file.filename)
    job.file_path = relative_path
    db.commit()
    db.refresh(job)

    # Count active jobs in queue (queued or printing) — this is the user's place in line
    queue_position = (
        db.query(func.count(PrintJob.id))
        .filter(PrintJob.status.in_(PrintJob.ACTIVE_STATUSES))
        .scalar()
    )

    # Remember the selected location for next upload
    request.session["preferred_location"] = location_id

    return {"id": job.id, "filename": job.filename, "status": job.status, "position": queue_position}


@router.get("/my-jobs")
async def my_jobs_api(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    jobs = (
        db.query(PrintJob)
        .filter(PrintJob.user_id == user.id)
        .order_by(PrintJob.created_at.desc())
        .all()
    )
    return [
        {
            "id": j.id,
            "status": j.status,
            "feedback": j.feedback,
            "reject_reason": j.reject_reason,
            "fail_count": j.fail_count,
        }
        for j in jobs
    ]
