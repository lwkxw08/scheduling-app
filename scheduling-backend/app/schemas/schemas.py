from pydantic import BaseModel, EmailStr
from typing import Optional, List, Any
from datetime import datetime
from enum import Enum


class UserRole(str, Enum):
    USER = "user"
    ENGINEER = "engineer"
    ADMIN = "admin"


class BookingStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: int
    email: str
    full_name: str
    role: UserRole
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    user: UserResponse


class MicrosoftAuthRequest(BaseModel):
    code: str
    redirect_uri: str


class ProductCreate(BaseModel):
    name: str
    description: Optional[str] = None
    expedite_fee: Optional[float] = 0.0
    expedite_contact_emails: Optional[List[str]] = None


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    expedite_fee: Optional[float] = None
    expedite_contact_emails: Optional[List[str]] = None


class ProductResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    expedite_fee: float
    expedite_contact_emails: Optional[List[str]]
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class ChangeTypeCreate(BaseModel):
    name: str
    description: Optional[str] = None
    minimum_notice_hours: Optional[int] = 0  # Minimum notice period in hours (0 = no minimum)


class ChangeTypeUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    minimum_notice_hours: Optional[int] = None


class ChangeTypeResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    minimum_notice_hours: int
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class EngineerScheduleCreate(BaseModel):
    day_of_week: int  # 0=Monday, 1=Tuesday, ..., 6=Sunday
    is_working: bool = True
    start_time: str = "09:00"
    end_time: str = "17:00"


class EngineerScheduleResponse(BaseModel):
    id: int
    engineer_id: int
    day_of_week: int
    is_working: bool
    start_time: str
    end_time: str

    class Config:
        from_attributes = True


class EngineerCreate(BaseModel):
    user_id: int
    calendar_email: str
    working_hours_start: str = "09:00"
    working_hours_end: str = "17:00"
    schedules: Optional[List[EngineerScheduleCreate]] = None


class EngineerResponse(BaseModel):
    id: int
    user_id: int
    calendar_email: str
    is_available: bool
    working_hours_start: str
    working_hours_end: str
    user: Optional[UserResponse] = None
    schedules: Optional[List[EngineerScheduleResponse]] = None

    class Config:
        from_attributes = True


class EngineerScheduleUpdate(BaseModel):
    schedules: List[EngineerScheduleCreate]


class EngineerSkillCreate(BaseModel):
    engineer_id: int
    product_id: int
    change_type_id: int
    proficiency_level: int = 1


class EngineerSkillResponse(BaseModel):
    id: int
    engineer_id: int
    product_id: int
    change_type_id: int
    proficiency_level: int
    product: Optional[ProductResponse] = None
    change_type: Optional[ChangeTypeResponse] = None

    class Config:
        from_attributes = True


class CustomFieldCreate(BaseModel):
    name: str
    field_type: str
    is_required: bool = False
    options: Optional[List[str]] = None
    display_order: int = 0


class CustomFieldResponse(BaseModel):
    id: int
    name: str
    field_type: str
    is_required: bool
    options: Optional[List[str]]
    display_order: int
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class BookingCreate(BaseModel):
    order_reference: str
    customer_name: str
    engineer_id: int
    product_id: int
    change_type_id: int
    scheduled_date: datetime
    duration_hours: float
    custom_fields_data: Optional[dict] = None
    notes: Optional[str] = None
    additional_emails: Optional[List[str]] = None
    engineer_attachment_url: Optional[str] = None
    customer_attachment_url: Optional[str] = None
    is_expedited: bool = False


class BookingUpdate(BaseModel):
    scheduled_date: Optional[datetime] = None
    duration_hours: Optional[float] = None
    notes: Optional[str] = None
    custom_fields_data: Optional[dict] = None
    additional_emails: Optional[List[str]] = None
    engineer_attachment_url: Optional[str] = None
    customer_attachment_url: Optional[str] = None


