from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime
from typing import List

from app.database import get_db
from app.models.database_models import User
from app.schemas.schemas import AvailabilityRequest, AvailabilityResponse, EngineerAvailability
from app.services.auth import decode_access_token
from app.services.availability import get_qualified_engineers, get_engineer_availability

router = APIRouter(prefix="/availability", tags=["Availability"])


async def get_current_user(authorization: str, db: AsyncSession) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing authorization")
    
    token = authorization.replace("Bearer ", "")
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    
    result = await db.execute(select(User).where(User.id == int(payload.get("sub"))))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


async def get_admin_token(db: AsyncSession) -> str:
    result = await db.execute(
        select(User).where(User.role == "admin", User.microsoft_access_token.isnot(None))
    )
    admin = result.scalar_one_or_none()
    if admin and admin.microsoft_access_token:
        return admin.microsoft_access_token
    return None


@router.post("/check", response_model=AvailabilityResponse)
async def check_availability(
    request: AvailabilityRequest,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    await get_current_user(authorization, db)
    
    try:
        target_date = datetime.strptime(request.date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid date format. Use YYYY-MM-DD"
        )
    
    engineers = await get_qualified_engineers(
        db,
        request.product_id,
        request.change_type_id
    )
    
    if not engineers:
        return AvailabilityResponse(
            date=request.date,
            engineers=[]
        )
    
    admin_token = await get_admin_token(db)
    
    engineer_availabilities = []
    for engineer in engineers:
        availability = await get_engineer_availability(
            db,
            engineer,
            target_date,
            request.duration_hours,
            admin_token
        )
        engineer_availabilities.append(EngineerAvailability(**availability))
    
    return AvailabilityResponse(
        date=request.date,
        engineers=engineer_availabilities
    )
