from fastapi import APIRouter, Depends, HTTPException, status, Header, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from sqlalchemy.exc import IntegrityError
from typing import List
from datetime import datetime, timedelta
import os
import uuid
import aiofiles

from app.database import get_db
from app.models.database_models import (
    User, UserRole, Engineer, Product, ChangeType, EngineerSkill,
    CustomField, SystemConfig, Fee, Booking, BookingStatus, EngineerSchedule,
    EmailTemplate, CalendarEventTemplate, TemplateType,
    RosterPattern, RosterPhase, EngineerRosterAssignment,
    ExpediteRequest, ExpediteRequestStatus, EngineerUnavailability, BookingStatusUpdate,
    FeeProductAssignment, FeeChangeTypeAssignment, FeeApplyMode, BookingFee, BookingFeeStatus,
    EmailRule, EmailRuleSentLog, EmailRuleTriggerType, EmailRuleRecipientType,
    BankHoliday
)
from app.schemas.schemas import (
    ProductCreate, ProductUpdate, ProductResponse, ChangeTypeCreate, ChangeTypeResponse,
    EngineerCreate, EngineerResponse, EngineerSkillCreate, EngineerSkillResponse,
    CustomFieldCreate, CustomFieldResponse, FeeCreate, FeeUpdate, FeeResponse,
    FeeApplyMode as FeeApplyModeSchema, BookingFeeResponse, BookingFeeWaive, BookingFeeApprove,
    SystemConfigUpdate, SystemConfigResponse, DashboardStats, UserResponse,
    EngineerScheduleCreate, EngineerScheduleResponse, EngineerScheduleUpdate,
    EmailTemplateCreate, EmailTemplateResponse, CalendarEventTemplateCreate,
    CalendarEventTemplateResponse, TemplatePlaceholders,
    RosterPatternCreate, RosterPatternUpdate, RosterPatternResponse,
    RosterPhaseCreate, RosterPhaseResponse, RosterPatternListResponse,
    EngineerRosterAssignmentCreate, EngineerRosterAssignmentResponse,
    ExpediteRequestCreate, ExpediteRequestApprove, ExpediteRequestReject, ExpediteRequestResponse,
    EngineerUnavailabilityCreate, EngineerUnavailabilityResponse,
    EmailRuleCreate, EmailRuleUpdate, EmailRuleResponse, EmailRuleSentLogResponse,
    BankHolidayCreate, BankHolidayResponse
)
from app.services.auth import decode_access_token
from app.routers.bookings import apply_fees_to_booking

router = APIRouter(prefix="/admin", tags=["Admin"])


async def get_admin_user(authorization: str, db: AsyncSession) -> User:
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
    
    if user.role != UserRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    
    return user


@router.get("/dashboard/stats", response_model=DashboardStats)
async def get_dashboard_stats(
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    await get_admin_user(authorization, db)
    
    # Only count future bookings (scheduled_date >= today) and exclude cancelled
    today = datetime.utcnow().date()
    
    total_bookings = await db.execute(
        select(func.count(Booking.id)).where(
            Booking.scheduled_date >= today,
            Booking.status != BookingStatus.CANCELLED
        )
    )
    pending_bookings = await db.execute(
        select(func.count(Booking.id)).where(
            Booking.status == BookingStatus.PENDING,
            Booking.scheduled_date >= today
        )
    )
    confirmed_bookings = await db.execute(
        select(func.count(Booking.id)).where(
            Booking.status == BookingStatus.CONFIRMED,
            Booking.scheduled_date >= today
        )
    )
    total_engineers = await db.execute(select(func.count(Engineer.id)))
    available_engineers = await db.execute(
        select(func.count(Engineer.id)).where(Engineer.is_available == True)
    )
    pending_expedite_requests = await db.execute(
        select(func.count(ExpediteRequest.id)).where(ExpediteRequest.status == ExpediteRequestStatus.PENDING)
    )
    
    return DashboardStats(
        total_bookings=total_bookings.scalar() or 0,
        pending_bookings=pending_bookings.scalar() or 0,
        confirmed_bookings=confirmed_bookings.scalar() or 0,
        total_engineers=total_engineers.scalar() or 0,
        available_engineers=available_engineers.scalar() or 0,
        pending_expedite_requests=pending_expedite_requests.scalar() or 0
    )


@router.get("/users", response_model=List[UserResponse])
async def get_all_users(
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    await get_admin_user(authorization, db)
    
    result = await db.execute(select(User).order_by(User.created_at.desc()))
    users = result.scalars().all()
    return [UserResponse.model_validate(u) for u in users]


@router.patch("/users/{user_id}/role")
async def update_user_role(
    user_id: int,
    role: str,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    await get_admin_user(authorization, db)
    
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    
    try:
        user.role = UserRole(role)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid role")
    
    await db.commit()
    return {"message": "Role updated successfully"}


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """Delete a user account. Cannot delete yourself or users with active bookings."""
    admin_user = await get_admin_user(authorization, db)
    
    if admin_user.id == user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account"
        )
    
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    
    # Check if user has any active bookings
    active_bookings = await db.execute(
        select(func.count(Booking.id)).where(
            Booking.booker_id == user_id,
            Booking.status.in_([BookingStatus.PENDING, BookingStatus.CONFIRMED])
        )
    )
    active_count = active_bookings.scalar()
    if active_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot delete user with {active_count} active booking(s). Cancel or complete bookings first."
        )
    
    # Check if user is an engineer with active bookings
    if user.engineer_profile:
        engineer_bookings = await db.execute(
            select(func.count(Booking.id)).where(
                Booking.engineer_id == user.engineer_profile.id,
                Booking.status.in_([BookingStatus.PENDING, BookingStatus.CONFIRMED])
            )
        )
        engineer_booking_count = engineer_bookings.scalar()
        if engineer_booking_count > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot delete engineer with {engineer_booking_count} active booking(s) assigned."
            )
    
    await db.delete(user)
    await db.commit()
    return {"message": f"User {user.email} deleted successfully"}


@router.get("/reports/user-activity")
async def get_user_activity_report(
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """Get user activity report showing last login for all users."""
    await get_admin_user(authorization, db)
    
    result = await db.execute(
        select(User).options(selectinload(User.engineer_profile)).order_by(User.last_login_at.desc().nullslast())
    )
    users = result.scalars().all()
    
    report_data = []
    for user in users:
        report_data.append({
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role.value,
            "is_active": user.is_active,
            "is_engineer": user.engineer_profile is not None,
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
            "days_since_login": (
                (datetime.utcnow() - user.last_login_at).days 
                if user.last_login_at else None
            )
        })
    
    return report_data


@router.post("/products", response_model=ProductResponse)
async def create_product(
    product_data: ProductCreate,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    await get_admin_user(authorization, db)
    
    product = Product(
        name=product_data.name,
        description=product_data.description,
        expedite_fee=product_data.expedite_fee or 0.0,
        expedite_contact_emails=product_data.expedite_contact_emails
    )
    db.add(product)
    try:
        await db.commit()
        await db.refresh(product)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"A product with the name '{product_data.name}' already exists"
        )
    return ProductResponse.model_validate(product)


@router.get("/products", response_model=List[ProductResponse])
async def get_products(
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Product).where(Product.is_active == True))
    products = result.scalars().all()
    return [ProductResponse.model_validate(p) for p in products]


