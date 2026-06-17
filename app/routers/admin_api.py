from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_admin
from app.models import Location, PrintJob, SessionPassphrase, User, _utcnow
from app.utils.passphrase import PASSPHRASE_TTL, ensure_utc, generate_passphrase
from app.utils.storage import delete_upload

router = APIRouter(prefix="/api", tags=["admin"])


@router.get("/locations")
async def list_locations(
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    locations = db.query(Location).order_by(Location.name).all()
    return [
        {
            "id": loc.id,
            "name": loc.name,
            "description": loc.description,
            "is_active": loc.is_active,
        }
        for loc in locations
    ]


@router.post("/locations")
async def create_location(
    request: Request,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    data = await request.json()
    name = data.get("name", "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Name is required")

    existing = db.query(Location).filter(Location.name == name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Location already exists")

    location = Location(name=name, description=data.get("description", "").strip() or None)
    db.add(location)
    db.commit()
    db.refresh(location)
    return {"id": location.id, "name": location.name, "description": location.description}


@router.patch("/locations/{location_id}")
async def update_location(
    location_id: int,
    request: Request,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    location = db.query(Location).filter(Location.id == location_id).first()
    if not location:
        raise HTTPException(status_code=404, detail="Location not found")

    data = await request.json()
    if "name" in data:
        name = data["name"].strip()
        if not name:
            raise HTTPException(status_code=400, detail="Name cannot be empty")
        location.name = name
    if "description" in data:
        location.description = data["description"].strip() or None
    if "is_active" in data:
        location.is_active = bool(data["is_active"])

    db.commit()
    db.refresh(location)
    return {"id": location.id, "name": location.name, "description": location.description, "is_active": location.is_active}


@router.delete("/locations/{location_id}")
async def delete_location(
    location_id: int,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    location = db.query(Location).filter(Location.id == location_id).first()
    if not location:
        raise HTTPException(status_code=404, detail="Location not found")

    location.is_active = False
    db.commit()
    return {"ok": True}


# --- User approval endpoints ---

@router.get("/pending-count")
async def pending_count(
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    count = db.query(User).filter(User.is_approved == False).count()
    return {"count": count}


@router.post("/users/{user_id}/approve")
async def approve_user(
    user_id: str,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    target.is_approved = True
    db.commit()
    return {"ok": True}


@router.post("/users/{user_id}/disapprove")
async def disapprove_user(
    user_id: str,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    if target.is_admin:
        raise HTTPException(status_code=400, detail="Cannot disapprove admin users")
    target.is_approved = False
    db.commit()
    return {"ok": True}


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: str,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    if target.is_admin:
        raise HTTPException(status_code=400, detail="Cannot delete admin users")
    # Delete the user's print jobs and uploaded files first
    jobs = db.query(PrintJob).filter(PrintJob.user_id == user_id).all()
    for job in jobs:
        delete_upload(job.id)
        db.delete(job)
    db.delete(target)
    db.commit()
    return {"ok": True}


# --- Session passphrase ---

@router.post("/admin/session/passphrase/refresh")
async def refresh_session_passphrase(
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    db.query(SessionPassphrase).filter(SessionPassphrase.is_active == True).update(
        {SessionPassphrase.is_active: False}, synchronize_session=False
    )
    sp = SessionPassphrase(
        phrase=generate_passphrase(),
        expires_at=_utcnow() + PASSPHRASE_TTL,
        created_by=user.id,
    )
    db.add(sp)
    db.commit()
    db.refresh(sp)
    return {
        "phrase": sp.phrase,
        "expires_at": ensure_utc(sp.expires_at).isoformat(),
        "created_at": ensure_utc(sp.created_at).isoformat(),
    }