class BookingResponse(BaseModel):
    id: int
    order_reference: str
    customer_name: str
    booker_id: int
    engineer_id: int
    product_id: int
    change_type_id: int
    scheduled_date: datetime
    duration_hours: float
    status: BookingStatus
    custom_fields_data: Optional[dict]
    notes: Optional[str]
    additional_emails: Optional[List[str]]
    engineer_attachment_url: Optional[str]
    customer_attachment_url: Optional[str]
    cancellation_fee: float
    expedite_fee: float
    created_at: datetime
    updated_at: datetime
    engineer: Optional[EngineerResponse] = None
    product: Optional[ProductResponse] = None
    change_type: Optional[ChangeTypeResponse] = None

    class Config:
        from_attributes = True


class AvailabilityRequest(BaseModel):
    date: str
    product_id: int
    change_type_id: int
    duration_hours: float


class TimeSlot(BaseModel):
    start_time: str
    end_time: str
    is_available: bool


class EngineerAvailability(BaseModel):
    engineer_id: int
    engineer_name: str
    calendar_email: str
    slots: List[TimeSlot]


class AvailabilityResponse(BaseModel):
    date: str
    engineers: List[EngineerAvailability]


class FeeApplyMode(str, Enum):
    AUTO = "auto"
    APPROVAL = "approval"


class FeeCreate(BaseModel):
    name: str
    fee_type: str
    amount: float
    description: Optional[str] = None
    apply_mode: FeeApplyMode = FeeApplyMode.AUTO
    product_ids: Optional[List[int]] = None  # Products this fee applies to
    change_type_ids: Optional[List[int]] = None  # Change types this fee applies to


class FeeUpdate(BaseModel):
    name: Optional[str] = None
    fee_type: Optional[str] = None
    amount: Optional[float] = None
    description: Optional[str] = None
    apply_mode: Optional[FeeApplyMode] = None
    product_ids: Optional[List[int]] = None
    change_type_ids: Optional[List[int]] = None


class FeeResponse(BaseModel):
    id: int
    name: str
    fee_type: str
    amount: float
    description: Optional[str]
    apply_mode: FeeApplyMode
    is_active: bool
    created_at: datetime
    product_ids: Optional[List[int]] = None
    change_type_ids: Optional[List[int]] = None

    class Config:
        from_attributes = True


class BookingFeeStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    WAIVED = "waived"


class BookingFeeCreate(BaseModel):
    fee_id: int
    amount: Optional[float] = None  # If not provided, uses fee.amount


class BookingFeeResponse(BaseModel):
    id: int
    booking_id: int
    fee_id: int
    amount: float
    status: BookingFeeStatus
    waived_by_id: Optional[int]
    waiver_reason: Optional[str]
    approved_by_id: Optional[int]
    created_at: datetime
    fee_name: Optional[str] = None
    fee_type: Optional[str] = None

    class Config:
        from_attributes = True


class BookingFeeWaive(BaseModel):
    waiver_reason: Optional[str] = None


class BookingFeeApprove(BaseModel):
    pass  # No additional fields needed


class SystemConfigUpdate(BaseModel):
    key: str
    value: str
    description: Optional[str] = None


class SystemConfigResponse(BaseModel):
    id: int
    key: str
    value: str
    description: Optional[str]
    updated_at: datetime

    class Config:
        from_attributes = True


class DashboardStats(BaseModel):
    total_bookings: int
    pending_bookings: int
    confirmed_bookings: int
    total_engineers: int
    available_engineers: int
    pending_expedite_requests: int


class TemplateType(str, Enum):
    CONFIRMATION = "confirmation"
    AMENDMENT = "amendment"
    CANCELLATION = "cancellation"
    REMINDER = "reminder"


class EmailTemplateCreate(BaseModel):
    name: str
    template_type: TemplateType
    subject: str
    body_html: str
    logo_url: Optional[str] = None
    send_to_engineer: bool = True
    send_to_customer: bool = True
    additional_emails: Optional[List[str]] = None
    is_default: bool = False