@router.patch("/products/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: int,
    product_data: ProductUpdate,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    await get_admin_user(authorization, db)
    
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    
    if product_data.name is not None:
        product.name = product_data.name
    if product_data.description is not None:
        product.description = product_data.description
    if product_data.expedite_fee is not None:
        product.expedite_fee = product_data.expedite_fee
    if product_data.expedite_contact_emails is not None:
        product.expedite_contact_emails = product_data.expedite_contact_emails
    
    await db.commit()
    await db.refresh(product)
    return ProductResponse.model_validate(product)


@router.delete("/products/{product_id}")
async def delete_product(
    product_id: int,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    await get_admin_user(authorization, db)
    
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    
    product.is_active = False
    await db.commit()
    return {"message": "Product deleted successfully"}


@router.post("/change-types", response_model=ChangeTypeResponse)
async def create_change_type(
    change_type_data: ChangeTypeCreate,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    await get_admin_user(authorization, db)
    
    change_type = ChangeType(
        name=change_type_data.name,
        description=change_type_data.description,
        minimum_notice_hours=change_type_data.minimum_notice_hours or 0,
        cancellation_notice_hours=change_type_data.cancellation_notice_hours,
        amendment_notice_hours=change_type_data.amendment_notice_hours
    )
    db.add(change_type)
    try:
        await db.commit()
        await db.refresh(change_type)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"A change type with the name '{change_type_data.name}' already exists"
        )
    return ChangeTypeResponse.model_validate(change_type)


@router.get("/change-types", response_model=List[ChangeTypeResponse])
async def get_change_types(
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(ChangeType).where(ChangeType.is_active == True))
    change_types = result.scalars().all()
    return [ChangeTypeResponse.model_validate(ct) for ct in change_types]


@router.patch("/change-types/{change_type_id}", response_model=ChangeTypeResponse)
async def update_change_type(
    change_type_id: int,
    change_type_data: ChangeTypeCreate,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    await get_admin_user(authorization, db)
    
    result = await db.execute(select(ChangeType).where(ChangeType.id == change_type_id))
    change_type = result.scalar_one_or_none()
    if not change_type:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Change type not found")
    
    change_type.name = change_type_data.name
    change_type.description = change_type_data.description
    if change_type_data.minimum_notice_hours is not None:
        change_type.minimum_notice_hours = change_type_data.minimum_notice_hours
    # Allow setting to None (use global) or a specific value
    change_type.cancellation_notice_hours = change_type_data.cancellation_notice_hours
    change_type.amendment_notice_hours = change_type_data.amendment_notice_hours
    await db.commit()
    await db.refresh(change_type)
    return ChangeTypeResponse.model_validate(change_type)


@router.delete("/change-types/{change_type_id}")
async def delete_change_type(
    change_type_id: int,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    await get_admin_user(authorization, db)
    
    result = await db.execute(select(ChangeType).where(ChangeType.id == change_type_id))
    change_type = result.scalar_one_or_none()
    if not change_type:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Change type not found")
    
    change_type.is_active = False
    await db.commit()
    return {"message": "Change type deleted successfully"}


@router.post("/engineers", response_model=EngineerResponse)
async def create_engineer(
    engineer_data: EngineerCreate,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    await get_admin_user(authorization, db)
    
    result = await db.execute(select(User).where(User.id == engineer_data.user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    
    # Check if user is already an engineer
    existing_engineer = await db.execute(select(Engineer).where(Engineer.user_id == engineer_data.user_id))
    if existing_engineer.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This user is already an engineer")
    
    user.role = UserRole.ENGINEER
    
    engineer = Engineer(
        user_id=engineer_data.user_id,
        calendar_email=engineer_data.calendar_email,
        working_hours_start=engineer_data.working_hours_start,
        working_hours_end=engineer_data.working_hours_end
    )
    db.add(engineer)
    await db.commit()
    await db.refresh(engineer)
    
    result = await db.execute(
        select(Engineer).where(Engineer.id == engineer.id).options(
            selectinload(Engineer.user),
            selectinload(Engineer.skills),
            selectinload(Engineer.schedules)
        )
    )
    engineer = result.scalar_one()
    
    return EngineerResponse.model_validate(engineer)


@router.get("/engineers", response_model=List[EngineerResponse])
async def get_engineers(
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Engineer).options(
            selectinload(Engineer.user),
            selectinload(Engineer.skills),
            selectinload(Engineer.schedules)
        )
    )
    engineers = result.scalars().all()
    return [EngineerResponse.model_validate(e) for e in engineers]


@router.patch("/engineers/{engineer_id}")
async def update_engineer(
    engineer_id: int,
    calendar_email: str = None,
    is_available: bool = None,
    working_hours_start: str = None,
    working_hours_end: str = None,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    await get_admin_user(authorization, db)
    
    result = await db.execute(select(Engineer).where(Engineer.id == engineer_id))
    engineer = result.scalar_one_or_none()
    if not engineer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Engineer not found")
    
    if calendar_email is not None:
        engineer.calendar_email = calendar_email
    if is_available is not None:
        engineer.is_available = is_available
    if working_hours_start is not None:
        engineer.working_hours_start = working_hours_start
    if working_hours_end is not None:
        engineer.working_hours_end = working_hours_end
    
    await db.commit()
    return {"message": "Engineer updated successfully"}


@router.post("/engineers/{engineer_id}/skills", response_model=EngineerSkillResponse)
async def add_engineer_skill(
    engineer_id: int,
    skill_data: EngineerSkillCreate,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    await get_admin_user(authorization, db)
    
    result = await db.execute(select(Engineer).where(Engineer.id == engineer_id))
    engineer = result.scalar_one_or_none()
    if not engineer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Engineer not found")
    
    skill = EngineerSkill(
        engineer_id=engineer_id,
        product_id=skill_data.product_id,
        change_type_id=skill_data.change_type_id,
        proficiency_level=skill_data.proficiency_level
    )
    db.add(skill)
    await db.commit()
    await db.refresh(skill)
    
    result = await db.execute(
        select(EngineerSkill)
        .where(EngineerSkill.id == skill.id)
        .options(selectinload(EngineerSkill.product), selectinload(EngineerSkill.change_type))
    )
    skill = result.scalar_one()
    
    return EngineerSkillResponse.model_validate(skill)


@router.get("/engineers/{engineer_id}/skills", response_model=List[EngineerSkillResponse])
async def get_engineer_skills(
    engineer_id: int,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(EngineerSkill)
        .where(EngineerSkill.engineer_id == engineer_id)
        .options(selectinload(EngineerSkill.product), selectinload(EngineerSkill.change_type))
    )
    skills = result.scalars().all()
    return [EngineerSkillResponse.model_validate(s) for s in skills]


@router.delete("/engineers/{engineer_id}/skills/{skill_id}")
async def remove_engineer_skill(
    engineer_id: int,
    skill_id: int,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    await get_admin_user(authorization, db)
    
    result = await db.execute(
        select(EngineerSkill).where(
            EngineerSkill.id == skill_id,
            EngineerSkill.engineer_id == engineer_id
        )
    )
    skill = result.scalar_one_or_none()
    if not skill:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Skill not found")
    
    await db.delete(skill)
    await db.commit()
    return {"message": "Skill removed successfully"}


@router.post("/custom-fields", response_model=CustomFieldResponse)
async def create_custom_field(
    field_data: CustomFieldCreate,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    await get_admin_user(authorization, db)
    
    field = CustomField(
        name=field_data.name,
        field_type=field_data.field_type,
        is_required=field_data.is_required,
        options=field_data.options,
        display_order=field_data.display_order
    )
    db.add(field)
    try:
        await db.commit()
        await db.refresh(field)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"A custom field with the name '{field_data.name}' already exists"
        )
    return CustomFieldResponse.model_validate(field)


@router.get("/custom-fields", response_model=List[CustomFieldResponse])
async def get_custom_fields(
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(CustomField)
        .where(CustomField.is_active == True)
        .order_by(CustomField.display_order)
    )
    fields = result.scalars().all()
    return [CustomFieldResponse.model_validate(f) for f in fields]


@router.patch("/custom-fields/{field_id}")
async def update_custom_field(
    field_id: int,
    field_data: CustomFieldCreate,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    await get_admin_user(authorization, db)
    
    result = await db.execute(select(CustomField).where(CustomField.id == field_id))
    field = result.scalar_one_or_none()
    if not field:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Custom field not found")
    
    field.name = field_data.name
    field.field_type = field_data.field_type
    field.is_required = field_data.is_required
    field.options = field_data.options
    field.display_order = field_data.display_order
    
    await db.commit()
    return {"message": "Custom field updated successfully"}


@router.delete("/custom-fields/{field_id}")
async def delete_custom_field(
    field_id: int,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    await get_admin_user(authorization, db)
    
    result = await db.execute(select(CustomField).where(CustomField.id == field_id))
    field = result.scalar_one_or_none()
    if not field:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Custom field not found")
    
    field.is_active = False
    await db.commit()
    return {"message": "Custom field deleted successfully"}


@router.post("/fees", response_model=FeeResponse)
async def create_fee(
    fee_data: FeeCreate,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    await get_admin_user(authorization, db)
    
    # Convert schema enum to model enum
    apply_mode = FeeApplyMode.AUTO
    if fee_data.apply_mode == FeeApplyModeSchema.APPROVAL:
        apply_mode = FeeApplyMode.APPROVAL
    
    fee = Fee(
        name=fee_data.name,
        fee_type=fee_data.fee_type,
        amount=fee_data.amount,
        description=fee_data.description,
        apply_mode=apply_mode,
        apply_on_weekends=fee_data.apply_on_weekends,
        apply_on_bank_holidays=fee_data.apply_on_bank_holidays,
        apply_outside_hours=fee_data.apply_outside_hours,
        outside_hours_start=fee_data.outside_hours_start,
        outside_hours_end=fee_data.outside_hours_end,
        charge_per_hour=fee_data.charge_per_hour
    )
    db.add(fee)
    await db.commit()
    await db.refresh(fee)
    
    # Add product assignments
    if fee_data.product_ids:
        for product_id in fee_data.product_ids:
            assignment = FeeProductAssignment(fee_id=fee.id, product_id=product_id)
            db.add(assignment)
    
    # Add change type assignments
    if fee_data.change_type_ids:
        for change_type_id in fee_data.change_type_ids:
            assignment = FeeChangeTypeAssignment(fee_id=fee.id, change_type_id=change_type_id)
            db.add(assignment)
    
    await db.commit()
    
    # Reload with assignments
    result = await db.execute(
        select(Fee).where(Fee.id == fee.id)
        .options(selectinload(Fee.product_assignments), selectinload(Fee.change_type_assignments))
    )
    fee = result.scalar_one()
    
    return FeeResponse(
        id=fee.id,
        name=fee.name,
        fee_type=fee.fee_type,
        amount=fee.amount,
        description=fee.description,
        apply_mode=FeeApplyModeSchema(fee.apply_mode.value) if fee.apply_mode else FeeApplyModeSchema.AUTO,
        is_active=fee.is_active,
        created_at=fee.created_at,
        product_ids=[a.product_id for a in fee.product_assignments],
        change_type_ids=[a.change_type_id for a in fee.change_type_assignments],
        apply_on_weekends=fee.apply_on_weekends or False,
        apply_on_bank_holidays=fee.apply_on_bank_holidays or False,
        apply_outside_hours=fee.apply_outside_hours or False,
        outside_hours_start=fee.outside_hours_start,
        outside_hours_end=fee.outside_hours_end,
        charge_per_hour=fee.charge_per_hour or False
    )


@router.get("/fees", response_model=List[FeeResponse])
async def get_fees(
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    await get_admin_user(authorization, db)
    
    result = await db.execute(
        select(Fee).where(Fee.is_active == True)
        .options(selectinload(Fee.product_assignments), selectinload(Fee.change_type_assignments))
    )
    fees = result.scalars().all()
    
    return [
        FeeResponse(
            id=f.id,
            name=f.name,
            fee_type=f.fee_type,
            amount=f.amount,
            description=f.description,
            apply_mode=FeeApplyModeSchema(f.apply_mode.value) if f.apply_mode else FeeApplyModeSchema.AUTO,
            is_active=f.is_active,
            created_at=f.created_at,
            product_ids=[a.product_id for a in f.product_assignments],
            change_type_ids=[a.change_type_id for a in f.change_type_assignments],
            apply_on_weekends=f.apply_on_weekends or False,
            apply_on_bank_holidays=f.apply_on_bank_holidays or False,
            apply_outside_hours=f.apply_outside_hours or False,
            outside_hours_start=f.outside_hours_start,
            outside_hours_end=f.outside_hours_end,
            charge_per_hour=f.charge_per_hour or False
        )
        for f in fees
    ]


@router.patch("/fees/{fee_id}")
async def update_fee(
    fee_id: int,
    fee_data: FeeUpdate,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    await get_admin_user(authorization, db)
    
    result = await db.execute(
        select(Fee).where(Fee.id == fee_id)
        .options(selectinload(Fee.product_assignments), selectinload(Fee.change_type_assignments))
    )
    fee = result.scalar_one_or_none()
    if not fee:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fee not found")
    
    if fee_data.name is not None:
        fee.name = fee_data.name
    if fee_data.fee_type is not None:
        fee.fee_type = fee_data.fee_type
    if fee_data.amount is not None:
        fee.amount = fee_data.amount
    if fee_data.description is not None:
        fee.description = fee_data.description
    if fee_data.apply_mode is not None:
        fee.apply_mode = FeeApplyMode.APPROVAL if fee_data.apply_mode == FeeApplyModeSchema.APPROVAL else FeeApplyMode.AUTO
    
    # Update fee rule conditions
    if fee_data.apply_on_weekends is not None:
        fee.apply_on_weekends = fee_data.apply_on_weekends
    if fee_data.apply_on_bank_holidays is not None:
        fee.apply_on_bank_holidays = fee_data.apply_on_bank_holidays
    if fee_data.apply_outside_hours is not None:
        fee.apply_outside_hours = fee_data.apply_outside_hours
    if fee_data.outside_hours_start is not None:
        fee.outside_hours_start = fee_data.outside_hours_start
    if fee_data.outside_hours_end is not None:
        fee.outside_hours_end = fee_data.outside_hours_end
    if fee_data.charge_per_hour is not None:
        fee.charge_per_hour = fee_data.charge_per_hour
    
    # Update product assignments if provided
    if fee_data.product_ids is not None:
        # Remove existing assignments
        for assignment in fee.product_assignments:
            await db.delete(assignment)
        # Add new assignments
        for product_id in fee_data.product_ids:
            assignment = FeeProductAssignment(fee_id=fee.id, product_id=product_id)
            db.add(assignment)
    
    # Update change type assignments if provided
    if fee_data.change_type_ids is not None:
        # Remove existing assignments
        for assignment in fee.change_type_assignments:
            await db.delete(assignment)
        # Add new assignments
        for change_type_id in fee_data.change_type_ids:
            assignment = FeeChangeTypeAssignment(fee_id=fee.id, change_type_id=change_type_id)
            db.add(assignment)
    
    await db.commit()
    return {"message": "Fee updated successfully"}


@router.delete("/fees/{fee_id}")
async def delete_fee(
    fee_id: int,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    await get_admin_user(authorization, db)
    
    result = await db.execute(select(Fee).where(Fee.id == fee_id))
    fee = result.scalar_one_or_none()
    if not fee:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fee not found")
    
    fee.is_active = False
    await db.commit()
    return {"message": "Fee deleted successfully"}


# Booking Fee Management Endpoints
@router.get("/bookings/{booking_id}/fees", response_model=List[BookingFeeResponse])
async def get_booking_fees(
    booking_id: int,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """Get all fees applied to a booking"""
    await get_admin_user(authorization, db)
    
    result = await db.execute(
        select(BookingFee).where(BookingFee.booking_id == booking_id)
        .options(selectinload(BookingFee.fee))
    )
    booking_fees = result.scalars().all()
    
    return [
        BookingFeeResponse(
            id=bf.id,
            booking_id=bf.booking_id,
            fee_id=bf.fee_id,
            amount=bf.amount,
            status=bf.status.value,
            waived_by_id=bf.waived_by_id,
            waiver_reason=bf.waiver_reason,
            approved_by_id=bf.approved_by_id,
            created_at=bf.created_at,
            fee_name=bf.fee.name if bf.fee else None,
            fee_type=bf.fee.fee_type if bf.fee else None
        )
        for bf in booking_fees
    ]


@router.post("/bookings/{booking_id}/fees/{fee_id}/waive")
async def waive_booking_fee(
    booking_id: int,
    fee_id: int,
    waive_data: BookingFeeWaive,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """Waive a fee on a booking"""
    admin_user = await get_admin_user(authorization, db)
    
    result = await db.execute(
        select(BookingFee).where(
            BookingFee.booking_id == booking_id,
            BookingFee.fee_id == fee_id
        )
    )
    booking_fee = result.scalar_one_or_none()
    if not booking_fee:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking fee not found")
    
    booking_fee.status = BookingFeeStatus.WAIVED
    booking_fee.waived_by_id = admin_user.id
    booking_fee.waiver_reason = waive_data.waiver_reason
    
    await db.commit()
    return {"message": "Fee waived successfully"}


@router.post("/bookings/{booking_id}/fees/{fee_id}/approve")
async def approve_booking_fee(
    booking_id: int,
    fee_id: int,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """Approve a pending fee on a booking"""
    admin_user = await get_admin_user(authorization, db)
    
    result = await db.execute(
        select(BookingFee).where(
            BookingFee.booking_id == booking_id,
            BookingFee.fee_id == fee_id
        )
    )
    booking_fee = result.scalar_one_or_none()
    if not booking_fee:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking fee not found")
    
    if booking_fee.status != BookingFeeStatus.PENDING:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Fee is not pending approval")
    
    booking_fee.status = BookingFeeStatus.APPROVED
    booking_fee.approved_by_id = admin_user.id
    
    await db.commit()
    return {"message": "Fee approved successfully"}


@router.delete("/bookings/{booking_id}/fees/{booking_fee_id}")
async def remove_booking_fee(
    booking_id: int,
    booking_fee_id: int,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """Remove a fee from a booking"""
    await get_admin_user(authorization, db)
    
    result = await db.execute(
        select(BookingFee).where(
            BookingFee.id == booking_fee_id,
            BookingFee.booking_id == booking_id
        )
    )
    booking_fee = result.scalar_one_or_none()
    if not booking_fee:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking fee not found")
    
    await db.delete(booking_fee)
    await db.commit()
    return {"message": "Fee removed from booking"}


@router.get("/fees/pending-approvals")
async def get_pending_fee_approvals(
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """Get all booking fees pending admin approval"""
    await get_admin_user(authorization, db)
    
    result = await db.execute(
        select(BookingFee).where(BookingFee.status == BookingFeeStatus.PENDING)
        .options(selectinload(BookingFee.fee), selectinload(BookingFee.booking))
    )
    booking_fees = result.scalars().all()
    
    return [
        {
            "id": bf.id,
            "booking_id": bf.booking_id,
            "fee_id": bf.fee_id,
            "amount": bf.amount,
            "status": bf.status.value,
            "waived_by_id": bf.waived_by_id,
            "waiver_reason": bf.waiver_reason,
            "approved_by_id": bf.approved_by_id,
            "created_at": bf.created_at,
            "fee_name": bf.fee.name if bf.fee else None,
            "fee_type": bf.fee.fee_type if bf.fee else None,
            "order_reference": bf.booking.order_reference if bf.booking else None
        }
        for bf in booking_fees
    ]


@router.post("/booking-fees/{booking_fee_id}/approve")
async def approve_booking_fee_by_id(
    booking_fee_id: int,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """Approve a pending fee by booking_fee_id"""
    admin_user = await get_admin_user(authorization, db)
    
    result = await db.execute(
        select(BookingFee).where(BookingFee.id == booking_fee_id)
    )
    booking_fee = result.scalar_one_or_none()
    if not booking_fee:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking fee not found")
    
    if booking_fee.status != BookingFeeStatus.PENDING:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Fee is not pending approval")
    
    booking_fee.status = BookingFeeStatus.APPROVED
    booking_fee.approved_by_id = admin_user.id
    
    await db.commit()
    return {"message": "Fee approved successfully"}


@router.post("/booking-fees/{booking_fee_id}/waive")
async def waive_booking_fee_by_id(
    booking_fee_id: int,
    reason: str = None,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """Waive a fee by booking_fee_id"""
    admin_user = await get_admin_user(authorization, db)
    
    result = await db.execute(
        select(BookingFee).where(BookingFee.id == booking_fee_id)
    )
    booking_fee = result.scalar_one_or_none()
    if not booking_fee:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking fee not found")
    
    booking_fee.status = BookingFeeStatus.WAIVED
    booking_fee.waived_by_id = admin_user.id
    booking_fee.waiver_reason = reason
    
    await db.commit()
    return {"message": "Fee waived successfully"}


@router.get("/config", response_model=List[SystemConfigResponse])
async def get_system_config(
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    await get_admin_user(authorization, db)
    
    result = await db.execute(select(SystemConfig))
    configs = result.scalars().all()
    return [SystemConfigResponse.model_validate(c) for c in configs]


@router.post("/config", response_model=SystemConfigResponse)
async def set_system_config(
    config_data: SystemConfigUpdate,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    await get_admin_user(authorization, db)
    
    result = await db.execute(select(SystemConfig).where(SystemConfig.key == config_data.key))
    config = result.scalar_one_or_none()
    
    if config:
        config.value = config_data.value
        config.description = config_data.description
    else:
        config = SystemConfig(
            key=config_data.key,
            value=config_data.value,
            description=config_data.description
        )
        db.add(config)
    
    await db.commit()
    await db.refresh(config)
    return SystemConfigResponse.model_validate(config)


@router.get("/engineers/{engineer_id}/schedules", response_model=List[EngineerScheduleResponse])
async def get_engineer_schedules(
    engineer_id: int,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    await get_admin_user(authorization, db)
    
    result = await db.execute(
        select(EngineerSchedule)
        .where(EngineerSchedule.engineer_id == engineer_id)
        .order_by(EngineerSchedule.day_of_week)
    )
    schedules = result.scalars().all()
    return [EngineerScheduleResponse.model_validate(s) for s in schedules]


@router.put("/engineers/{engineer_id}/schedules", response_model=List[EngineerScheduleResponse])
async def update_engineer_schedules(
    engineer_id: int,
    schedule_data: EngineerScheduleUpdate,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """Update all schedules for an engineer (replaces existing schedules)"""
    await get_admin_user(authorization, db)
    
    result = await db.execute(select(Engineer).where(Engineer.id == engineer_id))
    engineer = result.scalar_one_or_none()
    if not engineer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Engineer not found")
    
    await db.execute(
        select(EngineerSchedule).where(EngineerSchedule.engineer_id == engineer_id)
    )
    existing = await db.execute(
        select(EngineerSchedule).where(EngineerSchedule.engineer_id == engineer_id)
    )
    for schedule in existing.scalars().all():
        await db.delete(schedule)
    
    new_schedules = []
    for sched in schedule_data.schedules:
        new_schedule = EngineerSchedule(
            engineer_id=engineer_id,
            day_of_week=sched.day_of_week,
            is_working=sched.is_working,
            start_time=sched.start_time,
            end_time=sched.end_time
        )
        db.add(new_schedule)
        new_schedules.append(new_schedule)
    
    await db.commit()
    
    for sched in new_schedules:
        await db.refresh(sched)
    
    return [EngineerScheduleResponse.model_validate(s) for s in new_schedules]


@router.post("/engineers/{engineer_id}/schedules/default")
async def create_default_schedules(
    engineer_id: int,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """Create default Mon-Fri 9-5 schedules for an engineer"""
    await get_admin_user(authorization, db)
    
    result = await db.execute(select(Engineer).where(Engineer.id == engineer_id))
    engineer = result.scalar_one_or_none()
    if not engineer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Engineer not found")
    
    existing = await db.execute(
        select(EngineerSchedule).where(EngineerSchedule.engineer_id == engineer_id)
    )
    if existing.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Engineer already has schedules. Use PUT to update."
        )
    
    day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    for day in range(7):
        is_working = day < 5
        schedule = EngineerSchedule(
            engineer_id=engineer_id,
            day_of_week=day,
            is_working=is_working,
            start_time="09:00" if is_working else "00:00",
            end_time="17:00" if is_working else "00:00"
        )
        db.add(schedule)
    
    await db.commit()
    return {"message": f"Default schedules created for engineer (Mon-Fri 9:00-17:00)"}


# Email Template Endpoints
@router.get("/templates/placeholders")
async def get_template_placeholders(
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """Get available placeholders for templates, including dynamic fee placeholders"""
    await get_admin_user(authorization, db)
    
    # Base placeholders
    base_placeholders = [
        "{{order_reference}}",
        "{{customer_name}}",
        "{{scheduled_date}}",
        "{{scheduled_time}}",
        "{{duration_hours}}",
        "{{product_name}}",
        "{{change_type}}",
        "{{engineer_name}}",
        "{{engineer_email}}",
        "{{booker_name}}",
        "{{booker_email}}",
        "{{booking_status}}",
        "{{notes}}",
        "{{booking_notes}}",
        "{{engineer_notes}}",
        "{{issue_description}}",
        "{{cancellation_fee}}",
        "{{expedite_fee}}",
        "{{total_fees}}",
    ]
    
    # Get all active fees and create dynamic placeholders
    result = await db.execute(select(Fee).where(Fee.is_active == True))
    fees = result.scalars().all()
    
    fee_placeholders = []
    for fee in fees:
        # Convert fee name to placeholder format: "Late Cancellation" -> "fee_late_cancellation"
        placeholder_name = fee.name.lower().replace(' ', '_').replace('-', '_')
        placeholder_name = ''.join(c if c.isalnum() or c == '_' else '' for c in placeholder_name)
        fee_placeholders.append(f"{{{{fee_{placeholder_name}}}}}")
    
    return {
        "booking_fields": base_placeholders + fee_placeholders,
        "fee_placeholders": fee_placeholders
    }


@router.post("/email-templates", response_model=EmailTemplateResponse)
async def create_email_template(
    template_data: EmailTemplateCreate,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    await get_admin_user(authorization, db)
    
    if template_data.is_default:
        existing_default = await db.execute(
            select(EmailTemplate).where(
                EmailTemplate.template_type == template_data.template_type,
                EmailTemplate.is_default == True,
                EmailTemplate.is_active == True
            )
        )
        for t in existing_default.scalars().all():
            t.is_default = False
    
    template = EmailTemplate(
        name=template_data.name,
        template_type=TemplateType(template_data.template_type.value),
        subject=template_data.subject,
        body_html=template_data.body_html,
        logo_url=template_data.logo_url,
        send_to_engineer=template_data.send_to_engineer,
        send_to_customer=template_data.send_to_customer,
        additional_emails=template_data.additional_emails,
        is_default=template_data.is_default
    )
    db.add(template)
    await db.commit()
    await db.refresh(template)
    return EmailTemplateResponse.model_validate(template)


@router.get("/email-templates", response_model=List[EmailTemplateResponse])
async def get_email_templates(
    template_type: str = None,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    await get_admin_user(authorization, db)
    
    query = select(EmailTemplate).where(EmailTemplate.is_active == True)
    if template_type:
        query = query.where(EmailTemplate.template_type == template_type)
    
    result = await db.execute(query.order_by(EmailTemplate.created_at.desc()))
    templates = result.scalars().all()
    return [EmailTemplateResponse.model_validate(t) for t in templates]


@router.get("/email-templates/{template_id}", response_model=EmailTemplateResponse)
async def get_email_template(
    template_id: int,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    await get_admin_user(authorization, db)
    
    result = await db.execute(select(EmailTemplate).where(EmailTemplate.id == template_id))
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
    return EmailTemplateResponse.model_validate(template)


@router.put("/email-templates/{template_id}", response_model=EmailTemplateResponse)
async def update_email_template(
    template_id: int,
    template_data: EmailTemplateCreate,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    await get_admin_user(authorization, db)
    
    result = await db.execute(select(EmailTemplate).where(EmailTemplate.id == template_id))
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
    
    if template_data.is_default and not template.is_default:
        existing_default = await db.execute(
            select(EmailTemplate).where(
                EmailTemplate.template_type == template_data.template_type,
                EmailTemplate.is_default == True,
                EmailTemplate.is_active == True,
                EmailTemplate.id != template_id
            )
        )
        for t in existing_default.scalars().all():
            t.is_default = False
    
    template.name = template_data.name
    template.template_type = TemplateType(template_data.template_type.value)
    template.subject = template_data.subject
    template.body_html = template_data.body_html
    template.logo_url = template_data.logo_url
    template.send_to_engineer = template_data.send_to_engineer
    template.send_to_customer = template_data.send_to_customer
    template.additional_emails = template_data.additional_emails
    template.is_default = template_data.is_default
    
    await db.commit()
    await db.refresh(template)
    return EmailTemplateResponse.model_validate(template)


@router.delete("/email-templates/{template_id}")
async def delete_email_template(
    template_id: int,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    await get_admin_user(authorization, db)
    
    result = await db.execute(select(EmailTemplate).where(EmailTemplate.id == template_id))
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
    
    template.is_active = False
    await db.commit()
    return {"message": "Template deleted successfully"}


@router.post("/email-templates/{template_id}/preview")
async def preview_email_template(
    template_id: int,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """Preview an email template with sample booking data"""
    await get_admin_user(authorization, db)
    
    result = await db.execute(select(EmailTemplate).where(EmailTemplate.id == template_id))
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
    
    # Sample data for preview
    sample_data = {
        "{{order_reference}}": "ORD-2024-001",
        "{{customer_name}}": "John Smith",
        "{{scheduled_date}}": "Monday, January 27, 2025",
        "{{scheduled_time}}": "09:00 AM",
        "{{duration_hours}}": "2",
        "{{product_name}}": "Premium Service",
        "{{change_type}}": "Installation",
        "{{engineer_name}}": "Jane Engineer",
        "{{engineer_email}}": "jane.engineer@company.com",
        "{{booker_name}}": "Admin User",
        "{{booker_email}}": "admin@company.com",
        "{{booking_status}}": "Confirmed",
        "{{notes}}": "Please bring ID for verification",
        "{{cancellation_fee}}": "50.00",
        "{{expedite_fee}}": "75.00",
    }
    
    # Replace placeholders in subject and body
    preview_subject = template.subject
    preview_body = template.body_html
    
    for placeholder, value in sample_data.items():
        preview_subject = preview_subject.replace(placeholder, value)
        preview_body = preview_body.replace(placeholder, value)
    
    # Build full HTML email with logo if present
    full_html = ""
    if template.logo_url:
        full_html = f'<div style="text-align: center; margin-bottom: 20px;"><img src="{template.logo_url}" alt="Company Logo" style="max-width: 200px; max-height: 100px;"></div>'
    full_html += preview_body
    
    return {
        "subject": preview_subject,
        "body_html": full_html,
        "logo_url": template.logo_url,
        "send_to_engineer": template.send_to_engineer,
        "send_to_customer": template.send_to_customer,
        "additional_emails": template.additional_emails
    }


@router.post("/email-templates/preview-custom")
async def preview_custom_email(
    subject: str,
    body_html: str,
    logo_url: str = None,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """Preview a custom email template (before saving) with sample booking data"""
    await get_admin_user(authorization, db)
    
    # Sample data for preview
    sample_data = {
        "{{order_reference}}": "ORD-2024-001",
        "{{customer_name}}": "John Smith",
        "{{scheduled_date}}": "Monday, January 27, 2025",
        "{{scheduled_time}}": "09:00 AM",
        "{{duration_hours}}": "2",
        "{{product_name}}": "Premium Service",
        "{{change_type}}": "Installation",
        "{{engineer_name}}": "Jane Engineer",
        "{{engineer_email}}": "jane.engineer@company.com",
        "{{booker_name}}": "Admin User",
        "{{booker_email}}": "admin@company.com",
        "{{booking_status}}": "Confirmed",
        "{{notes}}": "Please bring ID for verification",
        "{{cancellation_fee}}": "50.00",
        "{{expedite_fee}}": "75.00",
    }
    
    # Replace placeholders in subject and body
    preview_subject = subject
    preview_body = body_html
    
    for placeholder, value in sample_data.items():
        preview_subject = preview_subject.replace(placeholder, value)
        preview_body = preview_body.replace(placeholder, value)
    
    # Build full HTML email with logo if present
    full_html = ""
    if logo_url:
        full_html = f'<div style="text-align: center; margin-bottom: 20px;"><img src="{logo_url}" alt="Company Logo" style="max-width: 200px; max-height: 100px;"></div>'
    full_html += preview_body
    
    return {
        "subject": preview_subject,
        "body_html": full_html
    }


@router.post("/smtp/test")
async def test_smtp_connection(
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """Test SMTP connection with current settings"""
    await get_admin_user(authorization, db)
    
    # Get SMTP settings from system config
    smtp_configs = {}
    for key in ['smtp_host', 'smtp_port', 'smtp_username', 'smtp_password', 'smtp_from_email', 'smtp_use_tls']:
        result = await db.execute(select(SystemConfig).where(SystemConfig.key == key))
        config = result.scalar_one_or_none()
        if config:
            smtp_configs[key] = config.value
    
    if not smtp_configs.get('smtp_host') or not smtp_configs.get('smtp_port'):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="SMTP host and port are required")
    
    import smtplib
    from email.mime.text import MIMEText
    
    try:
        port = int(smtp_configs.get('smtp_port', 587))
        use_tls = smtp_configs.get('smtp_use_tls', 'true').lower() == 'true'
        
        if use_tls:
            server = smtplib.SMTP(smtp_configs['smtp_host'], port)
            server.starttls()
        else:
            server = smtplib.SMTP(smtp_configs['smtp_host'], port)
        
        if smtp_configs.get('smtp_username') and smtp_configs.get('smtp_password'):
            server.login(smtp_configs['smtp_username'], smtp_configs['smtp_password'])
        
        server.quit()
        return {"success": True, "message": "SMTP connection successful"}
    except Exception as e:
        return {"success": False, "message": f"SMTP connection failed: {str(e)}"}


@router.post("/smtp/send-test-email")
async def send_test_email(
    to_email: str,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """Send a test email using SMTP settings"""
    await get_admin_user(authorization, db)
    
    # Get SMTP settings from system config
    smtp_configs = {}
    for key in ['smtp_host', 'smtp_port', 'smtp_username', 'smtp_password', 'smtp_from_email', 'smtp_use_tls', 'smtp_from_name']:
        result = await db.execute(select(SystemConfig).where(SystemConfig.key == key))
        config = result.scalar_one_or_none()
        if config:
            smtp_configs[key] = config.value
    
    if not smtp_configs.get('smtp_host') or not smtp_configs.get('smtp_port'):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="SMTP host and port are required")
    
    if not smtp_configs.get('smtp_from_email'):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="SMTP from email is required")
    
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = 'Test Email from Scheduling App'
        msg['From'] = f"{smtp_configs.get('smtp_from_name', 'Scheduling App')} <{smtp_configs['smtp_from_email']}>"
        msg['To'] = to_email
        
        text_content = "This is a test email from your Scheduling App. If you received this, your SMTP settings are working correctly!"
        html_content = """
        <html>
        <body style="font-family: Arial, sans-serif; padding: 20px;">
            <h2 style="color: #4F46E5;">Test Email from Scheduling App</h2>
            <p>This is a test email from your Scheduling App.</p>
            <p style="color: #22C55E; font-weight: bold;">If you received this, your SMTP settings are working correctly!</p>
            <hr style="border: 1px solid #E5E7EB; margin: 20px 0;">
            <p style="color: #6B7280; font-size: 12px;">This email was sent as a test from the admin panel.</p>
        </body>
        </html>
        """
        
        msg.attach(MIMEText(text_content, 'plain'))
        msg.attach(MIMEText(html_content, 'html'))
        
        port = int(smtp_configs.get('smtp_port', 587))
        use_tls = smtp_configs.get('smtp_use_tls', 'true').lower() == 'true'
        
        if use_tls:
            server = smtplib.SMTP(smtp_configs['smtp_host'], port)
            server.starttls()
        else:
            server = smtplib.SMTP(smtp_configs['smtp_host'], port)
        
        if smtp_configs.get('smtp_username') and smtp_configs.get('smtp_password'):
            server.login(smtp_configs['smtp_username'], smtp_configs['smtp_password'])
        
        server.sendmail(smtp_configs['smtp_from_email'], to_email, msg.as_string())
        server.quit()
        
        return {"success": True, "message": f"Test email sent successfully to {to_email}"}
    except Exception as e:
        return {"success": False, "message": f"Failed to send test email: {str(e)}"}


# Calendar Event Template Endpoints
@router.post("/calendar-templates", response_model=CalendarEventTemplateResponse)
async def create_calendar_template(
    template_data: CalendarEventTemplateCreate,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    await get_admin_user(authorization, db)
    
    if template_data.is_default:
        existing_default = await db.execute(
            select(CalendarEventTemplate).where(
                CalendarEventTemplate.template_type == template_data.template_type,
                CalendarEventTemplate.is_default == True,
                CalendarEventTemplate.is_active == True
            )
        )
        for t in existing_default.scalars().all():
            t.is_default = False
    
    template = CalendarEventTemplate(
        name=template_data.name,
        template_type=TemplateType(template_data.template_type.value),
        event_title=template_data.event_title,
        event_body=template_data.event_body,
        include_customer_as_attendee=template_data.include_customer_as_attendee,
        additional_attendees=template_data.additional_attendees,
        is_default=template_data.is_default
    )
    db.add(template)
    await db.commit()
    await db.refresh(template)
    return CalendarEventTemplateResponse.model_validate(template)


@router.get("/calendar-templates", response_model=List[CalendarEventTemplateResponse])
async def get_calendar_templates(
    template_type: str = None,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    await get_admin_user(authorization, db)
    
    query = select(CalendarEventTemplate).where(CalendarEventTemplate.is_active == True)
    if template_type:
        query = query.where(CalendarEventTemplate.template_type == template_type)
    
    result = await db.execute(query.order_by(CalendarEventTemplate.created_at.desc()))
    templates = result.scalars().all()
    return [CalendarEventTemplateResponse.model_validate(t) for t in templates]


@router.get("/calendar-templates/{template_id}", response_model=CalendarEventTemplateResponse)
async def get_calendar_template(
    template_id: int,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    await get_admin_user(authorization, db)
    
    result = await db.execute(select(CalendarEventTemplate).where(CalendarEventTemplate.id == template_id))
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
    return CalendarEventTemplateResponse.model_validate(template)


@router.put("/calendar-templates/{template_id}", response_model=CalendarEventTemplateResponse)
async def update_calendar_template(
    template_id: int,
    template_data: CalendarEventTemplateCreate,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    await get_admin_user(authorization, db)
    
    result = await db.execute(select(CalendarEventTemplate).where(CalendarEventTemplate.id == template_id))
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
    
    if template_data.is_default and not template.is_default:
        existing_default = await db.execute(
            select(CalendarEventTemplate).where(
                CalendarEventTemplate.template_type == template_data.template_type,
                CalendarEventTemplate.is_default == True,
                CalendarEventTemplate.is_active == True,
                CalendarEventTemplate.id != template_id
            )
        )
        for t in existing_default.scalars().all():
            t.is_default = False
    
    template.name = template_data.name
    template.template_type = TemplateType(template_data.template_type.value)
    template.event_title = template_data.event_title
    template.event_body = template_data.event_body
    template.include_customer_as_attendee = template_data.include_customer_as_attendee
    template.additional_attendees = template_data.additional_attendees
    template.is_default = template_data.is_default
    
    await db.commit()
    await db.refresh(template)
    return CalendarEventTemplateResponse.model_validate(template)


@router.delete("/calendar-templates/{template_id}")
async def delete_calendar_template(
    template_id: int,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    await get_admin_user(authorization, db)
    
    result = await db.execute(select(CalendarEventTemplate).where(CalendarEventTemplate.id == template_id))
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
    
    template.is_active = False
    await db.commit()
    return {"message": "Template deleted successfully"}


# ==================== Roster Pattern Endpoints ====================

@router.post("/roster-patterns", response_model=RosterPatternResponse)
async def create_roster_pattern(
    pattern_data: RosterPatternCreate,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """Create a new roster pattern with phases"""
    await get_admin_user(authorization, db)
    
    pattern = RosterPattern(
        name=pattern_data.name,
        description=pattern_data.description
    )
    db.add(pattern)
    await db.flush()
    
    for phase_data in pattern_data.phases:
        phase = RosterPhase(
            pattern_id=pattern.id,
            phase_order=phase_data.phase_order,
            name=phase_data.name,
            days_on=phase_data.days_on,
            days_off=phase_data.days_off,
            start_time=phase_data.start_time,
            end_time=phase_data.end_time,
            repeat_weeks=phase_data.repeat_weeks
        )
        db.add(phase)
    
    await db.commit()
    
    result = await db.execute(
        select(RosterPattern)
        .where(RosterPattern.id == pattern.id)
        .options(selectinload(RosterPattern.phases))
    )
    pattern = result.scalar_one()
    return RosterPatternResponse.model_validate(pattern)


@router.get("/roster-patterns", response_model=List[RosterPatternListResponse])
async def get_roster_patterns(
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """Get all active roster patterns"""
    await get_admin_user(authorization, db)
    
    result = await db.execute(
        select(RosterPattern)
        .where(RosterPattern.is_active == True)
        .options(selectinload(RosterPattern.phases))
        .order_by(RosterPattern.name)
    )
    patterns = result.scalars().all()
    
    return [
        RosterPatternListResponse(
            id=p.id,
            name=p.name,
            description=p.description,
            is_active=p.is_active,
            phase_count=len(p.phases),
            created_at=p.created_at
        )
        for p in patterns
    ]


@router.get("/roster-patterns/{pattern_id}", response_model=RosterPatternResponse)
async def get_roster_pattern(
    pattern_id: int,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """Get a specific roster pattern with all phases"""
    await get_admin_user(authorization, db)
    
    result = await db.execute(
        select(RosterPattern)
        .where(RosterPattern.id == pattern_id)
        .options(selectinload(RosterPattern.phases))
    )
    pattern = result.scalar_one_or_none()
    if not pattern:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Roster pattern not found")
    
    return RosterPatternResponse.model_validate(pattern)


@router.put("/roster-patterns/{pattern_id}", response_model=RosterPatternResponse)
async def update_roster_pattern(
    pattern_id: int,
    pattern_data: RosterPatternUpdate,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """Update a roster pattern and its phases"""
    await get_admin_user(authorization, db)
    
    result = await db.execute(
        select(RosterPattern)
        .where(RosterPattern.id == pattern_id)
        .options(selectinload(RosterPattern.phases))
    )
    pattern = result.scalar_one_or_none()
    if not pattern:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Roster pattern not found")
    
    if pattern_data.name is not None:
        pattern.name = pattern_data.name
    if pattern_data.description is not None:
        pattern.description = pattern_data.description
    
    if pattern_data.phases is not None:
        for phase in pattern.phases:
            await db.delete(phase)
        
        for phase_data in pattern_data.phases:
            phase = RosterPhase(
                pattern_id=pattern.id,
                phase_order=phase_data.phase_order,
                name=phase_data.name,
                days_on=phase_data.days_on,
                days_off=phase_data.days_off,
                start_time=phase_data.start_time,
                end_time=phase_data.end_time,
                repeat_weeks=phase_data.repeat_weeks
            )
            db.add(phase)
    
    await db.commit()
    
    result = await db.execute(
        select(RosterPattern)
        .where(RosterPattern.id == pattern_id)
        .options(selectinload(RosterPattern.phases))
    )
    pattern = result.scalar_one()
    return RosterPatternResponse.model_validate(pattern)


@router.delete("/roster-patterns/{pattern_id}")
async def delete_roster_pattern(
    pattern_id: int,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """Soft delete a roster pattern"""
    await get_admin_user(authorization, db)
    
    result = await db.execute(select(RosterPattern).where(RosterPattern.id == pattern_id))
    pattern = result.scalar_one_or_none()
    if not pattern:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Roster pattern not found")
    
    pattern.is_active = False
    await db.commit()
    return {"message": "Roster pattern deleted successfully"}


# ==================== Engineer Roster Assignment Endpoints ====================

@router.post("/engineers/{engineer_id}/roster-assignment", response_model=EngineerRosterAssignmentResponse)
async def assign_roster_to_engineer(
    engineer_id: int,
    assignment_data: EngineerRosterAssignmentCreate,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """Assign a roster pattern to an engineer"""
    await get_admin_user(authorization, db)
    
    result = await db.execute(select(Engineer).where(Engineer.id == engineer_id))
    engineer = result.scalar_one_or_none()
    if not engineer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Engineer not found")
    
    result = await db.execute(select(RosterPattern).where(RosterPattern.id == assignment_data.pattern_id))
    pattern = result.scalar_one_or_none()
    if not pattern:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Roster pattern not found")
    
    existing = await db.execute(
        select(EngineerRosterAssignment)
        .where(
            EngineerRosterAssignment.engineer_id == engineer_id,
            EngineerRosterAssignment.is_active == True
        )
    )
    existing_assignment = existing.scalar_one_or_none()
    if existing_assignment:
        existing_assignment.is_active = False
    
    assignment = EngineerRosterAssignment(
        engineer_id=engineer_id,
        pattern_id=assignment_data.pattern_id,
        start_date=assignment_data.start_date,
        end_date=assignment_data.end_date,
        is_repeating=assignment_data.is_repeating
    )
    db.add(assignment)
    await db.commit()
    
    result = await db.execute(
        select(EngineerRosterAssignment)
        .where(EngineerRosterAssignment.id == assignment.id)
        .options(selectinload(EngineerRosterAssignment.pattern).selectinload(RosterPattern.phases))
    )
    assignment = result.scalar_one()
    return EngineerRosterAssignmentResponse.model_validate(assignment)


@router.get("/engineers/{engineer_id}/roster-assignment", response_model=EngineerRosterAssignmentResponse)
async def get_engineer_roster_assignment(
    engineer_id: int,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """Get the active roster assignment for an engineer"""
    await get_admin_user(authorization, db)
    
    result = await db.execute(
        select(EngineerRosterAssignment)
        .where(
            EngineerRosterAssignment.engineer_id == engineer_id,
            EngineerRosterAssignment.is_active == True
        )
        .options(selectinload(EngineerRosterAssignment.pattern).selectinload(RosterPattern.phases))
    )
    assignment = result.scalar_one_or_none()
    if not assignment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No active roster assignment found")
    
    return EngineerRosterAssignmentResponse.model_validate(assignment)


@router.delete("/engineers/{engineer_id}/roster-assignment")
async def remove_engineer_roster_assignment(
    engineer_id: int,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """Remove the active roster assignment from an engineer"""
    await get_admin_user(authorization, db)
    
    result = await db.execute(
        select(EngineerRosterAssignment)
        .where(
            EngineerRosterAssignment.engineer_id == engineer_id,
            EngineerRosterAssignment.is_active == True
        )
    )
    assignment = result.scalar_one_or_none()
    if not assignment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No active roster assignment found")
    
    assignment.is_active = False
    await db.commit()
    return {"message": "Roster assignment removed successfully"}


@router.get("/roster-assignments", response_model=List[EngineerRosterAssignmentResponse])
async def get_all_roster_assignments(
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """Get all active roster assignments"""
    await get_admin_user(authorization, db)
    
    result = await db.execute(
        select(EngineerRosterAssignment)
        .where(EngineerRosterAssignment.is_active == True)
        .options(selectinload(EngineerRosterAssignment.pattern).selectinload(RosterPattern.phases))
    )
    assignments = result.scalars().all()
    return [EngineerRosterAssignmentResponse.model_validate(a) for a in assignments]


# File upload configuration
UPLOAD_DIR = "/data/uploads" if os.path.exists("/data") else "./uploads"
ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".txt"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    file_type: str = "attachment",
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """Upload a file and return its URL. file_type can be 'logo' or 'attachment'"""
    await get_admin_user(authorization, db)
    
    # Validate file extension
    file_ext = os.path.splitext(file.filename)[1].lower() if file.filename else ""
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type not allowed. Allowed types: {', '.join(ALLOWED_EXTENSIONS)}"
        )
    
    # Create upload directory if it doesn't exist
    upload_subdir = os.path.join(UPLOAD_DIR, file_type)
    os.makedirs(upload_subdir, exist_ok=True)
    
    # Generate unique filename
    unique_filename = f"{uuid.uuid4()}{file_ext}"
    file_path = os.path.join(upload_subdir, unique_filename)
    
    # Read and validate file size
    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File too large. Maximum size is {MAX_FILE_SIZE // (1024*1024)}MB"
        )
    
    # Save file
    async with aiofiles.open(file_path, 'wb') as f:
        await f.write(contents)
    
    # Return the URL path to access the file
    return {
        "filename": unique_filename,
        "original_filename": file.filename,
        "file_type": file_type,
        "url": f"/admin/files/{file_type}/{unique_filename}"
    }


@router.get("/files/{file_type}/{filename}")
async def get_uploaded_file(file_type: str, filename: str):
    """Serve uploaded files"""
    file_path = os.path.join(UPLOAD_DIR, file_type, filename)
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
    
    return FileResponse(file_path)


# Expedite Request Endpoints
@router.get("/expedite-requests", response_model=List[ExpediteRequestResponse])
async def get_expedite_requests(
    status_filter: str = None,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """Get all expedite requests (admin only)"""
    await get_admin_user(authorization, db)
    
    query = select(ExpediteRequest).options(
        selectinload(ExpediteRequest.requester),
        selectinload(ExpediteRequest.fee_acknowledged_by),
        selectinload(ExpediteRequest.product),
        selectinload(ExpediteRequest.change_type),
        selectinload(ExpediteRequest.assigned_engineer).selectinload(Engineer.user),
        selectinload(ExpediteRequest.assigned_engineer).selectinload(Engineer.schedules)
    ).order_by(ExpediteRequest.created_at.desc())
    
    if status_filter:
        query = query.where(ExpediteRequest.status == status_filter)
    
    result = await db.execute(query)
    requests = result.scalars().all()
    return [ExpediteRequestResponse.model_validate(r) for r in requests]


@router.get("/expedite-requests/{request_id}", response_model=ExpediteRequestResponse)
async def get_expedite_request(
    request_id: int,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """Get a specific expedite request"""
    await get_admin_user(authorization, db)
    
    result = await db.execute(
        select(ExpediteRequest)
        .options(
            selectinload(ExpediteRequest.requester),
            selectinload(ExpediteRequest.product),
            selectinload(ExpediteRequest.change_type),
            selectinload(ExpediteRequest.assigned_engineer).selectinload(Engineer.user),
            selectinload(ExpediteRequest.assigned_engineer).selectinload(Engineer.schedules)
        )
        .where(ExpediteRequest.id == request_id)
    )
    request = result.scalar_one_or_none()
    if not request:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Expedite request not found")
    
    return ExpediteRequestResponse.model_validate(request)


@router.post("/expedite-requests/{request_id}/approve", response_model=ExpediteRequestResponse)
async def approve_expedite_request(
    request_id: int,
    approval_data: ExpediteRequestApprove,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """Approve an expedite request and create a booking"""
    await get_admin_user(authorization, db)
    
    result = await db.execute(
        select(ExpediteRequest)
        .options(
            selectinload(ExpediteRequest.requester),
            selectinload(ExpediteRequest.product),
            selectinload(ExpediteRequest.change_type)
        )
        .where(ExpediteRequest.id == request_id)
    )
    expedite_request = result.scalar_one_or_none()
    if not expedite_request:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Expedite request not found")
    
    if expedite_request.status != ExpediteRequestStatus.PENDING:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Request has already been processed")
    
    # Verify engineer exists
    engineer_result = await db.execute(select(Engineer).where(Engineer.id == approval_data.assigned_engineer_id))
    engineer = engineer_result.scalar_one_or_none()
    if not engineer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Engineer not found")
    
    # Create the booking
    booking = Booking(
        order_reference=expedite_request.order_reference,
        customer_name=expedite_request.customer_name,
        booker_id=expedite_request.requester_id,
        engineer_id=approval_data.assigned_engineer_id,
        product_id=expedite_request.product_id,
        change_type_id=expedite_request.change_type_id,
        scheduled_date=approval_data.scheduled_date,
        duration_hours=expedite_request.duration_hours,
        status=BookingStatus.CONFIRMED,
        custom_fields_data=expedite_request.custom_fields_data,
        notes=expedite_request.notes,
        additional_emails=expedite_request.additional_emails,
        engineer_attachment_url=expedite_request.engineer_attachment_url,
        customer_attachment_url=expedite_request.customer_attachment_url,
        expedite_fee=expedite_request.expedite_fee
    )
    db.add(booking)
    await db.flush()
    
    # Apply fees to the booking (Failover Testing, Out of Hours, etc.)
    await apply_fees_to_booking(
        db,
        booking.id,
        expedite_request.product_id,
        expedite_request.change_type_id,
        approval_data.scheduled_date,
        expedite_request.duration_hours
    )
    
    # Update the expedite request
    expedite_request.status = ExpediteRequestStatus.APPROVED
    expedite_request.assigned_engineer_id = approval_data.assigned_engineer_id
    expedite_request.admin_notes = approval_data.admin_notes
    expedite_request.resulting_booking_id = booking.id
    
    await db.commit()
    
    # Reload with relationships
    result = await db.execute(
        select(ExpediteRequest)
        .options(
            selectinload(ExpediteRequest.requester),
            selectinload(ExpediteRequest.product),
            selectinload(ExpediteRequest.change_type),
            selectinload(ExpediteRequest.assigned_engineer).selectinload(Engineer.user),
            selectinload(ExpediteRequest.assigned_engineer).selectinload(Engineer.schedules)
        )
        .where(ExpediteRequest.id == request_id)
    )
    updated_request = result.scalar_one()
    return ExpediteRequestResponse.model_validate(updated_request)


@router.post("/expedite-requests/{request_id}/reject", response_model=ExpediteRequestResponse)
async def reject_expedite_request(
    request_id: int,
    rejection_data: ExpediteRequestReject,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """Reject an expedite request"""
    await get_admin_user(authorization, db)
    
    result = await db.execute(
        select(ExpediteRequest)
        .options(
            selectinload(ExpediteRequest.requester),
            selectinload(ExpediteRequest.product),
            selectinload(ExpediteRequest.change_type)
        )
        .where(ExpediteRequest.id == request_id)
    )
    expedite_request = result.scalar_one_or_none()
    if not expedite_request:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Expedite request not found")
    
    if expedite_request.status != ExpediteRequestStatus.PENDING:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Request has already been processed")
    
    expedite_request.status = ExpediteRequestStatus.REJECTED
    expedite_request.admin_notes = rejection_data.admin_notes
    
    await db.commit()
    await db.refresh(expedite_request)
    return ExpediteRequestResponse.model_validate(expedite_request)


# ==================== REPORTING ENDPOINTS ====================

@router.get("/reports/bookings")
async def get_bookings_report(
    start_date: str = None,
    end_date: str = None,
    status: str = None,
    product_id: int = None,
    engineer_id: int = None,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """Get bookings report with optional filters"""
    await get_admin_user(authorization, db)
    
    from datetime import datetime
    
    query = select(Booking).options(
        selectinload(Booking.engineer).selectinload(Engineer.user),
        selectinload(Booking.product),
        selectinload(Booking.change_type),
        selectinload(Booking.booker)
    )
    
    if start_date:
        query = query.where(Booking.scheduled_date >= datetime.fromisoformat(start_date))
    if end_date:
        query = query.where(Booking.scheduled_date <= datetime.fromisoformat(end_date))
    if status:
        query = query.where(Booking.status == status)
    if product_id:
        query = query.where(Booking.product_id == product_id)
    if engineer_id:
        query = query.where(Booking.engineer_id == engineer_id)
    
    query = query.order_by(Booking.scheduled_date.desc())
    result = await db.execute(query)
    bookings = result.scalars().all()
    
    return [{
        "id": b.id,
        "order_reference": b.order_reference,
        "customer_name": b.customer_name,
        "scheduled_date": b.scheduled_date.isoformat() if b.scheduled_date else None,
        "duration_hours": b.duration_hours,
        "status": b.status.value if hasattr(b.status, 'value') else b.status,
        "product_name": b.product.name if b.product else None,
        "change_type_name": b.change_type.name if b.change_type else None,
        "engineer_name": b.engineer.user.full_name if b.engineer and b.engineer.user else None,
        "booker_name": b.booker.full_name if b.booker else None,
        "cancellation_fee": b.cancellation_fee,
        "expedite_fee": b.expedite_fee,
        "created_at": b.created_at.isoformat() if b.created_at else None,
    } for b in bookings]


@router.get("/reports/full-data-export")
async def get_full_data_export(
    start_date: str = None,
    end_date: str = None,
    status: str = None,
    product_id: int = None,
    engineer_id: int = None,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """Get full data export with all booking fields for Excel export"""
    await get_admin_user(authorization, db)
    
    from datetime import datetime
    
    query = select(Booking).options(
        selectinload(Booking.engineer).selectinload(Engineer.user),
        selectinload(Booking.product),
        selectinload(Booking.change_type),
        selectinload(Booking.booker),
        selectinload(Booking.fees).selectinload(BookingFee.fee),
        selectinload(Booking.fees).selectinload(BookingFee.approved_by),
        selectinload(Booking.fees).selectinload(BookingFee.waived_by)
    )
    
    if start_date:
        query = query.where(Booking.scheduled_date >= datetime.fromisoformat(start_date))
    if end_date:
        query = query.where(Booking.scheduled_date <= datetime.fromisoformat(end_date))
    if status:
        query = query.where(Booking.status == status)
    if product_id:
        query = query.where(Booking.product_id == product_id)
    if engineer_id:
        query = query.where(Booking.engineer_id == engineer_id)
    
    query = query.order_by(Booking.scheduled_date.desc())
    result = await db.execute(query)
    bookings = result.scalars().all()
    
    # Get custom fields for column headers
    custom_fields_result = await db.execute(select(CustomField).where(CustomField.is_active == True))
    custom_fields = custom_fields_result.scalars().all()
    
    export_data = []
    for b in bookings:
        # Calculate total fees by status
        total_approved = sum(f.amount for f in b.fees if f.status.value == 'approved') if b.fees else 0
        total_pending = sum(f.amount for f in b.fees if f.status.value == 'pending') if b.fees else 0
        total_waived = sum(f.amount for f in b.fees if f.status.value == 'waived') if b.fees else 0
        
        # Build fee breakdown string and collect fee details
        fee_names = []
        fee_details = []
        for f in (b.fees or []):
            fee_name = f.fee.name if f.fee else "Unknown"
            fee_names.append(fee_name)
            fee_details.append(f"{fee_name}: £{f.amount:.2f} ({f.status.value})")
        
        row = {
            "id": b.id,
            "order_reference": b.order_reference,
            "customer_name": b.customer_name,
            "scheduled_date": b.scheduled_date.isoformat() if b.scheduled_date else None,
            "duration_hours": b.duration_hours,
            "status": b.status.value if hasattr(b.status, 'value') else b.status,
            "product_name": b.product.name if b.product else None,
            "change_type_name": b.change_type.name if b.change_type else None,
            "engineer_name": b.engineer.user.full_name if b.engineer and b.engineer.user else None,
            "engineer_email": b.engineer.calendar_email if b.engineer else None,
            "booker_name": b.booker.full_name if b.booker else None,
            "booker_email": b.booker.email if b.booker else None,
            "notes": b.notes,
            "engineer_notes": b.engineer_notes,
            "additional_emails": ", ".join(b.additional_emails) if b.additional_emails else None,
            "cancellation_fee": b.cancellation_fee,
            "expedite_fee": b.expedite_fee,
            "total_approved_fees": total_approved,
            "total_pending_fees": total_pending,
            "total_waived_fees": total_waived,
            "fee_count": len(b.fees) if b.fees else 0,
            "fee_names": ", ".join(fee_names) if fee_names else None,
            "fee_breakdown": "; ".join(fee_details) if fee_details else None,
            "issue_description": b.issue_description,
            "issue_reported_at": b.issue_reported_at.isoformat() if b.issue_reported_at else None,
            "issue_resolved": b.issue_resolved,
            "outlook_event_id": b.outlook_event_id,
            "sharepoint_item_id": b.sharepoint_item_id,
            "engineer_attachment_url": b.engineer_attachment_url,
            "customer_attachment_url": b.customer_attachment_url,
            "created_at": b.created_at.isoformat() if b.created_at else None,
            "updated_at": b.updated_at.isoformat() if b.updated_at else None,
        }
        
        # Add custom field values
        if b.custom_fields_data:
            for cf in custom_fields:
                field_key = f"custom_{cf.id}"
                row[f"custom_field_{cf.name}"] = b.custom_fields_data.get(str(cf.id), "")
        
        export_data.append(row)
    
    return export_data


@router.get("/reports/engineers-utilization")
async def get_engineers_utilization_report(
    start_date: str = None,
    end_date: str = None,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """Get engineer utilization report"""
    await get_admin_user(authorization, db)
    
    from datetime import datetime
    
    # Get all engineers
    engineers_result = await db.execute(
        select(Engineer).options(selectinload(Engineer.user))
    )
    engineers = engineers_result.scalars().all()
    
    report = []
    for eng in engineers:
        # Count bookings for this engineer
        booking_query = select(func.count(Booking.id), func.sum(Booking.duration_hours)).where(
            Booking.engineer_id == eng.id,
            Booking.status.in_([BookingStatus.CONFIRMED, BookingStatus.COMPLETED])
        )
        
        if start_date:
            booking_query = booking_query.where(Booking.scheduled_date >= datetime.fromisoformat(start_date))
        if end_date:
            booking_query = booking_query.where(Booking.scheduled_date <= datetime.fromisoformat(end_date))
        
        result = await db.execute(booking_query)
        row = result.one()
        booking_count = row[0] or 0
        total_hours = float(row[1] or 0)
        
        # Count completed bookings
        completed_query = select(func.count(Booking.id)).where(
            Booking.engineer_id == eng.id,
            Booking.status == BookingStatus.COMPLETED
        )
        if start_date:
            completed_query = completed_query.where(Booking.scheduled_date >= datetime.fromisoformat(start_date))
        if end_date:
            completed_query = completed_query.where(Booking.scheduled_date <= datetime.fromisoformat(end_date))
        
        completed_result = await db.execute(completed_query)
        completed_count = completed_result.scalar() or 0
        
        report.append({
            "engineer_id": eng.id,
            "engineer_name": eng.user.full_name if eng.user else f"Engineer {eng.id}",
            "calendar_email": eng.calendar_email,
            "is_available": eng.is_available,
            "total_bookings": booking_count,
            "completed_bookings": completed_count,
            "total_hours": total_hours,
        })
    
    return report


@router.get("/reports/products-summary")
async def get_products_summary_report(
    start_date: str = None,
    end_date: str = None,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """Get products summary report"""
    await get_admin_user(authorization, db)
    
    from datetime import datetime
    
    # Get all products
    products_result = await db.execute(select(Product).where(Product.is_active == True))
    products = products_result.scalars().all()
    
    report = []
    for prod in products:
        # Count bookings for this product
        booking_query = select(
            func.count(Booking.id),
            func.sum(Booking.duration_hours),
            func.sum(Booking.expedite_fee),
            func.sum(Booking.cancellation_fee)
        ).where(Booking.product_id == prod.id)
        
        if start_date:
            booking_query = booking_query.where(Booking.scheduled_date >= datetime.fromisoformat(start_date))
        if end_date:
            booking_query = booking_query.where(Booking.scheduled_date <= datetime.fromisoformat(end_date))
        
        result = await db.execute(booking_query)
        row = result.one()
        
        report.append({
            "product_id": prod.id,
            "product_name": prod.name,
            "total_bookings": row[0] or 0,
            "total_hours": float(row[1] or 0),
            "total_expedite_fees": float(row[2] or 0),
            "total_cancellation_fees": float(row[3] or 0),
        })
    
    return report


@router.get("/reports/expedite-requests-summary")
async def get_expedite_requests_summary_report(
    start_date: str = None,
    end_date: str = None,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """Get expedite requests summary report"""
    await get_admin_user(authorization, db)
    
    from datetime import datetime
    
    query = select(ExpediteRequest).options(
        selectinload(ExpediteRequest.requester),
        selectinload(ExpediteRequest.fee_acknowledged_by),
        selectinload(ExpediteRequest.product),
        selectinload(ExpediteRequest.change_type),
        selectinload(ExpediteRequest.assigned_engineer).selectinload(Engineer.user),
        selectinload(ExpediteRequest.assigned_engineer).selectinload(Engineer.schedules)
    )
    
    if start_date:
        query = query.where(ExpediteRequest.created_at >= datetime.fromisoformat(start_date))
    if end_date:
        query = query.where(ExpediteRequest.created_at <= datetime.fromisoformat(end_date))
    
    query = query.order_by(ExpediteRequest.created_at.desc())
    result = await db.execute(query)
    requests = result.scalars().all()
    
    return [{
        "id": r.id,
        "order_reference": r.order_reference,
        "customer_name": r.customer_name,
        "requested_date": r.requested_date.isoformat() if r.requested_date else None,
        "duration_hours": r.duration_hours,
        "status": r.status.value if hasattr(r.status, 'value') else r.status,
        "expedite_fee": r.expedite_fee,
        "fee_acknowledged": r.fee_acknowledged,
        "fee_acknowledged_at": r.fee_acknowledged_at.isoformat() if r.fee_acknowledged_at else None,
        "fee_acknowledged_by_email": r.fee_acknowledged_by.email if r.fee_acknowledged_by else None,
        "product_name": r.product.name if r.product else None,
        "change_type_name": r.change_type.name if r.change_type else None,
        "requester_name": r.requester.full_name if r.requester else None,
        "assigned_engineer_name": r.assigned_engineer.user.full_name if r.assigned_engineer and r.assigned_engineer.user else None,
        "admin_notes": r.admin_notes,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    } for r in requests]


@router.get("/reports/revenue-summary")
async def get_revenue_summary_report(
    start_date: str = None,
    end_date: str = None,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """Get revenue summary report with individual fee breakdowns"""
    await get_admin_user(authorization, db)
    
    from datetime import datetime
    
    # Get booking revenue
    booking_query = select(
        func.count(Booking.id),
        func.sum(Booking.expedite_fee),
        func.sum(Booking.cancellation_fee)
    )
    
    if start_date:
        booking_query = booking_query.where(Booking.scheduled_date >= datetime.fromisoformat(start_date))
    if end_date:
        booking_query = booking_query.where(Booking.scheduled_date <= datetime.fromisoformat(end_date))
    
    result = await db.execute(booking_query)
    row = result.one()
    
    # Get status breakdown
    status_query = select(Booking.status, func.count(Booking.id))
    if start_date:
        status_query = status_query.where(Booking.scheduled_date >= datetime.fromisoformat(start_date))
    if end_date:
        status_query = status_query.where(Booking.scheduled_date <= datetime.fromisoformat(end_date))
    status_query = status_query.group_by(Booking.status)
    
    status_result = await db.execute(status_query)
    status_breakdown = {str(s[0].value if hasattr(s[0], 'value') else s[0]): s[1] for s in status_result.all()}
    
    # Get expedite request stats
    expedite_query = select(
        func.count(ExpediteRequest.id),
        func.sum(ExpediteRequest.expedite_fee)
    ).where(ExpediteRequest.status == ExpediteRequestStatus.APPROVED)
    
    if start_date:
        expedite_query = expedite_query.where(ExpediteRequest.created_at >= datetime.fromisoformat(start_date))
    if end_date:
        expedite_query = expedite_query.where(ExpediteRequest.created_at <= datetime.fromisoformat(end_date))
    
    expedite_result = await db.execute(expedite_query)
    expedite_row = expedite_result.one()
    
    # Get individual fee breakdowns from BookingFee table (approved fees only)
    fee_breakdown_query = select(
        Fee.name,
        Fee.fee_type,
        func.sum(BookingFee.amount),
        func.count(BookingFee.id)
    ).join(Fee, BookingFee.fee_id == Fee.id).join(
        Booking, BookingFee.booking_id == Booking.id
    ).where(BookingFee.status == BookingFeeStatus.APPROVED)
    
    if start_date:
        fee_breakdown_query = fee_breakdown_query.where(Booking.scheduled_date >= datetime.fromisoformat(start_date))
    if end_date:
        fee_breakdown_query = fee_breakdown_query.where(Booking.scheduled_date <= datetime.fromisoformat(end_date))
    
    fee_breakdown_query = fee_breakdown_query.group_by(Fee.id, Fee.name, Fee.fee_type)
    
    fee_result = await db.execute(fee_breakdown_query)
    fee_rows = fee_result.all()
    
    # Build individual fee breakdown list
    individual_fees = []
    total_other_fees = 0
    for fee_row in fee_rows:
        fee_name, fee_type, total_amount, count = fee_row
        fee_entry = {
            "name": fee_name,
            "type": fee_type.value if hasattr(fee_type, 'value') else str(fee_type),
            "total_amount": float(total_amount or 0),
            "count": count or 0
        }
        individual_fees.append(fee_entry)
        if fee_type and (fee_type.value if hasattr(fee_type, 'value') else str(fee_type)) == "other":
            total_other_fees += float(total_amount or 0)
    
    return {
        "total_bookings": row[0] or 0,
        "total_expedite_fees": float(row[1] or 0),
        "total_cancellation_fees": float(row[2] or 0),
        "status_breakdown": status_breakdown,
        "approved_expedite_requests": expedite_row[0] or 0,
        "expedite_request_fees": float(expedite_row[1] or 0),
        "individual_fees": individual_fees,
        "total_other_fees": total_other_fees,
    }


@router.get("/reports/fees-by-booking")
async def get_fees_by_booking_report(
    start_date: str = None,
    end_date: str = None,
    status: str = None,
    product_id: int = None,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """Get fees by booking report with detailed fee breakdown per booking"""
    await get_admin_user(authorization, db)
    
    from datetime import datetime
    
    # Query ALL bookings with their fees (not just those with fees)
    query = select(Booking).options(
        selectinload(Booking.product),
        selectinload(Booking.change_type),
        selectinload(Booking.booker),
        selectinload(Booking.fees).selectinload(BookingFee.fee),
        selectinload(Booking.fees).selectinload(BookingFee.approved_by),
        selectinload(Booking.fees).selectinload(BookingFee.waived_by)
    )
    
    if start_date:
        query = query.where(Booking.scheduled_date >= datetime.fromisoformat(start_date))
    if end_date:
        query = query.where(Booking.scheduled_date <= datetime.fromisoformat(end_date))
    if status:
        query = query.where(Booking.status == status)
    if product_id:
        query = query.where(Booking.product_id == product_id)
    
    query = query.order_by(Booking.scheduled_date.desc())
    result = await db.execute(query)
    bookings = result.scalars().all()
    
    report_data = []
    for b in bookings:
        # Build fee breakdown for this booking from BookingFee records
        fee_breakdown = []
        total_approved = 0
        total_pending = 0
        total_waived = 0
        
        for bf in (b.fees or []):
            fee_entry = {
                "fee_id": bf.fee_id,
                "fee_name": bf.fee.name if bf.fee else "Unknown",
                "fee_type": bf.fee.fee_type.value if bf.fee and hasattr(bf.fee.fee_type, 'value') else str(bf.fee.fee_type) if bf.fee else None,
                "amount": bf.amount,
                "status": bf.status.value if hasattr(bf.status, 'value') else bf.status,
                "approved_by": bf.approved_by.full_name if bf.approved_by else None,
                "approved_at": bf.updated_at.isoformat() if bf.approved_by and bf.updated_at else None,
                "waived_by": bf.waived_by.full_name if bf.waived_by else None,
                "waiver_reason": bf.waiver_reason,
                "created_at": bf.created_at.isoformat() if bf.created_at else None
            }
            fee_breakdown.append(fee_entry)
            
            if bf.status.value == 'approved':
                total_approved += bf.amount
            elif bf.status.value == 'pending':
                total_pending += bf.amount
            elif bf.status.value == 'waived':
                total_waived += bf.amount
        
        # Include legacy expedite_fee and cancellation_fee from Booking table
        legacy_expedite_fee = float(b.expedite_fee or 0)
        legacy_cancellation_fee = float(b.cancellation_fee or 0)
        
        booking_entry = {
            "booking_id": b.id,
            "order_reference": b.order_reference,
            "customer_name": b.customer_name,
            "product_name": b.product.name if b.product else None,
            "change_type_name": b.change_type.name if b.change_type else None,
            "scheduled_date": b.scheduled_date.isoformat() if b.scheduled_date else None,
            "booking_status": b.status.value if hasattr(b.status, 'value') else b.status,
            "booker_name": b.booker.full_name if b.booker else None,
            "booker_email": b.booker.email if b.booker else None,
            "booking_created_at": b.created_at.isoformat() if b.created_at else None,
            "fee_breakdown": fee_breakdown,
            "total_approved_fees": total_approved,
            "total_pending_fees": total_pending,
            "total_waived_fees": total_waived,
            "total_fees": total_approved + total_pending,
            "legacy_expedite_fee": legacy_expedite_fee,
            "legacy_cancellation_fee": legacy_cancellation_fee,
            "has_booking_fees": len(b.fees or []) > 0
        }
        report_data.append(booking_entry)
    
    return report_data


@router.get("/reports/engineer-availability")
async def get_engineer_availability_report(
    start_date: str = None,
    end_date: str = None,
    engineer_id: int = None,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """Get engineer availability report showing unavailability periods and booking load"""
    await get_admin_user(authorization, db)
    
    from datetime import datetime, timedelta
    
    # Default date range: current month if not specified
    if not start_date:
        today = datetime.utcnow()
        start_date = today.replace(day=1).strftime('%Y-%m-%d')
    if not end_date:
        today = datetime.utcnow()
        next_month = today.replace(day=28) + timedelta(days=4)
        end_date = (next_month - timedelta(days=next_month.day)).strftime('%Y-%m-%d')
    
    start_dt = datetime.fromisoformat(start_date)
    end_dt = datetime.fromisoformat(end_date)
    
    # Get all engineers (or specific one)
    eng_query = select(Engineer).options(selectinload(Engineer.user))
    if engineer_id:
        eng_query = eng_query.where(Engineer.id == engineer_id)
    engineers_result = await db.execute(eng_query)
    engineers = engineers_result.scalars().all()
    
    report = []
    for eng in engineers:
        # Get unavailability entries for this engineer in date range
        unavail_query = select(EngineerUnavailability).options(
            selectinload(EngineerUnavailability.created_by)
        ).where(
            EngineerUnavailability.engineer_id == eng.id,
            EngineerUnavailability.start_datetime <= end_dt,
            EngineerUnavailability.end_datetime >= start_dt
        ).order_by(EngineerUnavailability.start_datetime)
        
        unavail_result = await db.execute(unavail_query)
        unavailability_entries = unavail_result.scalars().all()
        
        # Get bookings for this engineer in date range
        booking_query = select(Booking).where(
            Booking.engineer_id == eng.id,
            Booking.scheduled_date >= start_dt,
            Booking.scheduled_date <= end_dt,
            Booking.status.in_([BookingStatus.PENDING, BookingStatus.CONFIRMED, BookingStatus.COMPLETED])
        )
        booking_result = await db.execute(booking_query)
        bookings = booking_result.scalars().all()
        
        # Calculate total unavailable hours
        total_unavailable_hours = 0
        unavailability_details = []
        for entry in unavailability_entries:
            if entry.is_all_day:
                # Count days and multiply by working hours (assume 8 hours per day)
                days = (entry.end_datetime.date() - entry.start_datetime.date()).days + 1
                hours = days * 8
            else:
                hours = (entry.end_datetime - entry.start_datetime).total_seconds() / 3600
            total_unavailable_hours += hours
            
            unavailability_details.append({
                "id": entry.id,
                "start_datetime": entry.start_datetime.isoformat(),
                "end_datetime": entry.end_datetime.isoformat(),
                "is_all_day": entry.is_all_day,
                "reason": entry.reason,
                "hours": round(hours, 2),
                "created_by": entry.created_by.full_name if entry.created_by else None,
                "created_at": entry.created_at.isoformat() if entry.created_at else None
            })
        
        # Calculate booking hours
        total_booking_hours = sum(float(b.duration_hours or 0) for b in bookings)
        booking_count = len(bookings)
        
        # Calculate working days in range (excluding weekends)
        working_days = 0
        current = start_dt
        while current <= end_dt:
            if current.weekday() < 5:  # Monday to Friday
                working_days += 1
            current += timedelta(days=1)
        
        # Calculate total available hours (working days * 8 hours - unavailable hours)
        total_working_hours = working_days * 8
        available_hours = max(0, total_working_hours - total_unavailable_hours)
        
        # Calculate utilization percentage
        utilization_pct = (total_booking_hours / available_hours * 100) if available_hours > 0 else 0
        
        report.append({
            "engineer_id": eng.id,
            "engineer_name": eng.user.full_name if eng.user else f"Engineer {eng.id}",
            "calendar_email": eng.calendar_email,
            "is_available": eng.is_available,
            "working_hours_start": eng.working_hours_start,
            "working_hours_end": eng.working_hours_end,
            "date_range_start": start_date,
            "date_range_end": end_date,
            "working_days_in_range": working_days,
            "total_working_hours": total_working_hours,
            "total_unavailable_hours": round(total_unavailable_hours, 2),
            "available_hours": round(available_hours, 2),
            "total_booking_hours": round(total_booking_hours, 2),
            "booking_count": booking_count,
            "utilization_percentage": round(utilization_pct, 1),
            "unavailability_entries": unavailability_details
        })
    
    return report


# ==================== Engineer Unavailability Management ====================

@router.get("/engineers/{engineer_id}/unavailability")
async def get_engineer_unavailability(
    engineer_id: int,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """Get all unavailability entries for an engineer"""
    await get_admin_user(authorization, db)
    
    result = await db.execute(
        select(EngineerUnavailability)
        .options(selectinload(EngineerUnavailability.created_by))
        .where(EngineerUnavailability.engineer_id == engineer_id)
        .order_by(EngineerUnavailability.start_datetime)
    )
    return result.scalars().all()


@router.post("/engineers/{engineer_id}/unavailability")
async def create_engineer_unavailability(
    engineer_id: int,
    unavailability: EngineerUnavailabilityCreate,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """Create an unavailability entry for any engineer (admin only)"""
    admin_user = await get_admin_user(authorization, db)
    
    # Verify engineer exists
    engineer_result = await db.execute(select(Engineer).where(Engineer.id == engineer_id))
    engineer = engineer_result.scalar_one_or_none()
    if not engineer:
        raise HTTPException(status_code=404, detail="Engineer not found")
    
    db_unavailability = EngineerUnavailability(
        engineer_id=engineer_id,
        start_datetime=unavailability.start_datetime,
        end_datetime=unavailability.end_datetime,
        reason=unavailability.reason,
        created_by_id=admin_user.id,
        is_all_day=unavailability.is_all_day
    )
    db.add(db_unavailability)
    await db.commit()
    await db.refresh(db_unavailability)
    
    # Load the created_by relationship
    result = await db.execute(
        select(EngineerUnavailability)
        .options(selectinload(EngineerUnavailability.created_by))
        .where(EngineerUnavailability.id == db_unavailability.id)
    )
    return result.scalar_one()


@router.delete("/unavailability/{unavailability_id}")
async def delete_unavailability(
    unavailability_id: int,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """Delete any unavailability entry (admin only)"""
    await get_admin_user(authorization, db)
    
    result = await db.execute(
        select(EngineerUnavailability).where(EngineerUnavailability.id == unavailability_id)
    )
    unavailability = result.scalar_one_or_none()
    if not unavailability:
        raise HTTPException(status_code=404, detail="Unavailability entry not found")
    
    await db.delete(unavailability)
    await db.commit()
    return {"message": "Unavailability entry deleted"}


@router.get("/all-unavailability")
async def get_all_unavailability(
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """Get all unavailability entries for all engineers"""
    await get_admin_user(authorization, db)
    
    result = await db.execute(
        select(EngineerUnavailability)
        .options(
            selectinload(EngineerUnavailability.created_by),
            selectinload(EngineerUnavailability.engineer).selectinload(Engineer.user)
        )
        .order_by(EngineerUnavailability.start_datetime)
    )
    return result.scalars().all()


# Email Rules CRUD
@router.post("/email-rules", response_model=EmailRuleResponse)
async def create_email_rule(
    rule_data: EmailRuleCreate,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """Create a new email rule"""
    await get_admin_user(authorization, db)
    
    # Verify email template exists
    template_result = await db.execute(
        select(EmailTemplate).where(EmailTemplate.id == rule_data.email_template_id)
    )
    template = template_result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail="Email template not found")
    
    rule = EmailRule(
        name=rule_data.name,
        description=rule_data.description,
        trigger_type=EmailRuleTriggerType(rule_data.trigger_type.value),
        trigger_hours=rule_data.trigger_hours,
        condition_status=BookingStatus(rule_data.condition_status.value) if rule_data.condition_status else None,
        email_template_id=rule_data.email_template_id,
        recipient_types=rule_data.recipient_types,
        additional_emails=rule_data.additional_emails,
        is_active=rule_data.is_active
    )
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    
    return EmailRuleResponse(
        id=rule.id,
        name=rule.name,
        description=rule.description,
        trigger_type=rule.trigger_type.value,
        trigger_hours=rule.trigger_hours,
        condition_status=rule.condition_status.value if rule.condition_status else None,
        email_template_id=rule.email_template_id,
        email_template_name=template.name,
        recipient_types=rule.recipient_types,
        additional_emails=rule.additional_emails,
        is_active=rule.is_active,
        created_at=rule.created_at,
        updated_at=rule.updated_at
    )


@router.get("/email-rules", response_model=List[EmailRuleResponse])
async def get_email_rules(
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """Get all email rules"""
    await get_admin_user(authorization, db)
    
    result = await db.execute(
        select(EmailRule)
        .options(selectinload(EmailRule.email_template))
        .order_by(EmailRule.created_at.desc())
    )
    rules = result.scalars().all()
    
    return [
        EmailRuleResponse(
            id=rule.id,
            name=rule.name,
            description=rule.description,
            trigger_type=rule.trigger_type.value,
            trigger_hours=rule.trigger_hours,
            condition_status=rule.condition_status.value if rule.condition_status else None,
            email_template_id=rule.email_template_id,
            email_template_name=rule.email_template.name if rule.email_template else None,
            recipient_types=rule.recipient_types,
            additional_emails=rule.additional_emails,
            is_active=rule.is_active,
            created_at=rule.created_at,
            updated_at=rule.updated_at
        )
        for rule in rules
    ]


@router.get("/email-rules/{rule_id}", response_model=EmailRuleResponse)
async def get_email_rule(
    rule_id: int,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """Get a specific email rule"""
    await get_admin_user(authorization, db)
    
    result = await db.execute(
        select(EmailRule)
        .options(selectinload(EmailRule.email_template))
        .where(EmailRule.id == rule_id)
    )
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Email rule not found")
    
    return EmailRuleResponse(
        id=rule.id,
        name=rule.name,
        description=rule.description,
        trigger_type=rule.trigger_type.value,
        trigger_hours=rule.trigger_hours,
        condition_status=rule.condition_status.value if rule.condition_status else None,
        email_template_id=rule.email_template_id,
        email_template_name=rule.email_template.name if rule.email_template else None,
        recipient_types=rule.recipient_types,
        additional_emails=rule.additional_emails,
        is_active=rule.is_active,
        created_at=rule.created_at,
        updated_at=rule.updated_at
    )


@router.put("/email-rules/{rule_id}", response_model=EmailRuleResponse)
async def update_email_rule(
    rule_id: int,
    rule_data: EmailRuleUpdate,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """Update an email rule"""
    await get_admin_user(authorization, db)
    
    result = await db.execute(
        select(EmailRule)
        .options(selectinload(EmailRule.email_template))
        .where(EmailRule.id == rule_id)
    )
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Email rule not found")
    
    if rule_data.name is not None:
        rule.name = rule_data.name
    if rule_data.description is not None:
        rule.description = rule_data.description
    if rule_data.trigger_type is not None:
        rule.trigger_type = EmailRuleTriggerType(rule_data.trigger_type.value)
    if rule_data.trigger_hours is not None:
        rule.trigger_hours = rule_data.trigger_hours
    if rule_data.condition_status is not None:
        rule.condition_status = BookingStatus(rule_data.condition_status.value)
    if rule_data.email_template_id is not None:
        # Verify template exists
        template_result = await db.execute(
            select(EmailTemplate).where(EmailTemplate.id == rule_data.email_template_id)
        )
        if not template_result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Email template not found")
        rule.email_template_id = rule_data.email_template_id
    if rule_data.recipient_types is not None:
        rule.recipient_types = rule_data.recipient_types
    if rule_data.additional_emails is not None:
        rule.additional_emails = rule_data.additional_emails
    if rule_data.is_active is not None:
        rule.is_active = rule_data.is_active
    
    await db.commit()
    await db.refresh(rule)
    
    # Reload with template
    result = await db.execute(
        select(EmailRule)
        .options(selectinload(EmailRule.email_template))
        .where(EmailRule.id == rule_id)
    )
    rule = result.scalar_one()
    
    return EmailRuleResponse(
        id=rule.id,
        name=rule.name,
        description=rule.description,
        trigger_type=rule.trigger_type.value,
        trigger_hours=rule.trigger_hours,
        condition_status=rule.condition_status.value if rule.condition_status else None,
        email_template_id=rule.email_template_id,
        email_template_name=rule.email_template.name if rule.email_template else None,
        recipient_types=rule.recipient_types,
        additional_emails=rule.additional_emails,
        is_active=rule.is_active,
        created_at=rule.created_at,
        updated_at=rule.updated_at
    )


@router.delete("/email-rules/{rule_id}")
async def delete_email_rule(
    rule_id: int,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """Delete an email rule"""
    await get_admin_user(authorization, db)
    
    result = await db.execute(select(EmailRule).where(EmailRule.id == rule_id))
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Email rule not found")
    
    await db.delete(rule)
    await db.commit()
    return {"message": "Email rule deleted"}


@router.post("/email-rules/{rule_id}/toggle")
async def toggle_email_rule(
    rule_id: int,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """Toggle an email rule's active status"""
    await get_admin_user(authorization, db)
    
    result = await db.execute(select(EmailRule).where(EmailRule.id == rule_id))
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Email rule not found")
    
    rule.is_active = not rule.is_active
    await db.commit()
    return {"message": f"Email rule {'activated' if rule.is_active else 'deactivated'}", "is_active": rule.is_active}


@router.get("/email-rules/{rule_id}/logs", response_model=List[EmailRuleSentLogResponse])
async def get_email_rule_logs(
    rule_id: int,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """Get sent email logs for a specific rule"""
    await get_admin_user(authorization, db)
    
    result = await db.execute(
        select(EmailRuleSentLog)
        .where(EmailRuleSentLog.rule_id == rule_id)
        .order_by(EmailRuleSentLog.sent_at.desc())
        .limit(100)
    )
    return result.scalars().all()


@router.post("/email-rules/process")
async def process_email_rules(
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """Manually trigger processing of all active email rules"""
    await get_admin_user(authorization, db)
    
    from app.services.email_rule_processor import process_all_rules
    results = await process_all_rules(db)
    return {"message": "Email rules processed", "results": results}


@router.delete("/bookings/{booking_id}/permanent")
async def permanently_delete_booking(
    booking_id: int,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """Permanently delete a booking and all related records (admin only)"""
    await get_admin_user(authorization, db)
    
    # Get the booking
    result = await db.execute(select(Booking).where(Booking.id == booking_id))
    booking = result.scalar_one_or_none()
    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")
    
    # Delete related booking fees
    await db.execute(
        select(BookingFee).where(BookingFee.booking_id == booking_id)
    )
    booking_fees_result = await db.execute(
        select(BookingFee).where(BookingFee.booking_id == booking_id)
    )
    for fee in booking_fees_result.scalars().all():
        await db.delete(fee)
    
    # Delete related status updates
    status_updates_result = await db.execute(
        select(BookingStatusUpdate).where(BookingStatusUpdate.booking_id == booking_id)
    )
    for update in status_updates_result.scalars().all():
        await db.delete(update)
    
    # Delete the booking itself
    await db.delete(booking)
    await db.commit()
    
    return {"message": f"Booking {booking_id} permanently deleted"}


# Bank Holiday Management Endpoints
@router.get("/bank-holidays", response_model=List[BankHolidayResponse])
async def get_bank_holidays(
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    await get_admin_user(authorization, db)
    
    result = await db.execute(
        select(BankHoliday).order_by(BankHoliday.date)
    )
    holidays = result.scalars().all()
    return [BankHolidayResponse.model_validate(h) for h in holidays]


@router.post("/bank-holidays", response_model=BankHolidayResponse)
async def create_bank_holiday(
    holiday_data: BankHolidayCreate,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    await get_admin_user(authorization, db)
    
    holiday = BankHoliday(
        name=holiday_data.name,
        date=holiday_data.date
    )
    db.add(holiday)
    await db.commit()
    await db.refresh(holiday)
    
    return BankHolidayResponse.model_validate(holiday)


@router.delete("/bank-holidays/{holiday_id}")
async def delete_bank_holiday(
    holiday_id: int,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    await get_admin_user(authorization, db)
    
    result = await db.execute(select(BankHoliday).where(BankHoliday.id == holiday_id))
    holiday = result.scalar_one_or_none()
    if not holiday:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bank holiday not found")
    
    await db.delete(holiday)
    await db.commit()
    
    return {"message": "Bank holiday deleted successfully"}


# ==================== ISSUES REPORTED ENDPOINTS ====================

@router.get("/issues")
async def get_open_issues(
    include_resolved: bool = False,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """Get all bookings with reported issues"""
    await get_admin_user(authorization, db)
    
    query = select(Booking).options(
        selectinload(Booking.engineer).selectinload(Engineer.user),
        selectinload(Booking.product),
        selectinload(Booking.change_type),
        selectinload(Booking.booker)
    ).where(Booking.issue_description.isnot(None))
    
    if not include_resolved:
        query = query.where(Booking.issue_resolved == False)
    
    query = query.order_by(Booking.issue_reported_at.desc())
    result = await db.execute(query)
    bookings = result.scalars().all()
    
    return [{
        "id": b.id,
        "order_reference": b.order_reference,
        "customer_name": b.customer_name,
        "scheduled_date": b.scheduled_date.isoformat() if b.scheduled_date else None,
        "status": b.status.value if hasattr(b.status, 'value') else b.status,
        "product_name": b.product.name if b.product else None,
        "engineer_name": b.engineer.user.full_name if b.engineer and b.engineer.user else None,
        "issue_description": b.issue_description,
        "issue_reported_at": b.issue_reported_at.isoformat() if b.issue_reported_at else None,
        "issue_resolved": b.issue_resolved,
        "engineer_notes": b.engineer_notes,
    } for b in bookings]


@router.get("/issues/count")
async def get_open_issues_count(
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """Get count of open issues"""
    await get_admin_user(authorization, db)
    
    from sqlalchemy import func
    result = await db.execute(
        select(func.count(Booking.id)).where(
            Booking.issue_description.isnot(None),
            Booking.issue_resolved == False
        )
    )
    count = result.scalar()
    
    return {"count": count}


@router.patch("/issues/{booking_id}/resolve")
async def resolve_issue(
    booking_id: int,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """Mark an issue as resolved"""
    await get_admin_user(authorization, db)
    
    result = await db.execute(select(Booking).where(Booking.id == booking_id))
    booking = result.scalar_one_or_none()
    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")
    
    booking.issue_resolved = True
    await db.commit()
    
    return {"message": "Issue marked as resolved"}


@router.patch("/issues/{booking_id}/reopen")
async def reopen_issue(
    booking_id: int,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """Reopen a resolved issue"""
    await get_admin_user(authorization, db)
    
    result = await db.execute(select(Booking).where(Booking.id == booking_id))
    booking = result.scalar_one_or_none()
    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")
    
    booking.issue_resolved = False
    await db.commit()
    
    return {"message": "Issue reopened"}


@router.get("/export-data")
async def export_all_data(
    secret_key: str,
    db: AsyncSession = Depends(get_db)
):
    """Export all data for migration purposes. Requires secret key."""
    import os
    expected_key = os.getenv("ADMIN_SETUP_KEY", "scheduling-app-admin-setup-2024")
    
    if secret_key != expected_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid secret key"
        )
    
    # Export all data
    data = {}
    
    # Users
    result = await db.execute(select(User))
    users = result.scalars().all()
    data["users"] = [
        {
            "id": u.id,
            "email": u.email,
            "full_name": u.full_name,
            "phone": u.phone,
            "role": u.role.value,
            "is_active": u.is_active,
            "microsoft_id": u.microsoft_id,
            "created_at": u.created_at.isoformat() if u.created_at else None,
            "last_login_at": u.last_login_at.isoformat() if u.last_login_at else None
        }
        for u in users
    ]
    
    # Products
    result = await db.execute(select(Product).where(Product.is_active == True))
    products = result.scalars().all()
    data["products"] = [
        {
            "id": p.id,
            "name": p.name,
            "description": p.description,
            "expedite_fee": p.expedite_fee,
            "expedite_contact_emails": p.expedite_contact_emails
        }
        for p in products
    ]
    
    # Change Types
    result = await db.execute(select(ChangeType).where(ChangeType.is_active == True))
    change_types = result.scalars().all()
    data["change_types"] = [
        {
            "id": ct.id,
            "name": ct.name,
            "description": ct.description,
            "minimum_notice_hours": ct.minimum_notice_hours,
            "cancellation_notice_hours": ct.cancellation_notice_hours,
            "amendment_notice_hours": ct.amendment_notice_hours
        }
        for ct in change_types
    ]
    
    # Engineers
    result = await db.execute(
        select(Engineer).options(
            selectinload(Engineer.user),
            selectinload(Engineer.skills)
        )
    )
    engineers = result.scalars().all()
    data["engineers"] = [
        {
            "id": e.id,
            "user_id": e.user_id,
            "user_email": e.user.email if e.user else None,
            "calendar_email": e.calendar_email,
            "is_available": e.is_available,
            "working_hours_start": e.working_hours_start,
            "working_hours_end": e.working_hours_end,
            "skills": [
                {
                    "product_id": s.product_id,
                    "change_type_id": s.change_type_id,
                    "proficiency_level": s.proficiency_level
                }
                for s in e.skills
            ]
        }
        for e in engineers
    ]
    
    # Fees
    result = await db.execute(
        select(Fee).where(Fee.is_active == True).options(
            selectinload(Fee.product_assignments),
            selectinload(Fee.change_type_assignments)
        )
    )
    fees = result.scalars().all()
    data["fees"] = [
        {
            "id": f.id,
            "name": f.name,
            "description": f.description,
            "amount": f.amount,
            "category": f.category,
            "apply_mode": f.apply_mode.value if f.apply_mode else "all",
            "requires_approval": f.requires_approval,
            "apply_on_weekends": f.apply_on_weekends,
            "apply_on_bank_holidays": f.apply_on_bank_holidays,
            "apply_out_of_hours": f.apply_out_of_hours,
            "charge_per_hour": f.charge_per_hour,
            "product_ids": [pa.product_id for pa in f.product_assignments],
            "change_type_ids": [cta.change_type_id for cta in f.change_type_assignments]
        }
        for f in fees
    ]
    
    # System Config
    result = await db.execute(select(SystemConfig))
    configs = result.scalars().all()
    data["system_config"] = {c.key: c.value for c in configs}
    
    # Email Templates
    result = await db.execute(select(EmailTemplate))
    templates = result.scalars().all()
    data["email_templates"] = [
        {
            "id": t.id,
            "name": t.name,
            "template_type": t.template_type.value,
            "subject": t.subject,
            "body": t.body,
            "is_active": t.is_active
        }
        for t in templates
    ]
    
    # Calendar Templates
    result = await db.execute(select(CalendarEventTemplate))
    cal_templates = result.scalars().all()
    data["calendar_templates"] = [
        {
            "id": t.id,
            "name": t.name,
            "template_type": t.template_type.value,
            "title_template": t.title_template,
            "description_template": t.description_template,
            "is_active": t.is_active
        }
        for t in cal_templates
    ]
    
    # Bank Holidays
    result = await db.execute(select(BankHoliday))
    holidays = result.scalars().all()
    data["bank_holidays"] = [
        {
            "id": h.id,
            "name": h.name,
            "date": h.date.isoformat() if h.date else None
        }
        for h in holidays
    ]
    
    # Custom Fields
    result = await db.execute(select(CustomField).where(CustomField.is_active == True))
    fields = result.scalars().all()
    data["custom_fields"] = [
        {
            "id": f.id,
            "name": f.name,
            "field_type": f.field_type,
            "is_required": f.is_required,
            "options": f.options
        }
        for f in fields
    ]
    
    # Email Rules
    result = await db.execute(select(EmailRule))
    rules = result.scalars().all()
    data["email_rules"] = [
        {
            "id": r.id,
            "name": r.name,
            "description": r.description,
            "trigger_type": r.trigger_type.value,
            "trigger_hours_before": r.trigger_hours_before,
            "recipient_type": r.recipient_type.value,
            "email_template_id": r.email_template_id,
            "is_active": r.is_active
        }
        for r in rules
    ]
    
    # Roster Patterns
    result = await db.execute(
        select(RosterPattern).options(selectinload(RosterPattern.phases))
    )
    patterns = result.scalars().all()
    data["roster_patterns"] = [
        {
            "id": p.id,
            "name": p.name,
            "description": p.description,
            "phases": [
                {
                    "phase_order": ph.phase_order,
                    "days_on": ph.days_on,
                    "days_off": ph.days_off,
                    "start_time": ph.start_time,
                    "end_time": ph.end_time
                }
                for ph in p.phases
            ]
        }
        for p in patterns
    ]
    
    # Bookings
    result = await db.execute(
        select(Booking).options(
            selectinload(Booking.product),
            selectinload(Booking.change_type),
            selectinload(Booking.engineer),
            selectinload(Booking.booker)
        )
    )
    bookings = result.scalars().all()
    data["bookings"] = [
        {
            "id": b.id,
            "reference_number": b.reference_number,
            "product_id": b.product_id,
            "change_type_id": b.change_type_id,
            "engineer_id": b.engineer_id,
            "booker_id": b.booker_id,
            "booker_email": b.booker.email if b.booker else None,
            "scheduled_date": b.scheduled_date.isoformat() if b.scheduled_date else None,
            "scheduled_time": b.scheduled_time,
            "duration_hours": b.duration_hours,
            "status": b.status.value,
            "notes": b.notes,
            "custom_field_values": b.custom_field_values,
            "created_at": b.created_at.isoformat() if b.created_at else None
        }
        for b in bookings
    ]
    
    return data


@router.post("/import-data")
async def import_all_data(
    secret_key: str,
    import_data: dict,
    db: AsyncSession = Depends(get_db)
):
    """Import data from another instance. Requires secret key."""
    import os
    expected_key = os.getenv("ADMIN_SETUP_KEY", "scheduling-app-admin-setup-2024")
    
    if secret_key != expected_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid secret key"
        )
    
    results = {
        "users": 0,
        "products": 0,
        "change_types": 0,
        "engineers": 0,
        "fees": 0,
        "system_config": 0,
        "email_templates": 0,
        "calendar_templates": 0,
        "bank_holidays": 0,
        "custom_fields": 0,
        "email_rules": 0,
        "roster_patterns": 0,
        "errors": []
    }
    
    # ID mappings for foreign keys
    user_mapping = {}
    product_mapping = {}
    change_type_mapping = {}
    engineer_mapping = {}
    email_template_mapping = {}
    
    # Import Users
    for user_data in import_data.get("users", []):
        try:
            # Check if user already exists
            existing = await db.execute(select(User).where(User.email == user_data["email"]))
            existing_user = existing.scalar_one_or_none()
            
            if existing_user:
                user_mapping[user_data["id"]] = existing_user.id
                continue
            
            user = User(
                email=user_data["email"],
                full_name=user_data.get("full_name", ""),
                phone=user_data.get("phone"),
                role=UserRole(user_data.get("role", "user")),
                is_active=user_data.get("is_active", True),
                microsoft_id=user_data.get("microsoft_id")
            )
            db.add(user)
            await db.flush()
            user_mapping[user_data["id"]] = user.id
            results["users"] += 1
        except Exception as e:
            results["errors"].append(f"User {user_data.get('email')}: {str(e)}")
    
    # Import Products
    for prod_data in import_data.get("products", []):
        try:
            existing = await db.execute(select(Product).where(Product.name == prod_data["name"]))
            existing_prod = existing.scalar_one_or_none()
            
            if existing_prod:
                product_mapping[prod_data["id"]] = existing_prod.id
                continue
            
            product = Product(
                name=prod_data["name"],
                description=prod_data.get("description", ""),
                expedite_fee=prod_data.get("expedite_fee", 0),
                expedite_contact_emails=prod_data.get("expedite_contact_emails")
            )
            db.add(product)
            await db.flush()
            product_mapping[prod_data["id"]] = product.id
            results["products"] += 1
        except Exception as e:
            results["errors"].append(f"Product {prod_data.get('name')}: {str(e)}")
    
    # Import Change Types
    for ct_data in import_data.get("change_types", []):
        try:
            existing = await db.execute(select(ChangeType).where(ChangeType.name == ct_data["name"]))
            existing_ct = existing.scalar_one_or_none()
            
            if existing_ct:
                change_type_mapping[ct_data["id"]] = existing_ct.id
                continue
            
            change_type = ChangeType(
                name=ct_data["name"],
                description=ct_data.get("description", ""),
                minimum_notice_hours=ct_data.get("minimum_notice_hours", 0),
                cancellation_notice_hours=ct_data.get("cancellation_notice_hours"),
                amendment_notice_hours=ct_data.get("amendment_notice_hours")
            )
            db.add(change_type)
            await db.flush()
            change_type_mapping[ct_data["id"]] = change_type.id
            results["change_types"] += 1
        except Exception as e:
            results["errors"].append(f"ChangeType {ct_data.get('name')}: {str(e)}")
    
    # Import System Config
    for key, value in import_data.get("system_config", {}).items():
        try:
            existing = await db.execute(select(SystemConfig).where(SystemConfig.key == key))
            config = existing.scalar_one_or_none()
            
            if config:
                config.value = str(value) if value is not None else ""
            else:
                config = SystemConfig(key=key, value=str(value) if value is not None else "")
                db.add(config)
            results["system_config"] += 1
        except Exception as e:
            results["errors"].append(f"SystemConfig {key}: {str(e)}")
    
    # Import Bank Holidays
    for holiday_data in import_data.get("bank_holidays", []):
        try:
            from datetime import date
            holiday_date = date.fromisoformat(holiday_data["date"]) if holiday_data.get("date") else None
            
            existing = await db.execute(
                select(BankHoliday).where(
                    BankHoliday.name == holiday_data["name"],
                    BankHoliday.date == holiday_date
                )
            )
            if existing.scalar_one_or_none():
                continue
            
            holiday = BankHoliday(
                name=holiday_data["name"],
                date=holiday_date
            )
            db.add(holiday)
            results["bank_holidays"] += 1
        except Exception as e:
            results["errors"].append(f"BankHoliday {holiday_data.get('name')}: {str(e)}")
    
    # Import Custom Fields
    for field_data in import_data.get("custom_fields", []):
        try:
            existing = await db.execute(select(CustomField).where(CustomField.name == field_data["name"]))
            if existing.scalar_one_or_none():
                continue
            
            field = CustomField(
                name=field_data["name"],
                field_type=field_data["field_type"],
                is_required=field_data.get("is_required", False),
                options=field_data.get("options")
            )
            db.add(field)
            results["custom_fields"] += 1
        except Exception as e:
            results["errors"].append(f"CustomField {field_data.get('name')}: {str(e)}")
    
    # Import Email Templates
    for template_data in import_data.get("email_templates", []):
        try:
            existing = await db.execute(select(EmailTemplate).where(EmailTemplate.name == template_data["name"]))
            existing_template = existing.scalar_one_or_none()
            
            if existing_template:
                email_template_mapping[template_data["id"]] = existing_template.id
                continue
            
            template = EmailTemplate(
                name=template_data["name"],
                template_type=TemplateType(template_data["template_type"]),
                subject=template_data["subject"],
                body=template_data["body"],
                is_active=template_data.get("is_active", True)
            )
            db.add(template)
            await db.flush()
            email_template_mapping[template_data["id"]] = template.id
            results["email_templates"] += 1
        except Exception as e:
            results["errors"].append(f"EmailTemplate {template_data.get('name')}: {str(e)}")
    
    # Import Calendar Templates
    for template_data in import_data.get("calendar_templates", []):
        try:
            existing = await db.execute(select(CalendarEventTemplate).where(CalendarEventTemplate.name == template_data["name"]))
            if existing.scalar_one_or_none():
                continue
            
            template = CalendarEventTemplate(
                name=template_data["name"],
                template_type=TemplateType(template_data["template_type"]),
                title_template=template_data["title_template"],
                description_template=template_data.get("description_template", ""),
                is_active=template_data.get("is_active", True)
            )
            db.add(template)
            results["calendar_templates"] += 1
        except Exception as e:
            results["errors"].append(f"CalendarTemplate {template_data.get('name')}: {str(e)}")
    
    # Import Email Rules
    for rule_data in import_data.get("email_rules", []):
        try:
            existing = await db.execute(select(EmailRule).where(EmailRule.name == rule_data["name"]))
            if existing.scalar_one_or_none():
                continue
            
            # Map email template ID
            old_template_id = rule_data.get("email_template_id")
            new_template_id = email_template_mapping.get(old_template_id, old_template_id) if old_template_id else None
            
            rule = EmailRule(
                name=rule_data["name"],
                description=rule_data.get("description", ""),
                trigger_type=EmailRuleTriggerType(rule_data["trigger_type"]),
                trigger_hours_before=rule_data.get("trigger_hours_before"),
                recipient_type=EmailRuleRecipientType(rule_data["recipient_type"]),
                email_template_id=new_template_id,
                is_active=rule_data.get("is_active", True)
            )
            db.add(rule)
            results["email_rules"] += 1
        except Exception as e:
            results["errors"].append(f"EmailRule {rule_data.get('name')}: {str(e)}")
    
    # Import Roster Patterns
    for pattern_data in import_data.get("roster_patterns", []):
        try:
            existing = await db.execute(select(RosterPattern).where(RosterPattern.name == pattern_data["name"]))
            if existing.scalar_one_or_none():
                continue
            
            pattern = RosterPattern(
                name=pattern_data["name"],
                description=pattern_data.get("description", "")
            )
            db.add(pattern)
            await db.flush()
            
            # Add phases
            for phase_data in pattern_data.get("phases", []):
                phase = RosterPhase(
                    roster_pattern_id=pattern.id,
                    phase_order=phase_data["phase_order"],
                    days_on=phase_data["days_on"],
                    days_off=phase_data["days_off"],
                    start_time=phase_data.get("start_time"),
                    end_time=phase_data.get("end_time")
                )
                db.add(phase)
            
            results["roster_patterns"] += 1
        except Exception as e:
            results["errors"].append(f"RosterPattern {pattern_data.get('name')}: {str(e)}")
    
    # Import Engineers (after users)
    for eng_data in import_data.get("engineers", []):
        try:
            # Find user by email
            user_email = eng_data.get("user_email")
            if not user_email:
                old_user_id = eng_data.get("user_id")
                new_user_id = user_mapping.get(old_user_id)
                if not new_user_id:
                    results["errors"].append(f"Engineer: No user mapping for user_id {old_user_id}")
                    continue
            else:
                user_result = await db.execute(select(User).where(User.email == user_email))
                user = user_result.scalar_one_or_none()
                if not user:
                    results["errors"].append(f"Engineer: User {user_email} not found")
                    continue
                new_user_id = user.id
            
            # Check if already an engineer
            existing = await db.execute(select(Engineer).where(Engineer.user_id == new_user_id))
            existing_eng = existing.scalar_one_or_none()
            
            if existing_eng:
                engineer_mapping[eng_data["id"]] = existing_eng.id
                continue
            
            # Update user role to engineer
            user_result = await db.execute(select(User).where(User.id == new_user_id))
            user = user_result.scalar_one_or_none()
            if user:
                user.role = UserRole.ENGINEER
            
            engineer = Engineer(
                user_id=new_user_id,
                calendar_email=eng_data.get("calendar_email"),
                is_available=eng_data.get("is_available", True),
                working_hours_start=eng_data.get("working_hours_start", "09:00"),
                working_hours_end=eng_data.get("working_hours_end", "17:00")
            )
            db.add(engineer)
            await db.flush()
            engineer_mapping[eng_data["id"]] = engineer.id
            
            # Add skills
            for skill_data in eng_data.get("skills", []):
                new_product_id = product_mapping.get(skill_data["product_id"])
                new_ct_id = change_type_mapping.get(skill_data["change_type_id"])
                
                if new_product_id and new_ct_id:
                    skill = EngineerSkill(
                        engineer_id=engineer.id,
                        product_id=new_product_id,
                        change_type_id=new_ct_id,
                        proficiency_level=skill_data.get("proficiency_level", 1)
                    )
                    db.add(skill)
            
            results["engineers"] += 1
        except Exception as e:
            results["errors"].append(f"Engineer {eng_data.get('user_email', 'unknown')}: {str(e)}")
    
    # Import Fees (after products and change types)
    for fee_data in import_data.get("fees", []):
        try:
            existing = await db.execute(select(Fee).where(Fee.name == fee_data["name"]))
            if existing.scalar_one_or_none():
                continue
            
            fee = Fee(
                name=fee_data["name"],
                description=fee_data.get("description", ""),
                amount=fee_data["amount"],
                category=fee_data.get("category", "other"),
                apply_mode=FeeApplyMode(fee_data.get("apply_mode", "all")),
                requires_approval=fee_data.get("requires_approval", False),
                apply_on_weekends=fee_data.get("apply_on_weekends", False),
                apply_on_bank_holidays=fee_data.get("apply_on_bank_holidays", False),
                apply_out_of_hours=fee_data.get("apply_out_of_hours", False),
                charge_per_hour=fee_data.get("charge_per_hour", False)
            )
            db.add(fee)
            await db.flush()
            
            # Add product assignments
            for old_prod_id in fee_data.get("product_ids", []):
                new_prod_id = product_mapping.get(old_prod_id)
                if new_prod_id:
                    assignment = FeeProductAssignment(fee_id=fee.id, product_id=new_prod_id)
                    db.add(assignment)
            
            # Add change type assignments
            for old_ct_id in fee_data.get("change_type_ids", []):
                new_ct_id = change_type_mapping.get(old_ct_id)
                if new_ct_id:
                    assignment = FeeChangeTypeAssignment(fee_id=fee.id, change_type_id=new_ct_id)
                    db.add(assignment)
            
            results["fees"] += 1
        except Exception as e:
            results["errors"].append(f"Fee {fee_data.get('name')}: {str(e)}")
    
    await db.commit()
    
    return {
        "message": "Import completed",
        "results": results,
        "id_mappings": {
            "users": user_mapping,
            "products": product_mapping,
            "change_types": change_type_mapping,
            "engineers": engineer_mapping
        }
    }


def is_overnight_shift_check(start_time: str, end_time: str) -> bool:
    """Check if a shift spans midnight (overnight shift)"""
    start_parts = start_time.split(":")
    end_parts = end_time.split(":")
    start_hour = int(start_parts[0])
    end_hour = int(end_parts[0])
    start_min = int(start_parts[1]) if len(start_parts) > 1 else 0
    end_min = int(end_parts[1]) if len(end_parts) > 1 else 0
    return end_hour < start_hour or (end_hour == start_hour and end_min < start_min)


def calculate_roster_for_date(assignment, target_date):
    """Calculate roster working hours for a specific date."""
    if not assignment or not assignment.pattern or not assignment.pattern.phases:
        return None
    
    pattern = assignment.pattern
    phases = sorted(pattern.phases, key=lambda p: p.phase_order)
    
    if not phases:
        return None
    
    start_date = assignment.start_date
    if isinstance(start_date, datetime):
        start_date = start_date.date()
    
    target = target_date.date() if isinstance(target_date, datetime) else target_date
    
    if target < start_date:
        return None
    
    if assignment.end_date:
        end_date = assignment.end_date
        if isinstance(end_date, datetime):
            end_date = end_date.date()
        if target > end_date:
            return None
    
    days_since_start = (target - start_date).days
    
    total_pattern_days = 0
    phase_info = []
    
    for phase in phases:
        phase_cycle_days = phase.days_on + phase.days_off
        if phase.repeat_weeks:
            phase_total_days = phase_cycle_days * phase.repeat_weeks
        else:
            phase_total_days = phase_cycle_days
        
        phase_info.append({
            'phase': phase,
            'cycle_days': phase_cycle_days,
            'total_days': phase_total_days,
            'start_day': total_pattern_days
        })
        total_pattern_days += phase_total_days
    
    if total_pattern_days == 0:
        return None
    
    if assignment.is_repeating:
        day_in_pattern = days_since_start % total_pattern_days
    else:
        if days_since_start >= total_pattern_days:
            return None
        day_in_pattern = days_since_start
    
    current_day = 0
    for info in phase_info:
        phase = info['phase']
        phase_total_days = info['total_days']
        phase_cycle_days = info['cycle_days']
        
        if current_day + phase_total_days > day_in_pattern:
            day_within_phase = day_in_pattern - current_day
            day_within_cycle = day_within_phase % phase_cycle_days
            
            if day_within_cycle < phase.days_on:
                return (phase.start_time, phase.end_time, True)
            else:
                return (phase.start_time, phase.end_time, False)
        
        current_day += phase_total_days
    
    return None


@router.get("/engineer-availability")
async def get_engineer_availability_view(
    date: str,
    engineer_id: int = None,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """Get all engineers' availability for a given date for the Gantt-style view."""
    await get_admin_user(authorization, db)
    
    try:
        target_date = datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid date format. Use YYYY-MM-DD"
        )
    
    day_of_week = target_date.weekday()
    day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    
    query = select(Engineer).options(
        selectinload(Engineer.user),
        selectinload(Engineer.schedules),
        selectinload(Engineer.roster_assignments).selectinload(EngineerRosterAssignment.pattern).selectinload(RosterPattern.phases)
    )
    if engineer_id:
        query = query.where(Engineer.id == engineer_id)
    
    result = await db.execute(query)
    engineers = result.scalars().all()
    
    start_of_day = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_day = target_date.replace(hour=23, minute=59, second=59, microsecond=999999)
    previous_date = target_date - timedelta(days=1)
    
    engineer_data = []
    
    for engineer in engineers:
        working_start = None
        working_end = None
        is_working = False
        overnight_continuation_end = None
        
        # Check for active roster assignment first
        active_roster = None
        for ra in engineer.roster_assignments:
            if ra.is_active:
                active_roster = ra
                break
        
        if active_roster:
            roster_result = calculate_roster_for_date(active_roster, target_date)
            
            # Check if previous day had an overnight shift that continues into today
            prev_roster_result = calculate_roster_for_date(active_roster, previous_date)
            if prev_roster_result:
                prev_start_time, prev_end_time, prev_is_working = prev_roster_result
                if prev_is_working and is_overnight_shift_check(prev_start_time, prev_end_time):
                    overnight_continuation_end = prev_end_time
            
            if roster_result:
                start_time, end_time, roster_is_working = roster_result
                if roster_is_working:
                    working_start = start_time
                    working_end = end_time
                    is_working = True
                else:
                    # Day off but might have overnight continuation
                    if overnight_continuation_end:
                        working_start = "00:00"
                        working_end = overnight_continuation_end
                        is_working = True
            else:
                # Roster doesn't apply - fall back to schedule
                schedule = None
                for s in engineer.schedules:
                    if s.day_of_week == day_of_week:
                        schedule = s
                        break
                
                if schedule:
                    if schedule.is_working:
                        working_start = schedule.start_time
                        working_end = schedule.end_time
                        is_working = True
                else:
                    if day_of_week < 5:
                        working_start = engineer.working_hours_start
                        working_end = engineer.working_hours_end
                        is_working = True
        else:
            # No roster - use schedule
            schedule = None
            for s in engineer.schedules:
                if s.day_of_week == day_of_week:
                    schedule = s
                    break
            
            if schedule:
                if schedule.is_working:
                    working_start = schedule.start_time
                    working_end = schedule.end_time
                    is_working = True
            else:
                if day_of_week < 5:
                    working_start = engineer.working_hours_start
                    working_end = engineer.working_hours_end
                    is_working = True
        
        bookings_result = await db.execute(
            select(Booking).where(
                Booking.engineer_id == engineer.id,
                Booking.scheduled_date >= start_of_day,
                Booking.scheduled_date <= end_of_day,
                Booking.status.in_([BookingStatus.PENDING, BookingStatus.CONFIRMED, BookingStatus.DELAYED])
            ).options(
                selectinload(Booking.product),
                selectinload(Booking.change_type)
            )
        )
        bookings = bookings_result.scalars().all()
        
        booked_slots = []
        for booking in bookings:
            booking_start = booking.scheduled_date
            booking_end = booking.scheduled_date + timedelta(hours=booking.duration_hours)
            booked_slots.append({
                "booking_id": booking.id,
                "order_reference": booking.order_reference,
                "customer_name": booking.customer_name,
                "start_time": booking_start.strftime("%H:%M"),
                "end_time": booking_end.strftime("%H:%M"),
                "duration_hours": booking.duration_hours,
                "status": booking.status.value,
                "product_name": booking.product.name if booking.product else None,
                "change_type_name": booking.change_type.name if booking.change_type else None
            })
        
        unavailability_result = await db.execute(
            select(EngineerUnavailability).where(
                EngineerUnavailability.engineer_id == engineer.id,
                EngineerUnavailability.start_datetime <= end_of_day,
                EngineerUnavailability.end_datetime >= start_of_day
            )
        )
        unavailability_entries = unavailability_result.scalars().all()
        
        unavailable_slots = []
        for entry in unavailability_entries:
            entry_start = max(entry.start_datetime, start_of_day)
            entry_end = min(entry.end_datetime, end_of_day)
            unavailable_slots.append({
                "id": entry.id,
                "start_time": entry_start.strftime("%H:%M"),
                "end_time": entry_end.strftime("%H:%M"),
                "reason": entry.reason,
                "is_all_day": entry.is_all_day
            })
        
        engineer_data.append({
            "engineer_id": engineer.id,
            "engineer_name": engineer.user.full_name if engineer.user else "Unknown",
            "calendar_email": engineer.calendar_email,
            "is_available": engineer.is_available,
            "is_working": is_working,
            "working_start": working_start,
            "working_end": working_end,
            "overnight_continuation_end": overnight_continuation_end,
            "day_name": day_names[day_of_week],
            "booked_slots": booked_slots,
            "unavailable_slots": unavailable_slots
        })
    
    return {
        "date": date,
        "day_name": day_names[day_of_week],
        "engineers": engineer_data
    }
