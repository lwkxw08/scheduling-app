from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload
from datetime import datetime, timedelta
from typing import List, Optional

from app.database import get_db
from app.models.database_models import (
    Booking, BookingStatus, Engineer, User, SystemConfig, Fee, Product, 
    ExpediteRequest, ExpediteRequestStatus, TemplateType,
    FeeProductAssignment, FeeChangeTypeAssignment, BookingFee, BookingFeeStatus, FeeApplyMode,
    BankHoliday
)
from app.schemas.schemas import BookingCreate, BookingUpdate, BookingResponse, ExpediteRequestCreate, ExpediteRequestResponse
from app.services.auth import decode_access_token
from app.services import microsoft_graph
from app.services.availability import check_specific_slot_availability
from app.services.email_service import send_booking_email, is_smtp_configured

router = APIRouter(prefix="/bookings", tags=["Bookings"])


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


async def get_admin_token(db: AsyncSession) -> Optional[str]:
    result = await db.execute(
        select(User).where(User.role == "admin", User.microsoft_access_token.isnot(None))
    )
    admin = result.scalar_one_or_none()
    if admin and admin.microsoft_access_token:
        return admin.microsoft_access_token
    return None


async def get_config_value(db: AsyncSession, key: str, default: str = "") -> str:
    result = await db.execute(select(SystemConfig).where(SystemConfig.key == key))
    config = result.scalar_one_or_none()
    return config.value if config else default


async def calculate_fees(
    db: AsyncSession,
    booking: Booking,
    is_expedited: bool = False,
    is_late_change: bool = False
) -> tuple:
    expedite_fee = 0.0
    cancellation_fee = 0.0
    
    if is_expedited:
        result = await db.execute(
            select(Fee).where(Fee.fee_type == "expedite", Fee.is_active == True)
        )
        fee = result.scalar_one_or_none()
        if fee:
            expedite_fee = fee.amount
    
    if is_late_change:
        result = await db.execute(
            select(Fee).where(Fee.fee_type == "late_change", Fee.is_active == True)
        )
        fee = result.scalar_one_or_none()
        if fee:
            cancellation_fee = fee.amount
    
    return expedite_fee, cancellation_fee


def is_outside_working_hours(scheduled_time: datetime, start_time: str, end_time: str) -> bool:
    """Check if the scheduled time is outside the specified working hours"""
    if not start_time or not end_time:
        return False
    
    try:
        start_hour, start_min = map(int, start_time.split(':'))
        end_hour, end_min = map(int, end_time.split(':'))
        
        booking_hour = scheduled_time.hour
        booking_min = scheduled_time.minute
        
        # Convert to minutes for easier comparison
        booking_minutes = booking_hour * 60 + booking_min
        start_minutes = start_hour * 60 + start_min
        end_minutes = end_hour * 60 + end_min
        
        # Outside hours if before start or after end
        return booking_minutes < start_minutes or booking_minutes >= end_minutes
    except (ValueError, AttributeError):
        return False


async def apply_fees_to_booking(
    db: AsyncSession,
    booking_id: int,
    product_id: int,
    change_type_id: int,
    scheduled_date: datetime = None
) -> List[BookingFee]:
    """
    Apply fees to a booking based on product and change type assignments,
    as well as time-based conditions (weekends, bank holidays, out-of-hours).
    Returns list of BookingFee objects created.
    """
    applied_fees = []
    
    # Get all active fees with their assignments
    result = await db.execute(
        select(Fee).where(Fee.is_active == True)
        .options(
            selectinload(Fee.product_assignments),
            selectinload(Fee.change_type_assignments)
        )
    )
    fees = result.scalars().all()
    
    # Get bank holidays for checking
    bank_holidays = []
    if scheduled_date:
        holidays_result = await db.execute(select(BankHoliday))
        bank_holidays = [h.date.date() for h in holidays_result.scalars().all()]
    
    for fee in fees:
        should_apply = False
        
        # Check if fee applies to this product
        product_ids = [a.product_id for a in fee.product_assignments]
        if product_id in product_ids:
            should_apply = True
        
        # Check if fee applies to this change type
        change_type_ids = [a.change_type_id for a in fee.change_type_assignments]
        if change_type_id in change_type_ids:
            should_apply = True
        
        # Check time-based conditions (only if scheduled_date is provided)
        if scheduled_date:
            # Check weekend condition
            if fee.apply_on_weekends and scheduled_date.weekday() >= 5:  # Saturday=5, Sunday=6
                should_apply = True
            
            # Check bank holiday condition
            if fee.apply_on_bank_holidays and scheduled_date.date() in bank_holidays:
                should_apply = True
            
            # Check out-of-hours condition
            if fee.apply_outside_hours and is_outside_working_hours(
                scheduled_date, fee.outside_hours_start, fee.outside_hours_end
            ):
                should_apply = True
        
        if should_apply:
            # Determine status based on apply_mode
            fee_status = BookingFeeStatus.APPROVED
            if fee.apply_mode == FeeApplyMode.APPROVAL:
                fee_status = BookingFeeStatus.PENDING
            
            booking_fee = BookingFee(
                booking_id=booking_id,
                fee_id=fee.id,
                amount=fee.amount,
                status=fee_status
            )
            db.add(booking_fee)
            applied_fees.append(booking_fee)
    
    if applied_fees:
        await db.commit()
    
    return applied_fees


