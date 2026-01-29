from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from sqlalchemy.orm import selectinload
from datetime import datetime, timedelta
from typing import List, Optional

from app.database import get_db
from app.models.database_models import (
    User, Engineer, Booking, BookingStatus, BookingStatusUpdate,
    EngineerUnavailability, UserRole
)
from app.schemas.schemas import (
    BookingResponse, BookingStatusUpdateCreate, BookingStatusUpdateResponse,
    EngineerUnavailabilityCreate, EngineerUnavailabilityResponse,
    EngineerDashboardStats, EngineerResponse
)
from app.services.auth import decode_access_token

router = APIRouter(prefix="/engineer", tags=["engineer"])


async def get_current_user(authorization: str, db: AsyncSession) -> User:
    """Get the current user from the authorization token"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")
    
    token = authorization.replace("Bearer ", "")
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")
    
    result = await db.execute(
        select(User).where(User.id == int(user_id))
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return user


async def get_engineer_user(authorization: str, db: AsyncSession) -> tuple[User, Engineer]:
    """Get the current user and verify they are an engineer"""
    user = await get_current_user(authorization, db)
    
    # Check if user is an engineer or admin
    if user.role not in [UserRole.ENGINEER, UserRole.ADMIN]:
        raise HTTPException(status_code=403, detail="Access denied. Engineer or admin role required.")
    
    # Get engineer profile
    result = await db.execute(
        select(Engineer).options(
            selectinload(Engineer.user)
        ).where(Engineer.user_id == user.id)
    )
    engineer = result.scalar_one_or_none()
    
    if not engineer and user.role == UserRole.ENGINEER:
        raise HTTPException(status_code=404, detail="Engineer profile not found")
    
    return user, engineer


@router.get("/profile")
async def get_engineer_profile(
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """Get the current engineer's profile"""
    user, engineer = await get_engineer_user(authorization, db)
    
    if not engineer:
        raise HTTPException(status_code=404, detail="Engineer profile not found")
    
    return {
        "id": engineer.id,
        "user_id": engineer.user_id,
        "calendar_email": engineer.calendar_email,
        "is_available": engineer.is_available,
        "working_hours_start": engineer.working_hours_start,
        "working_hours_end": engineer.working_hours_end,
        "user": {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role.value
        }
    }


