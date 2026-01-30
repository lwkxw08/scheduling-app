import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime

from app.models.database_models import SystemConfig, EmailTemplate, TemplateType, Booking, Engineer, BookingFee, BookingFeeStatus
from sqlalchemy.orm import selectinload


async def get_smtp_config(db: AsyncSession) -> dict:
    """Get SMTP configuration from system config"""
    smtp_configs = {}
    for key in ['smtp_host', 'smtp_port', 'smtp_username', 'smtp_password', 'smtp_from_email', 'smtp_use_tls', 'smtp_from_name']:
        result = await db.execute(select(SystemConfig).where(SystemConfig.key == key))
        config = result.scalar_one_or_none()
        if config:
            smtp_configs[key] = config.value
    return smtp_configs


async def is_smtp_configured(db: AsyncSession) -> bool:
    """Check if SMTP is properly configured"""
    config = await get_smtp_config(db)
    return bool(config.get('smtp_host') and config.get('smtp_port') and config.get('smtp_from_email'))


async def get_email_template(db: AsyncSession, template_type: TemplateType) -> Optional[EmailTemplate]:
    """Get email template by type - returns the default or first active template for this type"""
    result = await db.execute(
        select(EmailTemplate).where(
            EmailTemplate.template_type == template_type,
            EmailTemplate.is_default == True,
            EmailTemplate.is_active == True
        )
    )
    template = result.scalar_one_or_none()
    
    if not template:
        result = await db.execute(
            select(EmailTemplate).where(
                EmailTemplate.template_type == template_type,
                EmailTemplate.is_active == True
            )
        )
        template = result.scalar_one_or_none()
    
    return template


def replace_placeholders(text: str, booking_data: dict) -> str:
    """Replace template placeholders with actual booking data, including dynamic fee placeholders"""
    if not text:
        return text
    
    replacements = {
        '{{order_reference}}': str(booking_data.get('order_reference', '')),
        '{{customer_name}}': str(booking_data.get('customer_name', '')),
        '{{scheduled_date}}': booking_data.get('scheduled_date', ''),
        '{{scheduled_time}}': booking_data.get('scheduled_time', ''),
        '{{duration_hours}}': str(booking_data.get('duration_hours', '')),
        '{{product_name}}': str(booking_data.get('product_name', '')),
        '{{change_type}}': str(booking_data.get('change_type', '')),
        '{{engineer_name}}': str(booking_data.get('engineer_name', '')),
        '{{engineer_email}}': str(booking_data.get('engineer_email', '')),
        '{{booker_name}}': str(booking_data.get('booker_name', '')),
        '{{booker_email}}': str(booking_data.get('booker_email', '')),
        '{{booking_status}}': str(booking_data.get('booking_status', '')),
        '{{notes}}': str(booking_data.get('notes', '') or ''),
        '{{booking_notes}}': str(booking_data.get('booking_notes', '') or ''),
        '{{engineer_notes}}': str(booking_data.get('engineer_notes', '') or ''),
        '{{issue_description}}': str(booking_data.get('issue_description', '') or ''),
        '{{cancellation_fee}}': str(booking_data.get('cancellation_fee', '0')),
        '{{expedite_fee}}': str(booking_data.get('expedite_fee', '0')),
        '{{total_fees}}': str(booking_data.get('total_fees', '0')),
    }
    
    # Add dynamic fee placeholders from booking_data
    fee_data = booking_data.get('fee_data', {})
    for fee_key, fee_value in fee_data.items():
        replacements[f'{{{{{fee_key}}}}}'] = str(fee_value)
    
    result = text
    for placeholder, value in replacements.items():
        result = result.replace(placeholder, value)
    
    return result


