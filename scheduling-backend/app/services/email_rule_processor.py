"""
Email Rule Processor Service

This service processes email rules and sends automated emails based on configured triggers.
It runs periodically to check for bookings that match rule conditions.
"""

import asyncio
from datetime import datetime, timedelta
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload

from app.models.database_models import (
    EmailRule, EmailRuleSentLog, EmailRuleTriggerType, EmailRuleRecipientType,
    Booking, BookingStatus, EmailTemplate, Engineer
)
from app.services.email_service import (
    get_smtp_config, is_smtp_configured, replace_placeholders, 
    build_booking_data, send_smtp_email
)


async def get_active_rules(db: AsyncSession) -> List[EmailRule]:
    """Get all active email rules"""
    result = await db.execute(
        select(EmailRule)
        .options(selectinload(EmailRule.email_template))
        .where(EmailRule.is_active == True)
    )
    return result.scalars().all()


async def has_email_been_sent(db: AsyncSession, rule_id: int, booking_id: int) -> bool:
    """Check if an email has already been sent for this rule and booking"""
    result = await db.execute(
        select(EmailRuleSentLog).where(
            and_(
                EmailRuleSentLog.rule_id == rule_id,
                EmailRuleSentLog.booking_id == booking_id,
                EmailRuleSentLog.success == True
            )
        )
    )
    return result.scalar_one_or_none() is not None


async def log_email_sent(
    db: AsyncSession, 
    rule_id: int, 
    booking_id: int, 
    recipient_email: str,
    success: bool = True,
    error_message: Optional[str] = None
):
    """Log that an email was sent (or attempted)"""
    log = EmailRuleSentLog(
        rule_id=rule_id,
        booking_id=booking_id,
        recipient_email=recipient_email,
        success=success,
        error_message=error_message
    )
    db.add(log)
    await db.commit()


async def get_bookings_for_time_before_rule(
    db: AsyncSession, 
    rule: EmailRule
) -> List[Booking]:
    """Get bookings that match a time_before_booking rule"""
    if not rule.trigger_hours:
        return []
    
    now = datetime.utcnow()
    target_time = now + timedelta(hours=rule.trigger_hours)
    
    # Find bookings scheduled within the next trigger_hours
    # We use a window to avoid missing bookings due to timing
    window_start = target_time - timedelta(minutes=30)
    window_end = target_time + timedelta(minutes=30)
    
    query = select(Booking).options(
        selectinload(Booking.engineer).selectinload(Engineer.user),
        selectinload(Booking.product),
        selectinload(Booking.change_type),
        selectinload(Booking.booker)
    ).where(
        and_(
            Booking.scheduled_date >= window_start,
            Booking.scheduled_date <= window_end,
            Booking.status != BookingStatus.CANCELLED
        )
    )
    
    # Add status condition if specified
    if rule.condition_status:
        query = query.where(Booking.status == rule.condition_status)
    
    result = await db.execute(query)
    return result.scalars().all()


async def get_bookings_for_time_after_created_rule(
    db: AsyncSession,
    rule: EmailRule
) -> List[Booking]:
    """Get bookings that match a time_after_booking_created rule"""
    if not rule.trigger_hours:
        return []
    
    now = datetime.utcnow()
    target_time = now - timedelta(hours=rule.trigger_hours)
    
    # Find bookings created around trigger_hours ago
    window_start = target_time - timedelta(minutes=30)
    window_end = target_time + timedelta(minutes=30)
    
    query = select(Booking).options(
        selectinload(Booking.engineer).selectinload(Engineer.user),
        selectinload(Booking.product),
        selectinload(Booking.change_type),
        selectinload(Booking.booker)
    ).where(
        and_(
            Booking.created_at >= window_start,
            Booking.created_at <= window_end,
            Booking.status != BookingStatus.CANCELLED
        )
    )
    
    if rule.condition_status:
        query = query.where(Booking.status == rule.condition_status)
    
    result = await db.execute(query)
    return result.scalars().all()


async def get_bookings_for_status_rule(
    db: AsyncSession,
    rule: EmailRule
) -> List[Booking]:
    """Get bookings that match a status_is rule"""
    if not rule.condition_status:
        return []
    
    # Get bookings with the specified status that haven't had this rule email sent
    query = select(Booking).options(
        selectinload(Booking.engineer).selectinload(Engineer.user),
        selectinload(Booking.product),
        selectinload(Booking.change_type),
        selectinload(Booking.booker)
    ).where(
        and_(
            Booking.status == rule.condition_status,
            Booking.scheduled_date >= datetime.utcnow()  # Only future bookings
        )
    )
    
    result = await db.execute(query)
    return result.scalars().all()


