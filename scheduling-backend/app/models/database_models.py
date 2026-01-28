from sqlalchemy import Column, Integer, String, DateTime, Boolean, Float, ForeignKey, Text, JSON, Enum as SQLEnum
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

from app.database import Base


class UserRole(str, enum.Enum):
    USER = "user"
    ENGINEER = "engineer"
    ADMIN = "admin"


class BookingStatus(str, enum.Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


class ExpediteRequestStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=True)
    full_name = Column(String(255), nullable=False)
    role = Column(SQLEnum(UserRole), default=UserRole.USER)
    microsoft_id = Column(String(255), unique=True, nullable=True)
    microsoft_access_token = Column(Text, nullable=True)
    microsoft_refresh_token = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    bookings = relationship("Booking", back_populates="booker", foreign_keys="Booking.booker_id")
    engineer_profile = relationship("Engineer", back_populates="user", uselist=False)


class Engineer(Base):
    __tablename__ = "engineers"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    calendar_email = Column(String(255), nullable=False)
    is_available = Column(Boolean, default=True)
    working_hours_start = Column(String(10), default="09:00")
    working_hours_end = Column(String(10), default="17:00")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="engineer_profile")
    skills = relationship("EngineerSkill", back_populates="engineer", cascade="all, delete-orphan")
    bookings = relationship("Booking", back_populates="engineer")
    schedules = relationship("EngineerSchedule", back_populates="engineer", cascade="all, delete-orphan")
    roster_assignments = relationship("EngineerRosterAssignment", back_populates="engineer", cascade="all, delete-orphan")
    unavailability_entries = relationship("EngineerUnavailability", back_populates="engineer", cascade="all, delete-orphan")


class EngineerSchedule(Base):
    """Defines working hours for each day of the week for an engineer"""
    __tablename__ = "engineer_schedules"

    id = Column(Integer, primary_key=True, index=True)
    engineer_id = Column(Integer, ForeignKey("engineers.id"), nullable=False)
    day_of_week = Column(Integer, nullable=False)  # 0=Monday, 1=Tuesday, ..., 6=Sunday
    is_working = Column(Boolean, default=True)
    start_time = Column(String(10), default="09:00")  # HH:MM format
    end_time = Column(String(10), default="17:00")  # HH:MM format
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    engineer = relationship("Engineer", back_populates="schedules")


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, nullable=False)
    description = Column(Text, nullable=True)
    expedite_fee = Column(Float, default=0.0)  # Fee for expedite requests
    expedite_contact_emails = Column(JSON, nullable=True)  # List of email addresses for expedite notifications
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    skills = relationship("EngineerSkill", back_populates="product")
    bookings = relationship("Booking", back_populates="product")
    expedite_requests = relationship("ExpediteRequest", back_populates="product")
    fee_assignments = relationship("FeeProductAssignment", back_populates="product", cascade="all, delete-orphan")


class ChangeType(Base):
    __tablename__ = "change_types"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, nullable=False)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    skills = relationship("EngineerSkill", back_populates="change_type")
    bookings = relationship("Booking", back_populates="change_type")
    fee_assignments = relationship("FeeChangeTypeAssignment", back_populates="change_type", cascade="all, delete-orphan")