def build_booking_data(booking: Booking, booker_name: str, booker_email: str) -> dict:
    """Build booking data dictionary for template replacement, including individual fee amounts"""
    scheduled_date = booking.scheduled_date
    if isinstance(scheduled_date, datetime):
        date_str = scheduled_date.strftime('%Y-%m-%d')
        time_str = scheduled_date.strftime('%H:%M')
    else:
        date_str = str(scheduled_date)
        time_str = ''
    
    # Build individual fee data from booking fees
    fee_data = {}
    total_fees = 0
    if hasattr(booking, 'fees') and booking.fees:
        for booking_fee in booking.fees:
            if booking_fee.status == BookingFeeStatus.APPROVED and booking_fee.fee:
                # Convert fee name to placeholder format: "Late Cancellation" -> "fee_late_cancellation"
                fee_name = booking_fee.fee.name
                placeholder_name = fee_name.lower().replace(' ', '_').replace('-', '_')
                placeholder_name = ''.join(c if c.isalnum() or c == '_' else '' for c in placeholder_name)
                fee_key = f"fee_{placeholder_name}"
                
                # Sum up if same fee applied multiple times
                if fee_key in fee_data:
                    fee_data[fee_key] = float(fee_data[fee_key]) + float(booking_fee.amount)
                else:
                    fee_data[fee_key] = float(booking_fee.amount)
                
                total_fees += float(booking_fee.amount)
    
    # Also add legacy cancellation_fee and expedite_fee to total
    if booking.cancellation_fee:
        total_fees += float(booking.cancellation_fee)
    if booking.expedite_fee:
        total_fees += float(booking.expedite_fee)
    
    return {
        'order_reference': booking.order_reference,
        'customer_name': booking.customer_name,
        'scheduled_date': date_str,
        'scheduled_time': time_str,
        'duration_hours': booking.duration_hours,
        'product_name': booking.product.name if booking.product else '',
        'change_type': booking.change_type.name if booking.change_type else '',
        'engineer_name': booking.engineer.user.full_name if booking.engineer and booking.engineer.user else '',
        'engineer_email': booking.engineer.calendar_email if booking.engineer else '',
        'booker_name': booker_name,
        'booker_email': booker_email,
        'booking_status': booking.status.value if booking.status else '',
        'notes': booking.notes or '',
        'booking_notes': booking.notes or '',
        'engineer_notes': getattr(booking, 'engineer_notes', '') or '',
        'issue_description': getattr(booking, 'issue_description', '') or '',
        'cancellation_fee': booking.cancellation_fee or 0,
        'expedite_fee': booking.expedite_fee or 0,
        'total_fees': total_fees,
        'fee_data': fee_data,
    }


async def send_smtp_email(
    db: AsyncSession,
    to_emails: List[str],
    subject: str,
    body_html: str,
    body_text: Optional[str] = None
) -> bool:
    """Send email via SMTP"""
    smtp_config = await get_smtp_config(db)
    
    if not smtp_config.get('smtp_host') or not smtp_config.get('smtp_from_email'):
        return False
    
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = f"{smtp_config.get('smtp_from_name', 'Scheduling App')} <{smtp_config['smtp_from_email']}>"
        msg['To'] = ', '.join(to_emails)
        
        if body_text:
            msg.attach(MIMEText(body_text, 'plain'))
        
        msg.attach(MIMEText(body_html, 'html'))
        
        port = int(smtp_config.get('smtp_port', 587))
        use_tls = smtp_config.get('smtp_use_tls', 'true').lower() == 'true'
        
        if use_tls:
            server = smtplib.SMTP(smtp_config['smtp_host'], port)
            server.starttls()
        else:
            server = smtplib.SMTP(smtp_config['smtp_host'], port)
        
        if smtp_config.get('smtp_username') and smtp_config.get('smtp_password'):
            server.login(smtp_config['smtp_username'], smtp_config['smtp_password'])
        
        server.sendmail(smtp_config['smtp_from_email'], to_emails, msg.as_string())
        server.quit()
        
        return True
    except Exception as e:
        print(f"SMTP email error: {str(e)}")
        return False