@router.post("/", response_model=BookingResponse)
async def create_booking(
    booking_data: BookingCreate,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    user = await get_current_user(authorization, db)
    
    # Check booking settings (skip for admins)
    if user.role != "admin":
        # Check booking advance limit
        advance_limit = await get_config_value(db, "booking_advance_limit_days", "0")
        if advance_limit and advance_limit != "0":
            try:
                max_days = int(advance_limit)
                if max_days > 0:
                    max_date = datetime.now() + timedelta(days=max_days)
                    if booking_data.scheduled_date > max_date:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Bookings cannot be made more than {max_days} days in advance"
                        )
            except ValueError:
                pass  # Invalid config value, skip validation
        
        # Check minimum booking notice
        min_notice = await get_config_value(db, "min_booking_notice_hours", "0")
        if min_notice and min_notice != "0":
            try:
                min_hours = int(min_notice)
                if min_hours > 0:
                    min_date = datetime.now() + timedelta(hours=min_hours)
                    if booking_data.scheduled_date < min_date:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Bookings must be made at least {min_hours} hours in advance"
                        )
            except ValueError:
                pass
    
    # Check maximum booking duration (applies to all users)
    max_duration = await get_config_value(db, "max_booking_duration_hours", "0")
    if max_duration and max_duration != "0":
        try:
            max_hours = float(max_duration)
            if max_hours > 0 and booking_data.duration_hours > max_hours:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Booking duration cannot exceed {max_hours} hours"
                )
        except ValueError:
            pass
    
    result = await db.execute(
        select(Engineer)
        .where(Engineer.id == booking_data.engineer_id)
        .options(selectinload(Engineer.user))
    )
    engineer = result.scalar_one_or_none()
    if not engineer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Engineer not found")
    
    admin_token = await get_admin_token(db)
    
    is_available = await check_specific_slot_availability(
        engineer,
        booking_data.scheduled_date,
        booking_data.duration_hours,
        admin_token
    )
    
    if not is_available:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Selected time slot is not available"
        )
    
    expedite_fee, _ = await calculate_fees(db, None, booking_data.is_expedited, False)
    
    new_booking = Booking(
        order_reference=booking_data.order_reference,
        customer_name=booking_data.customer_name,
        booker_id=user.id,
        engineer_id=booking_data.engineer_id,
        product_id=booking_data.product_id,
        change_type_id=booking_data.change_type_id,
        scheduled_date=booking_data.scheduled_date,
        duration_hours=booking_data.duration_hours,
        custom_fields_data=booking_data.custom_fields_data,
        notes=booking_data.notes,
        additional_emails=booking_data.additional_emails,
        expedite_fee=expedite_fee,
        status=BookingStatus.PENDING
    )
    
    db.add(new_booking)
    await db.commit()
    await db.refresh(new_booking)
    
    # Apply fees based on product, change type, and time-based conditions
    await apply_fees_to_booking(
        db,
        new_booking.id,
        booking_data.product_id,
        booking_data.change_type_id,
        booking_data.scheduled_date
    )
    
    if admin_token and engineer.calendar_email:
        end_time = booking_data.scheduled_date + timedelta(hours=booking_data.duration_hours)
        event_body = f"""
        <h2>Booking Details</h2>
        <p><strong>Order Reference:</strong> {booking_data.order_reference}</p>
        <p><strong>Customer:</strong> {booking_data.customer_name}</p>
        <p><strong>Duration:</strong> {booking_data.duration_hours} hours</p>
        <p><strong>Notes:</strong> {booking_data.notes or 'N/A'}</p>
        """
        
        try:
            event = await microsoft_graph.create_calendar_event(
                admin_token,
                engineer.calendar_email,
                f"Booking: {booking_data.order_reference} - {booking_data.customer_name}",
                booking_data.scheduled_date,
                end_time,
                event_body,
                [user.email]
            )
            
            if event:
                new_booking.outlook_event_id = event.get("id")
                new_booking.status = BookingStatus.CONFIRMED
                await db.commit()
        except Exception:
            pass
        
        try:
            confirmation_body = f"""
            <h2>Booking Confirmation</h2>
            <p>Your booking has been confirmed.</p>
            <p><strong>Order Reference:</strong> {booking_data.order_reference}</p>
            <p><strong>Customer:</strong> {booking_data.customer_name}</p>
            <p><strong>Date:</strong> {booking_data.scheduled_date.strftime('%Y-%m-%d %H:%M')}</p>
            <p><strong>Duration:</strong> {booking_data.duration_hours} hours</p>
            <p><strong>Engineer:</strong> {engineer.user.full_name if engineer.user else 'TBD'}</p>
            """
            
            await microsoft_graph.send_email(
                admin_token,
                [user.email],
                f"Booking Confirmation - {booking_data.order_reference}",
                confirmation_body
            )
            
            if engineer.user:
                await microsoft_graph.send_email(
                    admin_token,
                    [engineer.calendar_email],
                    f"New Booking Assignment - {booking_data.order_reference}",
                    confirmation_body
                )
        except Exception:
            pass
    
    result = await db.execute(
        select(Booking)
        .where(Booking.id == new_booking.id)
        .options(
            selectinload(Booking.engineer).selectinload(Engineer.user),
            selectinload(Booking.engineer).selectinload(Engineer.schedules),
            selectinload(Booking.product),
            selectinload(Booking.change_type)
        )
    )
    booking = result.scalar_one()
    
    additional_emails_list = []
    if booking_data.additional_emails:
        if isinstance(booking_data.additional_emails, list):
            additional_emails_list = [e.strip() for e in booking_data.additional_emails if e and e.strip()]
        elif isinstance(booking_data.additional_emails, str):
            additional_emails_list = [e.strip() for e in booking_data.additional_emails.split(',') if e.strip()]
    
    try:
        await send_booking_email(
            db,
            booking,
            user.full_name,
            user.email,
            TemplateType.CONFIRMATION,
            additional_emails_list
        )
    except Exception as e:
        print(f"Email sending error: {str(e)}")
    
    return BookingResponse.model_validate(booking)