class EngineerSkill(Base):
    __tablename__ = "engineer_skills"

    id = Column(Integer, primary_key=True, index=True)
    engineer_id = Column(Integer, ForeignKey("engineers.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    change_type_id = Column(Integer, ForeignKey("change_types.id"), nullable=False)
    proficiency_level = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)

    engineer = relationship("Engineer", back_populates="skills")
    product = relationship("Product", back_populates="skills")
    change_type = relationship("ChangeType", back_populates="skills")


class CustomField(Base):
    __tablename__ = "custom_fields"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    field_type = Column(String(50), nullable=False)
    is_required = Column(Boolean, default=False)
    options = Column(JSON, nullable=True)
    display_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Booking(Base):
    __tablename__ = "bookings"

    id = Column(Integer, primary_key=True, index=True)
    order_reference = Column(String(255), nullable=False, index=True)
    customer_name = Column(String(255), nullable=False)
    booker_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    engineer_id = Column(Integer, ForeignKey("engineers.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    change_type_id = Column(Integer, ForeignKey("change_types.id"), nullable=False)
    scheduled_date = Column(DateTime, nullable=False)
    duration_hours = Column(Float, nullable=False)
    status = Column(SQLEnum(BookingStatus), default=BookingStatus.PENDING)
    custom_fields_data = Column(JSON, nullable=True)
    outlook_event_id = Column(String(255), nullable=True)
    sharepoint_item_id = Column(String(255), nullable=True)
    notes = Column(Text, nullable=True)
    additional_emails = Column(JSON, nullable=True)  # List of additional email addresses for notifications
    engineer_attachment_url = Column(String(1000), nullable=True)  # Attachment URL for engineer confirmation email
    customer_attachment_url = Column(String(1000), nullable=True)  # Attachment URL for customer confirmation email
    cancellation_fee = Column(Float, default=0.0)
    expedite_fee = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    booker = relationship("User", back_populates="bookings", foreign_keys=[booker_id])
    engineer = relationship("Engineer", back_populates="bookings")
    product = relationship("Product", back_populates="bookings")
    change_type = relationship("ChangeType", back_populates="bookings")
    status_updates = relationship("BookingStatusUpdate", back_populates="booking", cascade="all, delete-orphan")
    fees = relationship("BookingFee", back_populates="booking", cascade="all, delete-orphan")


class SystemConfig(Base):
    __tablename__ = "system_config"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(255), unique=True, nullable=False)
    value = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class FeeApplyMode(str, enum.Enum):
    AUTO = "auto"  # Automatically applied to bookings
    APPROVAL = "approval"  # Requires admin approval before applying


class Fee(Base):
    __tablename__ = "fees"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    fee_type = Column(String(50), nullable=False)
    amount = Column(Float, nullable=False)
    description = Column(Text, nullable=True)
    apply_mode = Column(SQLEnum(FeeApplyMode, values_callable=lambda x: [e.value for e in x]), default=FeeApplyMode.AUTO)  # Auto or requires approval
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    product_assignments = relationship("FeeProductAssignment", back_populates="fee", cascade="all, delete-orphan")
    change_type_assignments = relationship("FeeChangeTypeAssignment", back_populates="fee", cascade="all, delete-orphan")


class FeeProductAssignment(Base):
    """Links fees to specific products"""
    __tablename__ = "fee_product_assignments"

    id = Column(Integer, primary_key=True, index=True)
    fee_id = Column(Integer, ForeignKey("fees.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    fee = relationship("Fee", back_populates="product_assignments")
    product = relationship("Product", back_populates="fee_assignments")


class FeeChangeTypeAssignment(Base):
    """Links fees to specific change types"""
    __tablename__ = "fee_change_type_assignments"

    id = Column(Integer, primary_key=True, index=True)
    fee_id = Column(Integer, ForeignKey("fees.id"), nullable=False)
    change_type_id = Column(Integer, ForeignKey("change_types.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    fee = relationship("Fee", back_populates="change_type_assignments")
    change_type = relationship("ChangeType", back_populates="fee_assignments")


class BookingFeeStatus(str, enum.Enum):
    PENDING = "pending"  # Fee requires admin approval
    APPROVED = "approved"  # Fee approved and applied
    WAIVED = "waived"  # Fee waived by admin


class BookingFee(Base):
    """Individual fees applied to bookings with approval/waiver tracking"""
    __tablename__ = "booking_fees"

    id = Column(Integer, primary_key=True, index=True)
    booking_id = Column(Integer, ForeignKey("bookings.id"), nullable=False)
    fee_id = Column(Integer, ForeignKey("fees.id"), nullable=False)
    amount = Column(Float, nullable=False)  # Amount at time of application (may differ from fee.amount)
    status = Column(SQLEnum(BookingFeeStatus, values_callable=lambda x: [e.value for e in x]), default=BookingFeeStatus.APPROVED)
    waived_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # Admin who waived the fee
    waiver_reason = Column(Text, nullable=True)
    approved_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # Admin who approved (if approval required)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    booking = relationship("Booking", back_populates="fees")
    fee = relationship("Fee")
    waived_by = relationship("User", foreign_keys=[waived_by_id])
    approved_by = relationship("User", foreign_keys=[approved_by_id])


class TemplateType(str, enum.Enum):
    CONFIRMATION = "confirmation"
    AMENDMENT = "amendment"
    CANCELLATION = "cancellation"
    REMINDER = "reminder"


class EmailTemplate(Base):
    """Email templates with booking field placeholders"""
    __tablename__ = "email_templates"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    template_type = Column(SQLEnum(TemplateType), nullable=False)
    subject = Column(String(500), nullable=False)
    body_html = Column(Text, nullable=False)
    logo_url = Column(String(1000), nullable=True)  # URL for company logo in email header
    send_to_engineer = Column(Boolean, default=True)
    send_to_customer = Column(Boolean, default=True)
    additional_emails = Column(JSON, nullable=True)  # List of additional email addresses
    is_active = Column(Boolean, default=True)
    is_default = Column(Boolean, default=False)  # Default template for this type
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class CalendarEventTemplate(Base):
    """Calendar event templates for Outlook"""
    __tablename__ = "calendar_event_templates"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    template_type = Column(SQLEnum(TemplateType), nullable=False)
    event_title = Column(String(500), nullable=False)
    event_body = Column(Text, nullable=True)
    include_customer_as_attendee = Column(Boolean, default=False)
    additional_attendees = Column(JSON, nullable=True)  # List of additional attendee emails
    is_teams_meeting = Column(Boolean, default=False)  # Create as Microsoft Teams meeting
    is_active = Column(Boolean, default=True)
    is_default = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class RosterPattern(Base):
    """Reusable roster patterns that can be assigned to engineers"""
    __tablename__ = "roster_patterns"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    phases = relationship("RosterPhase", back_populates="pattern", cascade="all, delete-orphan", order_by="RosterPhase.phase_order")
    assignments = relationship("EngineerRosterAssignment", back_populates="pattern", cascade="all, delete-orphan")


class RosterPhase(Base):
    """A phase within a roster pattern (e.g., 3 days on, 4 days off)"""
    __tablename__ = "roster_phases"

    id = Column(Integer, primary_key=True, index=True)
    pattern_id = Column(Integer, ForeignKey("roster_patterns.id"), nullable=False)
    phase_order = Column(Integer, nullable=False)  # Order of this phase in the pattern
    name = Column(String(255), nullable=True)  # Optional name like "Day Shift" or "Night Shift"
    days_on = Column(Integer, nullable=False)  # Number of working days
    days_off = Column(Integer, nullable=False)  # Number of off days after working days
    start_time = Column(String(10), nullable=False)  # HH:MM format
    end_time = Column(String(10), nullable=False)  # HH:MM format
    repeat_weeks = Column(Integer, nullable=True)  # How many weeks to repeat this phase (null = until next phase)
    created_at = Column(DateTime, default=datetime.utcnow)

    pattern = relationship("RosterPattern", back_populates="phases")


class EngineerRosterAssignment(Base):
    """Assigns a roster pattern to an engineer with start/end dates"""
    __tablename__ = "engineer_roster_assignments"

    id = Column(Integer, primary_key=True, index=True)
    engineer_id = Column(Integer, ForeignKey("engineers.id"), nullable=False)
    pattern_id = Column(Integer, ForeignKey("roster_patterns.id"), nullable=False)
    start_date = Column(DateTime, nullable=False)  # When this pattern starts
    end_date = Column(DateTime, nullable=True)  # When this pattern ends (null = continuous)
    is_repeating = Column(Boolean, default=True)  # Whether to repeat the full pattern cycle
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    engineer = relationship("Engineer", back_populates="roster_assignments")
    pattern = relationship("RosterPattern", back_populates="assignments")


class EngineerUnavailability(Base):
    """Manual unavailability entries for engineers that override Outlook calendar"""
    __tablename__ = "engineer_unavailability"

    id = Column(Integer, primary_key=True, index=True)
    engineer_id = Column(Integer, ForeignKey("engineers.id"), nullable=False)
    start_datetime = Column(DateTime, nullable=False)
    end_datetime = Column(DateTime, nullable=False)
    reason = Column(String(500), nullable=True)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)  # Who created this entry
    is_all_day = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    engineer = relationship("Engineer", back_populates="unavailability_entries")
    created_by = relationship("User", foreign_keys=[created_by_id])


class BookingStatusUpdate(Base):
    """Status updates and notes from engineers for bookings"""
    __tablename__ = "booking_status_updates"

    id = Column(Integer, primary_key=True, index=True)
    booking_id = Column(Integer, ForeignKey("bookings.id"), nullable=False)
    updated_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    previous_status = Column(SQLEnum(BookingStatus), nullable=True)
    new_status = Column(SQLEnum(BookingStatus), nullable=False)
    notes = Column(Text, nullable=True)
    issue_reported = Column(Boolean, default=False)
    issue_description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    booking = relationship("Booking", back_populates="status_updates")
    updated_by = relationship("User", foreign_keys=[updated_by_id])


class ExpediteRequest(Base):
    """Expedite requests for bookings when no availability exists"""
    __tablename__ = "expedite_requests"

    id = Column(Integer, primary_key=True, index=True)
    requester_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    change_type_id = Column(Integer, ForeignKey("change_types.id"), nullable=False)
    order_reference = Column(String(255), nullable=False)
    customer_name = Column(String(255), nullable=False)
    requested_date = Column(DateTime, nullable=False)
    duration_hours = Column(Float, nullable=False)
    custom_fields_data = Column(JSON, nullable=True)
    notes = Column(Text, nullable=True)
    additional_emails = Column(JSON, nullable=True)
    engineer_attachment_url = Column(String(1000), nullable=True)
    customer_attachment_url = Column(String(1000), nullable=True)
    expedite_fee = Column(Float, nullable=False)
    fee_acknowledged = Column(Boolean, default=False)
    status = Column(SQLEnum(ExpediteRequestStatus), default=ExpediteRequestStatus.PENDING)
    admin_notes = Column(Text, nullable=True)
    assigned_engineer_id = Column(Integer, ForeignKey("engineers.id"), nullable=True)
    resulting_booking_id = Column(Integer, ForeignKey("bookings.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    requester = relationship("User", foreign_keys=[requester_id])
    product = relationship("Product", back_populates="expedite_requests")
    change_type = relationship("ChangeType")
    assigned_engineer = relationship("Engineer", foreign_keys=[assigned_engineer_id])
    resulting_booking = relationship("Booking", foreign_keys=[resulting_booking_id])