async def send_booking_email(
    db: AsyncSession,
    booking: Booking,
    booker_name: str,
    booker_email: str,
    template_type: TemplateType,
    additional_emails: Optional[List[str]] = None
) -> dict:
    """Send booking-related emails using templates"""
    results = {
        'booker_sent': False,
        'engineer_sent': False,
        'additional_sent': False,
        'errors': []
    }
    
    if not await is_smtp_configured(db):
        results['errors'].append('SMTP not configured')
        return results
    
    booking_data = build_booking_data(booking, booker_name, booker_email)
    
    template = await get_email_template(db, template_type)
    
    should_send_to_customer = template.send_to_customer if template else True
    should_send_to_engineer = template.send_to_engineer if template else True
    
    if should_send_to_customer:
        if template:
            subject = replace_placeholders(template.subject, booking_data)
            body = replace_placeholders(template.body_html, booking_data)
            
            if template.logo_url:
                body = f'<div style="margin-bottom: 20px;"><img src="{template.logo_url}" alt="Company Logo" style="max-height: 80px;"></div>' + body
        else:
            subject = f"Booking {template_type.value.title()} - {booking.order_reference}"
            body = f"""
            <html>
            <body style="font-family: Arial, sans-serif; padding: 20px;">
                <h2>Booking {template_type.value.title()}</h2>
                <p><strong>Order Reference:</strong> {booking_data['order_reference']}</p>
                <p><strong>Customer:</strong> {booking_data['customer_name']}</p>
                <p><strong>Date:</strong> {booking_data['scheduled_date']} at {booking_data['scheduled_time']}</p>
                <p><strong>Duration:</strong> {booking_data['duration_hours']} hours</p>
                <p><strong>Product:</strong> {booking_data['product_name']}</p>
                <p><strong>Engineer:</strong> {booking_data['engineer_name']}</p>
                <p><strong>Notes:</strong> {booking_data['notes'] or 'N/A'}</p>
            </body>
            </html>
            """
        
        try:
            results['booker_sent'] = await send_smtp_email(db, [booker_email], subject, body)
        except Exception as e:
            results['errors'].append(f'Booker email error: {str(e)}')
    
    if should_send_to_engineer and booking.engineer and booking.engineer.calendar_email:
        engineer_email = booking.engineer.calendar_email
        
        if template:
            subject = replace_placeholders(template.subject, booking_data)
            body = replace_placeholders(template.body_html, booking_data)
            
            if template.logo_url:
                body = f'<div style="margin-bottom: 20px;"><img src="{template.logo_url}" alt="Company Logo" style="max-height: 80px;"></div>' + body
        else:
            subject = f"Booking Assignment - {booking.order_reference}"
            body = f"""
            <html>
            <body style="font-family: Arial, sans-serif; padding: 20px;">
                <h2>New Booking Assignment</h2>
                <p><strong>Order Reference:</strong> {booking_data['order_reference']}</p>
                <p><strong>Customer:</strong> {booking_data['customer_name']}</p>
                <p><strong>Date:</strong> {booking_data['scheduled_date']} at {booking_data['scheduled_time']}</p>
                <p><strong>Duration:</strong> {booking_data['duration_hours']} hours</p>
                <p><strong>Product:</strong> {booking_data['product_name']}</p>
                <p><strong>Notes:</strong> {booking_data['notes'] or 'N/A'}</p>
            </body>
            </html>
            """
        
        try:
            results['engineer_sent'] = await send_smtp_email(db, [engineer_email], subject, body)
        except Exception as e:
            results['errors'].append(f'Engineer email error: {str(e)}')
    
    if additional_emails:
        valid_emails = [e for e in additional_emails if e and '@' in e]
        if valid_emails:
            if template:
                subject = replace_placeholders(template.subject, booking_data)
                body = replace_placeholders(template.body_html, booking_data)
                
                if template.logo_url:
                    body = f'<div style="margin-bottom: 20px;"><img src="{template.logo_url}" alt="Company Logo" style="max-height: 80px;"></div>' + body
            else:
                subject = f"Booking {template_type.value.title()} - {booking.order_reference}"
                body = f"""
                <html>
                <body style="font-family: Arial, sans-serif; padding: 20px;">
                    <h2>Booking {template_type.value.title()}</h2>
                    <p><strong>Order Reference:</strong> {booking_data['order_reference']}</p>
                    <p><strong>Customer:</strong> {booking_data['customer_name']}</p>
                    <p><strong>Date:</strong> {booking_data['scheduled_date']} at {booking_data['scheduled_time']}</p>
                    <p><strong>Duration:</strong> {booking_data['duration_hours']} hours</p>
                    <p><strong>Product:</strong> {booking_data['product_name']}</p>
                    <p><strong>Engineer:</strong> {booking_data['engineer_name']}</p>
                </body>
                </html>
                """
            
            try:
                results['additional_sent'] = await send_smtp_email(db, valid_emails, subject, body)
            except Exception as e:
                results['errors'].append(f'Additional emails error: {str(e)}')
    
    return results