@router.get("/dashboard/stats")
async def get_engineer_dashboard_stats(
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """Get dashboard statistics for the engineer"""
    user, engineer = await get_engineer_user(authorization, db)
    
    if not engineer:
        raise HTTPException(status_code=404, detail="Engineer profile not found")
    
    now = datetime.utcnow()
    
    # Get all bookings for this engineer
    result = await db.execute(
        select(Booking).where(Booking.engineer_id == engineer.id)
    )
    bookings = result.scalars().all()
    
    total_bookings = len(bookings)
    upcoming_bookings = len([b for b in bookings if b.scheduled_date > now and b.status != BookingStatus.CANCELLED])
    completed_bookings = len([b for b in bookings if b.status == BookingStatus.COMPLETED])
    pending_bookings = len([b for b in bookings if b.status == BookingStatus.PENDING])
    
    # Count issues reported
    result = await db.execute(
        select(BookingStatusUpdate).where(
            and_(
                BookingStatusUpdate.booking_id.in_([b.id for b in bookings]),
                BookingStatusUpdate.issue_reported == True
            )
        )
    )
    issues = result.scalars().all()
    issues_reported = len(issues)
    
    return {
        "total_bookings": total_bookings,
        "upcoming_bookings": upcoming_bookings,
        "completed_bookings": completed_bookings,
        "pending_bookings": pending_bookings,
        "issues_reported": issues_reported
    }


@router.get("/bookings")
async def get_engineer_bookings(
    status: Optional[str] = None,
    upcoming_only: bool = False,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """Get all bookings assigned to the current engineer"""
    user, engineer = await get_engineer_user(authorization, db)
    
    if not engineer:
        raise HTTPException(status_code=404, detail="Engineer profile not found")
    
    query = select(Booking).options(
        selectinload(Booking.product),
        selectinload(Booking.change_type),
        selectinload(Booking.booker),
        selectinload(Booking.status_updates).selectinload(BookingStatusUpdate.updated_by)
    ).where(Booking.engineer_id == engineer.id)
    
    if status:
        query = query.where(Booking.status == status)
    
    if upcoming_only:
        query = query.where(Booking.scheduled_date > datetime.utcnow())
    
    query = query.order_by(Booking.scheduled_date.asc())
    
    result = await db.execute(query)
    bookings = result.scalars().all()
    
    return [{
        "id": b.id,
        "order_reference": b.order_reference,
        "customer_name": b.customer_name,
        "scheduled_date": b.scheduled_date.isoformat() if b.scheduled_date else None,
        "duration_hours": b.duration_hours,
        "status": b.status.value if hasattr(b.status, 'value') else b.status,
        "notes": b.notes,
        "product": {"id": b.product.id, "name": b.product.name} if b.product else None,
        "change_type": {"id": b.change_type.id, "name": b.change_type.name} if b.change_type else None,
        "booker": {"id": b.booker.id, "full_name": b.booker.full_name, "email": b.booker.email} if b.booker else None,
        "custom_fields_data": b.custom_fields_data,
        "engineer_attachment_url": b.engineer_attachment_url,
        "status_updates": [{
            "id": su.id,
            "previous_status": su.previous_status.value if su.previous_status else None,
            "new_status": su.new_status.value if su.new_status else None,
            "notes": su.notes,
            "issue_reported": su.issue_reported,
            "issue_description": su.issue_description,
            "created_at": su.created_at.isoformat() if su.created_at else None,
            "updated_by": {"id": su.updated_by.id, "full_name": su.updated_by.full_name} if su.updated_by else None
        } for su in (b.status_updates or [])]
    } for b in bookings]


@router.get("/bookings/{booking_id}")
async def get_engineer_booking_detail(
    booking_id: int,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """Get detailed information about a specific booking"""
    user, engineer = await get_engineer_user(authorization, db)
    
    if not engineer:
        raise HTTPException(status_code=404, detail="Engineer profile not found")
    
    result = await db.execute(
        select(Booking).options(
            selectinload(Booking.product),
            selectinload(Booking.change_type),
            selectinload(Booking.booker),
            selectinload(Booking.status_updates).selectinload(BookingStatusUpdate.updated_by)
        ).where(
            and_(
                Booking.id == booking_id,
                Booking.engineer_id == engineer.id
            )
        )
    )
    booking = result.scalar_one_or_none()
    
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found or not assigned to you")
    
    return {
        "id": booking.id,
        "order_reference": booking.order_reference,
        "customer_name": booking.customer_name,
        "scheduled_date": booking.scheduled_date.isoformat() if booking.scheduled_date else None,
        "duration_hours": booking.duration_hours,
        "status": booking.status.value if hasattr(booking.status, 'value') else booking.status,
        "notes": booking.notes,
        "product": {"id": booking.product.id, "name": booking.product.name, "description": booking.product.description} if booking.product else None,
        "change_type": {"id": booking.change_type.id, "name": booking.change_type.name, "description": booking.change_type.description} if booking.change_type else None,
        "booker": {"id": booking.booker.id, "full_name": booking.booker.full_name, "email": booking.booker.email} if booking.booker else None,
        "custom_fields_data": booking.custom_fields_data,
        "engineer_attachment_url": booking.engineer_attachment_url,
        "customer_attachment_url": booking.customer_attachment_url,
        "created_at": booking.created_at.isoformat() if booking.created_at else None,
        "updated_at": booking.updated_at.isoformat() if booking.updated_at else None,
        "status_updates": [{
            "id": su.id,
            "previous_status": su.previous_status.value if su.previous_status else None,
            "new_status": su.new_status.value if su.new_status else None,
            "notes": su.notes,
            "issue_reported": su.issue_reported,
            "issue_description": su.issue_description,
            "created_at": su.created_at.isoformat() if su.created_at else None,
            "updated_by": {"id": su.updated_by.id, "full_name": su.updated_by.full_name} if su.updated_by else None
        } for su in (booking.status_updates or [])]
    }


@router.post("/bookings/{booking_id}/status")
async def update_booking_status(
    booking_id: int,
    status_update: BookingStatusUpdateCreate,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """Update the status of a booking (mark as complete, report issues, etc.)"""
    user, engineer = await get_engineer_user(authorization, db)
    
    if not engineer:
        raise HTTPException(status_code=404, detail="Engineer profile not found")
    
    # Get the booking
    result = await db.execute(
        select(Booking).where(
            and_(
                Booking.id == booking_id,
                Booking.engineer_id == engineer.id
            )
        )
    )
    booking = result.scalar_one_or_none()
    
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found or not assigned to you")
    
    # Create status update record
    previous_status = booking.status
    
    status_update_record = BookingStatusUpdate(
        booking_id=booking_id,
        updated_by_id=user.id,
        previous_status=previous_status,
        new_status=status_update.new_status,
        notes=status_update.notes,
        issue_reported=status_update.issue_reported,
        issue_description=status_update.issue_description
    )
    db.add(status_update_record)
    
    # Update the booking status
    booking.status = status_update.new_status
    booking.updated_at = datetime.utcnow()
    
    # If an issue is being reported, update the booking's issue fields
    if status_update.issue_reported and status_update.issue_description:
        booking.issue_description = status_update.issue_description
        booking.issue_reported_at = datetime.utcnow()
        booking.issue_resolved = False
    
    await db.commit()
    await db.refresh(status_update_record)
    
    return {
        "id": status_update_record.id,
        "booking_id": status_update_record.booking_id,
        "previous_status": previous_status.value if previous_status else None,
        "new_status": status_update_record.new_status.value,
        "notes": status_update_record.notes,
        "issue_reported": status_update_record.issue_reported,
        "issue_description": status_update_record.issue_description,
        "created_at": status_update_record.created_at.isoformat()
    }


# Unavailability Management
@router.get("/unavailability")
async def get_engineer_unavailability(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """Get unavailability entries for the current engineer"""
    user, engineer = await get_engineer_user(authorization, db)
    
    if not engineer:
        raise HTTPException(status_code=404, detail="Engineer profile not found")
    
    query = select(EngineerUnavailability).options(
        selectinload(EngineerUnavailability.created_by)
    ).where(EngineerUnavailability.engineer_id == engineer.id)
    
    if start_date:
        query = query.where(EngineerUnavailability.end_datetime >= datetime.fromisoformat(start_date))
    if end_date:
        query = query.where(EngineerUnavailability.start_datetime <= datetime.fromisoformat(end_date))
    
    query = query.order_by(EngineerUnavailability.start_datetime.asc())
    
    result = await db.execute(query)
    entries = result.scalars().all()
    
    return [{
        "id": e.id,
        "engineer_id": e.engineer_id,
        "start_datetime": e.start_datetime.isoformat(),
        "end_datetime": e.end_datetime.isoformat(),
        "reason": e.reason,
        "is_all_day": e.is_all_day,
        "created_by": {"id": e.created_by.id, "full_name": e.created_by.full_name} if e.created_by else None,
        "created_at": e.created_at.isoformat()
    } for e in entries]


@router.post("/unavailability")
async def create_engineer_unavailability(
    unavailability: EngineerUnavailabilityCreate,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """Create an unavailability entry for the current engineer"""
    user, engineer = await get_engineer_user(authorization, db)
    
    if not engineer:
        raise HTTPException(status_code=404, detail="Engineer profile not found")
    
    # Engineers can only mark themselves unavailable
    if unavailability.engineer_id != engineer.id and user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="You can only mark yourself as unavailable")
    
    # Validate dates
    if unavailability.end_datetime <= unavailability.start_datetime:
        raise HTTPException(status_code=400, detail="End datetime must be after start datetime")
    
    entry = EngineerUnavailability(
        engineer_id=unavailability.engineer_id,
        start_datetime=unavailability.start_datetime,
        end_datetime=unavailability.end_datetime,
        reason=unavailability.reason,
        is_all_day=unavailability.is_all_day,
        created_by_id=user.id
    )
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    
    return {
        "id": entry.id,
        "engineer_id": entry.engineer_id,
        "start_datetime": entry.start_datetime.isoformat(),
        "end_datetime": entry.end_datetime.isoformat(),
        "reason": entry.reason,
        "is_all_day": entry.is_all_day,
        "created_at": entry.created_at.isoformat()
    }


@router.delete("/unavailability/{entry_id}")
async def delete_engineer_unavailability(
    entry_id: int,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """Delete an unavailability entry"""
    user, engineer = await get_engineer_user(authorization, db)
    
    if not engineer:
        raise HTTPException(status_code=404, detail="Engineer profile not found")
    
    result = await db.execute(
        select(EngineerUnavailability).where(EngineerUnavailability.id == entry_id)
    )
    entry = result.scalar_one_or_none()
    
    if not entry:
        raise HTTPException(status_code=404, detail="Unavailability entry not found")
    
    # Engineers can only delete their own entries, admins can delete any
    if entry.engineer_id != engineer.id and user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="You can only delete your own unavailability entries")
    
    await db.delete(entry)
    await db.commit()
    
    return {"message": "Unavailability entry deleted successfully"}
