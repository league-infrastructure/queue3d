from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app import templates
from app.database import get_db
from app.dependencies import get_current_user, require_admin
from app.models import PrintJob, User
from app.utils.storage import delete_upload, get_upload_path

router = APIRouter(prefix="/api", tags=["queue"])


@router.get("/jobs")
async def list_jobs(
    status: str | None = None,
    scope: str | None = None,
    limit: int = 100,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    query = db.query(PrintJob).order_by(PrintJob.position.asc())
    if scope == "active":
        query = query.filter(PrintJob.status.in_(PrintJob.ACTIVE_STATUSES))
    elif scope == "completed":
        query = query.filter(PrintJob.status.in_(PrintJob.COMPLETED_STATUSES))
    if status:
        query = query.filter(PrintJob.status == status)
    jobs = query.limit(limit).all()
    return [
        {
            "id": j.id,
            "filename": j.filename,
            "status": j.status,
            "position": j.position,
            "user_email": j.user.email,
            "user_name": j.user.display_name,
            "location": j.location.name,
            "file_size": j.file_size,
            "feedback": j.feedback,
            "reject_reason": j.reject_reason,
            "fail_count": j.fail_count,
            "created_at": j.created_at.isoformat(),
            "updated_at": j.updated_at.isoformat(),
        }
        for j in jobs
    ]


@router.get("/jobs/{job_id}")
async def get_job(
    job_id: str,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    job = db.query(PrintJob).filter(PrintJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {
        "id": job.id,
        "filename": job.filename,
        "status": job.status,
        "position": job.position,
        "user_email": job.user.email,
        "user_name": job.user.display_name,
        "location": job.location.name,
        "file_size": job.file_size,
        "feedback": job.feedback,
        "reject_reason": job.reject_reason,
        "fail_count": job.fail_count,
        "created_at": job.created_at.isoformat(),
        "updated_at": job.updated_at.isoformat(),
    }


@router.patch("/jobs/{job_id}")
async def update_job(
    job_id: str,
    request: Request,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    job = db.query(PrintJob).filter(PrintJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    data = await request.json()

    if "status" in data:
        new_status = data["status"]
        if new_status not in PrintJob.VALID_STATUSES:
            raise HTTPException(status_code=400, detail=f"Invalid status: {new_status}")

        if new_status == "failed":
            # Mark the failure and requeue to front
            job.fail_count += 1
            job.status = "queued"
            min_pos = db.query(func.min(PrintJob.position)).scalar() or 0
            job.position = min_pos - 1
        else:
            job.status = new_status

    if "feedback" in data:
        job.feedback = data["feedback"]

    if "reject_reason" in data:
        job.reject_reason = data["reject_reason"]

    db.commit()
    db.refresh(job)

    return {
        "id": job.id,
        "filename": job.filename,
        "status": job.status,
        "feedback": job.feedback,
        "reject_reason": job.reject_reason,
    }


@router.delete("/jobs/{job_id}")
async def delete_job(
    job_id: str,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    job = db.query(PrintJob).filter(PrintJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    delete_upload(job.id)
    db.delete(job)
    db.commit()
    return {"ok": True}


@router.get("/jobs/{job_id}/download")
async def download_job(
    job_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    job = db.query(PrintJob).filter(PrintJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    # Admins can fetch any job; students may fetch only their own (for the viewer).
    if not user.is_admin and job.user_id != user.id:
        raise HTTPException(status_code=403, detail="Not allowed")

    file_path = get_upload_path(job.file_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found on disk")

    return FileResponse(
        path=str(file_path),
        filename=job.filename,
        media_type="application/octet-stream",
    )


# HTMX partial endpoints

@router.get("/partials/queue-card/{job_id}", include_in_schema=False)
async def queue_card_partial(
    job_id: str,
    request: Request,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    job = db.query(PrintJob).filter(PrintJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return templates.TemplateResponse(
        "components/queue_card.html", {"request": request, "job": job, "user": user}
    )


@router.get("/partials/job-modal/{job_id}", include_in_schema=False)
async def job_modal_partial(
    job_id: str,
    request: Request,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    job = db.query(PrintJob).filter(PrintJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return templates.TemplateResponse(
        "components/job_modal.html", {"request": request, "job": job, "user": user}
    )
