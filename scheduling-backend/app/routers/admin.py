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
    ExpediteRequest, ExpediteRequestStatus
)
from app.schemas.schemas import (
    ProductCreate, ProductUpdate, ProductResponse, ChangeTypeCreate, ChangeTypeResponse,
    EngineerCreate, EngineerResponse, EngineerSkillCreate, EngineerSkillResponse,
    CustomFieldCreate, CustomFieldResponse, FeeCreate, FeeResponse,
    SystemConfigUpdate, SystemConfigResponse, DashboardStats, UserResponse,
    EngineerScheduleCreate, EngineerScheduleResponse, EngineerScheduleUpdate,
    EmailTemplateCreate, EmailTemplateResponse, CalendarEventTemplateCreate,
    CalendarEventTemplateResponse, TemplatePlaceholders,
    RosterPatternCreate, RosterPatternUpdate, RosterPatternResponse,
    RosterPhaseCreate, RosterPhaseResponse, RosterPatternListResponse,
    EngineerRosterAssignmentCreate, EngineerRosterAssignmentResponse,
    ExpediteRequestCreate, ExpediteRequestApprove, ExpediteRequestReject, ExpediteRequestResponse
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
    
    return DashboardStats(
        total_bookings=total_bookings.scalar() or 0,
        pending_bookings=pending_bookings.scalar() or 0,
        confirmed_bookings=confirmed_bookings.scalar() or 0,
        total_engineers=total_engineers.scalar() or 0,
        available_engineers=available_engineers.scalar() or 0
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
    
    change_type = ChangeType(name=change_type_data.name, description=change_type_data.description)
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


@router.patch("/change-types/{change_type_id}")
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
    await db.commit()
    return {"message": "Change type updated successfully"}


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
    
    fee = Fee(
        name=fee_data.name,
        fee_type=fee_data.fee_type,
        amount=fee_data.amount,
        description=fee_data.description
    )
    db.add(fee)
    await db.commit()
    await db.refresh(fee)
    return FeeResponse.model_validate(fee)


@router.get("/fees", response_model=List[FeeResponse])
async def get_fees(
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    await get_admin_user(authorization, db)
    
    result = await db.execute(select(Fee).where(Fee.is_active == True))
    fees = result.scalars().all()
    return [FeeResponse.model_validate(f) for f in fees]


@router.patch("/fees/{fee_id}")
async def update_fee(
    fee_id: int,
    fee_data: FeeCreate,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    await get_admin_user(authorization, db)
    
    result = await db.execute(select(Fee).where(Fee.id == fee_id))
    fee = result.scalar_one_or_none()
    if not fee:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fee not found")
    
    fee.name = fee_data.name
    fee.fee_type = fee_data.fee_type
    fee.amount = fee_data.amount
    fee.description = fee_data.description
    
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