class EmailTemplateUpdate(BaseModel):
    name: Optional[str] = None
    template_type: Optional[TemplateType] = None
    subject: Optional[str] = None
    body_html: Optional[str] = None
    logo_url: Optional[str] = None
    send_to_engineer: Optional[bool] = None
    send_to_customer: Optional[bool] = None
    additional_emails: Optional[List[str]] = None
    is_default: Optional[bool] = None


class EmailTemplateResponse(BaseModel):
    id: int
    name: str
    template_type: TemplateType
    subject: str
    body_html: str
    logo_url: Optional[str]
    send_to_engineer: bool
    send_to_customer: bool
    additional_emails: Optional[List[str]]
    is_active: bool
    is_default: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CalendarEventTemplateCreate(BaseModel):
    name: str
    template_type: TemplateType
    event_title: str
    event_body: Optional[str] = None
    include_customer_as_attendee: bool = False
    additional_attendees: Optional[List[str]] = None
    is_teams_meeting: bool = False
    is_default: bool = False


class CalendarEventTemplateResponse(BaseModel):
    id: int
    name: str
    template_type: TemplateType
    event_title: str
    event_body: Optional[str]
    include_customer_as_attendee: bool
    additional_attendees: Optional[List[str]]
    is_teams_meeting: bool
    is_active: bool
    is_default: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TemplatePlaceholders(BaseModel):
    """Available placeholders for templates"""
    booking_fields: List[str] = [
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
        "{{cancellation_fee}}",
        "{{expedite_fee}}",
    ]


# Roster Pattern Schemas
class RosterPhaseCreate(BaseModel):
    phase_order: int
    name: Optional[str] = None
    days_on: int
    days_off: int
    start_time: str  # HH:MM format
    end_time: str  # HH:MM format
    repeat_weeks: Optional[int] = None  # How many weeks to repeat this phase


class RosterPhaseResponse(BaseModel):
    id: int
    pattern_id: int
    phase_order: int
    name: Optional[str]
    days_on: int
    days_off: int
    start_time: str
    end_time: str
    repeat_weeks: Optional[int]
    created_at: datetime

    class Config:
        from_attributes = True


class RosterPatternCreate(BaseModel):
    name: str
    description: Optional[str] = None
    phases: List[RosterPhaseCreate]


class RosterPatternUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    phases: Optional[List[RosterPhaseCreate]] = None


class RosterPatternResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    is_active: bool
    phases: List[RosterPhaseResponse]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class EngineerRosterAssignmentCreate(BaseModel):
    engineer_id: int
    pattern_id: int
    start_date: datetime
    end_date: Optional[datetime] = None  # None = continuous
    is_repeating: bool = True


class EngineerRosterAssignmentResponse(BaseModel):
    id: int
    engineer_id: int
    pattern_id: int
    start_date: datetime
    end_date: Optional[datetime]
    is_repeating: bool
    is_active: bool
    pattern: Optional[RosterPatternResponse] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class RosterPatternListResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    is_active: bool
    phase_count: int
    created_at: datetime

    class Config:
        from_attributes = True


# Expedite Request Schemas
class ExpediteRequestStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class ExpediteRequestCreate(BaseModel):
    product_id: int
    change_type_id: int
    order_reference: str
    customer_name: str
    requested_date: datetime
    duration_hours: float
    custom_fields_data: Optional[dict] = None
    notes: Optional[str] = None
    additional_emails: Optional[List[str]] = None
    engineer_attachment_url: Optional[str] = None
    customer_attachment_url: Optional[str] = None
    fee_acknowledged: bool = True


class ExpediteRequestApprove(BaseModel):
    assigned_engineer_id: int
    scheduled_date: datetime
    admin_notes: Optional[str] = None


class ExpediteRequestReject(BaseModel):
    admin_notes: Optional[str] = None