@router.get("/", response_model=List[BookingResponse])
async def get_bookings(
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    user = await get_current_user(authorization, db)
    
    if user.role.value == "admin":
        query = select(Booking).options(
            selectinload(Booking.engineer).selectinload(Engineer.user),
            selectinload(Booking.engineer).selectinload(Engineer.schedules),
            selectinload(Booking.product),
            selectinload(Booking.change_type)
        ).order_by(Booking.scheduled_date.desc())
    else:
        query = select(Booking).where(Booking.booker_id == user.id).options(
            selectinload(Booking.engineer).selectinload(Engineer.user),
            selectinload(Booking.engineer).selectinload(Engineer.schedules),
            selectinload(Booking.product),
            selectinload(Booking.change_type)
        ).order_by(Booking.scheduled_date.desc())
    
    result = await db.execute(query)
    bookings = result.scalars().all()
    
    return [BookingResponse.model_validate(b) for b in bookings]


@router.get("/{booking_id}", response_model=BookingResponse)
async def get_booking(
    booking_id: int,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    user = await get_current_user(authorization, db)
    
    result = await db.execute(
        select(Booking)
        .where(Booking.id == booking_id)
        .options(
            selectinload(Booking.engineer).selectinload(Engineer.user),
            selectinload(Booking.engineer).selectinload(Engineer.schedules),
            selectinload(Booking.product),
            selectinload(Booking.change_type)
        )
    )
    booking = result.scalar_one_or_none()
    
    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")
    
    if user.role.value != "admin" and booking.booker_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    
    return BookingResponse.model_validate(booking)


@router.patch("/{booking_id}", response_model=BookingResponse)
async def update_booking(
    booking_id: int,
    update_data: BookingUpdate,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    user = await get_current_user(authorization, db)
    
        result = await db.execute(
            select(Booking)
            .where(Booking.id == booking_id)
            .options(
                selectinload(Booking.engineer).selectinload(Engineer.user),
                selectinload(Booking.product),
                selectinload(Booking.change_type)
            )
        )
        booking = result.scalar_one_or_none()
    
        if not booking:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")
    
        if user.role.value != "admin" and booking.booker_id != user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    
        if booking.status == BookingStatus.CANCELLED:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot update cancelled booking")
    
        # Use change type-specific amendment notice if set, otherwise use global setting
        if booking.change_type and booking.change_type.amendment_notice_hours is not None:
        deadline_hours = booking.change_type.amendment_notice_hours
    else:
        deadline_hours = int(await get_config_value(db, "amendment_deadline_hours", "24"))
    deadline = booking.scheduled_date - timedelta(hours=deadline_hours)
    
    is_late_change = datetime.utcnow() > deadline
    
    if is_late_change and user.role.value != "admin":
        _, late_fee = await calculate_fees(db, booking, False, True)
        booking.cancellation_fee += late_fee
    
    if update_data.scheduled_date:
        booking.scheduled_date = update_data.scheduled_date
    if update_data.duration_hours:
        booking.duration_hours = update_data.duration_hours
    if update_data.notes is not None:
        booking.notes = update_data.notes
    if update_data.custom_fields_data is not None:
        booking.custom_fields_data = update_data.custom_fields_data
    if update_data.additional_emails is not None:
        booking.additional_emails = update_data.additional_emails
    if update_data.engineer_id is not None:
        # Verify the new engineer exists
        result = await db.execute(
            select(Engineer).where(Engineer.id == update_data.engineer_id)
        )
        new_engineer = result.scalar_one_or_none()
        if not new_engineer:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Engineer not found")
        booking.engineer_id = update_data.engineer_id
    
    # Handle engineer notes
    if update_data.engineer_notes is not None:
        booking.engineer_notes = update_data.engineer_notes
    
    # Handle issue description - set issue_reported_at when first reported
    if update_data.issue_description is not None:
        if update_data.issue_description and not booking.issue_description:
            # First time reporting an issue
            booking.issue_reported_at = datetime.utcnow()
        booking.issue_description = update_data.issue_description
    
    # Handle issue resolved status
    if update_data.issue_resolved is not None:
        booking.issue_resolved = update_data.issue_resolved
    
    admin_token = await get_admin_token(db)
    if admin_token and booking.outlook_event_id and booking.engineer.calendar_email:
        try:
            end_time = booking.scheduled_date + timedelta(hours=booking.duration_hours)
            await microsoft_graph.update_calendar_event(
                admin_token,
                booking.engineer.calendar_email,
                booking.outlook_event_id,
                start_datetime=booking.scheduled_date,
                end_datetime=end_time
            )
        except Exception:
            pass
    
    await db.commit()
    await db.refresh(booking)
    
    result = await db.execute(
        select(Booking)
        .where(Booking.id == booking.id)
        .options(
            selectinload(Booking.engineer).selectinload(Engineer.user),
            selectinload(Booking.engineer).selectinload(Engineer.schedules),
            selectinload(Booking.product),
            selectinload(Booking.change_type)
        )
    )
    booking = result.scalar_one()
    
    additional_emails_list = []
    if booking.additional_emails:
        if isinstance(booking.additional_emails, list):
            additional_emails_list = [e.strip() for e in booking.additional_emails if e and e.strip()]
        elif isinstance(booking.additional_emails, str):
            additional_emails_list = [e.strip() for e in booking.additional_emails.split(',') if e.strip()]
    
    try:
        await send_booking_email(
            db,
            booking,
            user.full_name,
            user.email,
            TemplateType.AMENDMENT,
            additional_emails_list
        )
    except Exception as e:
        print(f"Amendment email error: {str(e)}")
    
    return BookingResponse.model_validate(booking)


@router.delete("/{booking_id}")
async def cancel_booking(
    booking_id: int,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    user = await get_current_user(authorization, db)
    
    result = await db.execute(
        select(Booking)
        .where(Booking.id == booking_id)
        .options(
            selectinload(Booking.engineer).selectinload(Engineer.user),
            selectinload(Booking.product),
            selectinload(Booking.change_type)
        )
    )
    booking = result.scalar_one_or_none()
    
    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")
    
    if user.role.value != "admin" and booking.booker_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    
    if booking.status == BookingStatus.CANCELLED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Booking already cancelled")
    
    # Use change type-specific cancellation notice if set, otherwise use global setting
    if booking.change_type and booking.change_type.cancellation_notice_hours is not None:
        deadline_hours = booking.change_type.cancellation_notice_hours
    else:
        deadline_hours = int(await get_config_value(db, "cancellation_deadline_hours", "24"))
    deadline = booking.scheduled_date - timedelta(hours=deadline_hours)
    
    is_late_cancellation = datetime.utcnow() > deadline
    
    if is_late_cancellation and user.role.value != "admin":
        result = await db.execute(
            select(Fee).where(Fee.fee_type == "cancellation", Fee.is_active == True)
        )
        fee = result.scalar_one_or_none()
        if fee:
            booking.cancellation_fee = fee.amount
    
    booking.status = BookingStatus.CANCELLED
    
    admin_token = await get_admin_token(db)
    if admin_token and booking.outlook_event_id and booking.engineer.calendar_email:
        try:
            await microsoft_graph.delete_calendar_event(
                admin_token,
                booking.engineer.calendar_email,
                booking.outlook_event_id
            )
        except Exception:
            pass
    
    additional_emails_list = []
    if booking.additional_emails:
        if isinstance(booking.additional_emails, list):
            additional_emails_list = [e.strip() for e in booking.additional_emails if e and e.strip()]
        elif isinstance(booking.additional_emails, str):
            additional_emails_list = [e.strip() for e in booking.additional_emails.split(',') if e.strip()]
    
    try:
        await send_booking_email(
            db,
            booking,
            user.full_name,
            user.email,
            TemplateType.CANCELLATION,
            additional_emails_list
        )
    except Exception as e:
        print(f"Cancellation email error: {str(e)}")
    
    await db.commit()
    
    return {
        "message": "Booking cancelled successfully",
        "cancellation_fee": booking.cancellation_fee
    }


@router.post("/expedite-request", response_model=ExpediteRequestResponse)
async def create_expedite_request(
    request_data: ExpediteRequestCreate,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """Create an expedite request when no availability exists for the requested date/time"""
    user = await get_current_user(authorization, db)
    
    # Get the product to retrieve the expedite fee
    result = await db.execute(select(Product).where(Product.id == request_data.product_id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    
    expedite_fee = product.expedite_fee or 0.0
    
    # Create the expedite request
    expedite_request = ExpediteRequest(
        requester_id=user.id,
        product_id=request_data.product_id,
        change_type_id=request_data.change_type_id,
        order_reference=request_data.order_reference,
        customer_name=request_data.customer_name,
        requested_date=request_data.requested_date,
        duration_hours=request_data.duration_hours,
        custom_fields_data=request_data.custom_fields_data,
        notes=request_data.notes,
        additional_emails=request_data.additional_emails,
        engineer_attachment_url=request_data.engineer_attachment_url,
        customer_attachment_url=request_data.customer_attachment_url,
        expedite_fee=expedite_fee,
        fee_acknowledged=request_data.fee_acknowledged,
        status=ExpediteRequestStatus.PENDING
    )
    
    db.add(expedite_request)
    await db.commit()
    await db.refresh(expedite_request)
    
    # Reload with relationships
    result = await db.execute(
        select(ExpediteRequest)
        .options(
            selectinload(ExpediteRequest.requester),
            selectinload(ExpediteRequest.product),
            selectinload(ExpediteRequest.change_type)
        )
        .where(ExpediteRequest.id == expedite_request.id)
    )
    expedite_request = result.scalar_one()
    
    return ExpediteRequestResponse.model_validate(expedite_request)


@router.get("/expedite-requests/my", response_model=List[ExpediteRequestResponse])
async def get_my_expedite_requests(
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """Get the current user's expedite requests"""
    user = await get_current_user(authorization, db)
    
    result = await db.execute(
        select(ExpediteRequest)
        .options(
            selectinload(ExpediteRequest.requester),
            selectinload(ExpediteRequest.product),
            selectinload(ExpediteRequest.change_type),
            selectinload(ExpediteRequest.assigned_engineer).selectinload(Engineer.user)
        )
        .where(ExpediteRequest.requester_id == user.id)
        .order_by(ExpediteRequest.created_at.desc())
    )
    requests = result.scalars().all()
    return [ExpediteRequestResponse.model_validate(r) for r in requests]


@router.get("/product/{product_id}/expedite-fee")
async def get_product_expedite_fee(
    product_id: int,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """Get the expedite fee for a specific product"""
    await get_current_user(authorization, db)
    
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    
    return {
        "product_id": product.id,
        "product_name": product.name,
        "expedite_fee": product.expedite_fee or 0.0
    }


@router.get("/booking-settings")
async def get_booking_settings(
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """Get public booking settings like advance limit"""
    await get_current_user(authorization, db)
    
    advance_limit = await get_config_value(db, "booking_advance_limit_days", "0")
    
    return {
        "booking_advance_limit_days": int(advance_limit) if advance_limit and advance_limit != "0" else 0
    }