def get_recipients_for_booking(
    rule: EmailRule,
    booking: Booking
) -> List[str]:
    """Get list of recipient emails based on rule configuration"""
    recipients = []
    recipient_types = rule.recipient_types or []
    
    for recipient_type in recipient_types:
        if recipient_type == 'engineer' or recipient_type == EmailRuleRecipientType.ENGINEER.value:
            if booking.engineer and booking.engineer.calendar_email:
                recipients.append(booking.engineer.calendar_email)
        
        elif recipient_type == 'customer' or recipient_type == EmailRuleRecipientType.CUSTOMER.value:
            if booking.booker and booking.booker.email:
                recipients.append(booking.booker.email)
        
        elif recipient_type == 'booker' or recipient_type == EmailRuleRecipientType.BOOKER.value:
            if booking.booker and booking.booker.email:
                recipients.append(booking.booker.email)
        
        elif recipient_type == 'additional' or recipient_type == EmailRuleRecipientType.ADDITIONAL.value:
            if rule.additional_emails:
                recipients.extend(rule.additional_emails)
    
    # Remove duplicates while preserving order
    seen = set()
    unique_recipients = []
    for email in recipients:
        if email and email not in seen:
            seen.add(email)
            unique_recipients.append(email)
    
    return unique_recipients


async def send_rule_email(
    db: AsyncSession,
    rule: EmailRule,
    booking: Booking,
    recipients: List[str]
) -> bool:
    """Send email for a rule to specified recipients"""
    if not rule.email_template:
        return False
    
    template = rule.email_template
    
    # Build booking data for placeholder replacement
    booker_name = booking.booker.full_name if booking.booker else ''
    booker_email = booking.booker.email if booking.booker else ''
    booking_data = build_booking_data(booking, booker_name, booker_email)
    
    # Replace placeholders in template
    subject = replace_placeholders(template.subject, booking_data)
    body = replace_placeholders(template.body_html, booking_data)
    
    # Add logo if configured
    if template.logo_url:
        body = f'<div style="margin-bottom: 20px;"><img src="{template.logo_url}" alt="Company Logo" style="max-height: 80px;"></div>' + body
    
    # Send email
    try:
        success = await send_smtp_email(db, recipients, subject, body)
        return success
    except Exception as e:
        print(f"Error sending rule email: {str(e)}")
        return False


async def process_rule(db: AsyncSession, rule: EmailRule) -> dict:
    """Process a single email rule"""
    results = {
        'rule_id': rule.id,
        'rule_name': rule.name,
        'bookings_processed': 0,
        'emails_sent': 0,
        'errors': []
    }
    
    # Get bookings based on trigger type
    bookings = []
    
    if rule.trigger_type == EmailRuleTriggerType.TIME_BEFORE_BOOKING:
        bookings = await get_bookings_for_time_before_rule(db, rule)
    elif rule.trigger_type == EmailRuleTriggerType.TIME_AFTER_BOOKING_CREATED:
        bookings = await get_bookings_for_time_after_created_rule(db, rule)
    elif rule.trigger_type == EmailRuleTriggerType.STATUS_IS:
        bookings = await get_bookings_for_status_rule(db, rule)
    
    for booking in bookings:
        # Check if email already sent for this rule/booking combination
        if await has_email_been_sent(db, rule.id, booking.id):
            continue
        
        results['bookings_processed'] += 1
        
        # Get recipients
        recipients = get_recipients_for_booking(rule, booking)
        if not recipients:
            continue
        
        # Send email
        success = await send_rule_email(db, rule, booking, recipients)
        
        # Log the email
        for recipient in recipients:
            await log_email_sent(
                db, 
                rule.id, 
                booking.id, 
                recipient,
                success=success,
                error_message=None if success else "Failed to send email"
            )
        
        if success:
            results['emails_sent'] += 1
        else:
            results['errors'].append(f"Failed to send email for booking {booking.id}")
    
    return results


async def process_all_rules(db: AsyncSession) -> List[dict]:
    """Process all active email rules"""
    # Check if SMTP is configured
    if not await is_smtp_configured(db):
        return [{'error': 'SMTP not configured'}]
    
    rules = await get_active_rules(db)
    results = []
    
    for rule in rules:
        try:
            result = await process_rule(db, rule)
            results.append(result)
        except Exception as e:
            results.append({
                'rule_id': rule.id,
                'rule_name': rule.name,
                'error': str(e)
            })
    
    return results


# Background task runner
_running = False
_task = None


async def rule_processor_loop(get_db_session):
    """Background loop that processes rules periodically"""
    global _running
    
    while _running:
        try:
            async for db in get_db_session():
                try:
                    results = await process_all_rules(db)
                    for result in results:
                        if result.get('emails_sent', 0) > 0:
                            print(f"Rule '{result.get('rule_name')}': sent {result['emails_sent']} emails")
                except Exception as e:
                    print(f"Error processing rules: {str(e)}")
                finally:
                    await db.close()
                break
        except Exception as e:
            print(f"Error in rule processor loop: {str(e)}")
        
        # Wait 15 minutes before next check
        await asyncio.sleep(900)


def start_rule_processor(get_db_session):
    """Start the background rule processor"""
    global _running, _task
    
    if _running:
        return
    
    _running = True
    _task = asyncio.create_task(rule_processor_loop(get_db_session))
    print("Email rule processor started")


def stop_rule_processor():
    """Stop the background rule processor"""
    global _running, _task
    
    _running = False
    if _task:
        _task.cancel()
        _task = None
    print("Email rule processor stopped")
