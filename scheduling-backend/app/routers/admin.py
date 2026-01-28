from fastapi import APIRouter, Depends, HTTPException, status, Header, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from sqlalchemy.exc import IntegrityError
from typing import List
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
    EmailRule, EmailRuleSentLog, EmailRuleTriggerType, EmailRuleRecipientType
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
    EmailRuleCreate, EmailRuleUpdate, EmailRuleResponse, EmailRuleSentLogResponse
)
from app.services.auth import decode_access_token

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
    
    total_bookings = await db.execute(select(func.count(Booking.id)))
    pending_bookings = await db.execute(
        select(func.count(Booking.id)).where(Booking.status == BookingStatus.PENDING)
    )
    confirmed_bookings = await db.execute(
        select(func.count(Booking.id)).where(Booking.status == BookingStatus.CONFIRMED)
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
        minimum_notice_hours=change_type_data.minimum_notice_hours or 0
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
        select(Engineer).where(Engineer.id == engineer.id).options(selectinload(Engineer.user))
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
        apply_mode=apply_mode
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
        change_type_ids=[a.change_type_id for a in fee.change_type_assignments]
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
            change_type_ids=[a.change_type_id for a in f.change_type_assignments]
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


@router.get("/fees/pending-approvals", response_model=List[BookingFeeResponse])
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
@router.get("/templates/placeholders", response_model=TemplatePlaceholders)
async def get_template_placeholders(
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """Get available placeholders for templates"""
    await get_admin_user(authorization, db)
    return TemplatePlaceholders()


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
        selectinload(ExpediteRequest.product),
        selectinload(ExpediteRequest.change_type),
        selectinload(ExpediteRequest.assigned_engineer).selectinload(Engineer.user)
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
            selectinload(ExpediteRequest.assigned_engineer).selectinload(Engineer.user)
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
            selectinload(ExpediteRequest.assigned_engineer).selectinload(Engineer.user)
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
        selectinload(ExpediteRequest.product),
        selectinload(ExpediteRequest.change_type),
        selectinload(ExpediteRequest.assigned_engineer).selectinload(Engineer.user)
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
    """Get revenue summary report"""
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
    
    return {
        "total_bookings": row[0] or 0,
        "total_expedite_fees": float(row[1] or 0),
        "total_cancellation_fees": float(row[2] or 0),
        "status_breakdown": status_breakdown,
        "approved_expedite_requests": expedite_row[0] or 0,
        "expedite_request_fees": float(expedite_row[1] or 0),
    }


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