class ExpediteRequestResponse(BaseModel):
    id: int
    requester_id: int
    product_id: int
    change_type_id: int
    order_reference: str
    customer_name: str
    requested_date: datetime
    duration_hours: float
    custom_fields_data: Optional[dict]
    notes: Optional[str]
    additional_emails: Optional[List[str]]
    engineer_attachment_url: Optional[str]
    customer_attachment_url: Optional[str]
    expedite_fee: float
    fee_acknowledged: bool
    status: ExpediteRequestStatus
    admin_notes: Optional[str]
    assigned_engineer_id: Optional[int]
    resulting_booking_id: Optional[int]
    created_at: datetime
    updated_at: datetime
    requester: Optional[UserResponse] = None
    product: Optional[ProductResponse] = None
    change_type: Optional[ChangeTypeResponse] = None
    assigned_engineer: Optional[EngineerResponse] = None

    class Config:
        from_attributes = True


# Engineer Unavailability Schemas
class EngineerUnavailabilityCreate(BaseModel):
    engineer_id: int
    start_datetime: datetime
    end_datetime: datetime
    reason: Optional[str] = None
    is_all_day: bool = False


class EngineerUnavailabilityResponse(BaseModel):
    id: int
    engineer_id: int
    start_datetime: datetime
    end_datetime: datetime
    reason: Optional[str] = None
    created_by_id: int
    is_all_day: bool
    created_at: datetime
    updated_at: Optional[datetime] = None
    engineer: Optional[EngineerResponse] = None
    created_by: Optional[UserResponse] = None

    class Config:
        from_attributes = True


# Booking Status Update Schemas
class BookingStatusUpdateCreate(BaseModel):
    new_status: BookingStatus
    notes: Optional[str] = None
    issue_reported: bool = False
    issue_description: Optional[str] = None


class BookingStatusUpdateResponse(BaseModel):
    id: int
    booking_id: int
    updated_by_id: int
    previous_status: Optional[BookingStatus]
    new_status: BookingStatus
    notes: Optional[str]
    issue_reported: bool
    issue_description: Optional[str]
    created_at: datetime
    updated_by: Optional[UserResponse] = None

    class Config:
        from_attributes = True


# Engineer Dashboard Stats
class EngineerDashboardStats(BaseModel):
    total_bookings: int
    upcoming_bookings: int
    completed_bookings: int
    pending_bookings: int
    issues_reported: int


# Email Rules
class EmailRuleTriggerType(str, Enum):
    TIME_BEFORE_BOOKING = "time_before_booking"
    TIME_AFTER_BOOKING_CREATED = "time_after_booking_created"
    STATUS_IS = "status_is"


class EmailRuleRecipientType(str, Enum):
    ENGINEER = "engineer"
    CUSTOMER = "customer"
    BOOKER = "booker"
    ADDITIONAL = "additional"


class EmailRuleCreate(BaseModel):
    name: str
    description: Optional[str] = None
    trigger_type: EmailRuleTriggerType
    trigger_hours: Optional[int] = None
    condition_status: Optional[BookingStatus] = None
    email_template_id: int
    recipient_types: List[str]
    additional_emails: Optional[List[str]] = None
    is_active: bool = True


class EmailRuleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    trigger_type: Optional[EmailRuleTriggerType] = None
    trigger_hours: Optional[int] = None
    condition_status: Optional[BookingStatus] = None
    email_template_id: Optional[int] = None
    recipient_types: Optional[List[str]] = None
    additional_emails: Optional[List[str]] = None
    is_active: Optional[bool] = None


class EmailRuleResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    trigger_type: str
    trigger_hours: Optional[int]
    condition_status: Optional[str]
    email_template_id: int
    email_template_name: Optional[str] = None
    recipient_types: List[str]
    additional_emails: Optional[List[str]]
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class EmailRuleSentLogResponse(BaseModel):
    id: int
    rule_id: int
    booking_id: int
    sent_at: datetime
    recipient_email: str
    success: bool
    error_message: Optional[str]

    class Config:
        from_attributes = True
