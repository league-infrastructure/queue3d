from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_admin
from app.models import Location, User

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
