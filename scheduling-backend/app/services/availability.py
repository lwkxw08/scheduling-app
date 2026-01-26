from datetime import datetime, timedelta, date
from typing import List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.database_models import Engineer, EngineerSkill, User, EngineerSchedule, EngineerRosterAssignment, RosterPattern, RosterPhase
from app.services import microsoft_graph


def parse_time(time_str: str) -> tuple:
    parts = time_str.split(":")
    return int(parts[0]), int(parts[1])


def generate_time_slots(
    start_hour: int,
    start_minute: int,
    end_hour: int,
    end_minute: int,
    slot_duration_minutes: int = 60
) -> List[dict]:
    slots = []
    current = datetime.now().replace(hour=start_hour, minute=start_minute, second=0, microsecond=0)
    end = datetime.now().replace(hour=end_hour, minute=end_minute, second=0, microsecond=0)
    
    while current + timedelta(minutes=slot_duration_minutes) <= end:
        slot_end = current + timedelta(minutes=slot_duration_minutes)
        slots.append({
            "start_time": current.strftime("%H:%M"),
            "end_time": slot_end.strftime("%H:%M"),
            "is_available": True
        })
        current = slot_end
    
    return slots


def check_slot_overlap(
    slot_start: str,
    slot_end: str,
    events: List[dict],
    target_date: datetime
) -> bool:
    slot_start_hour, slot_start_min = parse_time(slot_start)
    slot_end_hour, slot_end_min = parse_time(slot_end)
    
    slot_start_dt = target_date.replace(hour=slot_start_hour, minute=slot_start_min, second=0, microsecond=0)
    slot_end_dt = target_date.replace(hour=slot_end_hour, minute=slot_end_min, second=0, microsecond=0)
    
    for event in events:
        event_start = datetime.fromisoformat(event["start"]["dateTime"].replace("Z", "+00:00"))
        event_end = datetime.fromisoformat(event["end"]["dateTime"].replace("Z", "+00:00"))
        
        event_start = event_start.replace(tzinfo=None)
        event_end = event_end.replace(tzinfo=None)
        
        show_as = event.get("showAs", "busy")
        if show_as == "free":
            continue
        
        if slot_start_dt < event_end and slot_end_dt > event_start:
            return True
    
    return False


async def get_qualified_engineers(
    db: AsyncSession,
    product_id: int,
    change_type_id: int
) -> List[Engineer]:
    query = (
        select(Engineer)
        .join(EngineerSkill)
        .where(
            EngineerSkill.product_id == product_id,
            EngineerSkill.change_type_id == change_type_id,
            Engineer.is_available == True
        )
        .options(selectinload(Engineer.user), selectinload(Engineer.skills))
        .distinct()
    )
    
    result = await db.execute(query)
    return result.scalars().all()


async def get_engineer_schedule_for_day(
    db: AsyncSession,
    engineer_id: int,
    day_of_week: int
) -> Optional[EngineerSchedule]:
    """Get the schedule for an engineer on a specific day of the week (0=Monday, 6=Sunday)"""
    result = await db.execute(
        select(EngineerSchedule).where(
            EngineerSchedule.engineer_id == engineer_id,
            EngineerSchedule.day_of_week == day_of_week
        )
    )
    return result.scalar_one_or_none()


async def get_engineer_roster_assignment(
    db: AsyncSession,
    engineer_id: int
) -> Optional[EngineerRosterAssignment]:
    """Get the active roster assignment for an engineer"""
    result = await db.execute(
        select(EngineerRosterAssignment)
        .where(
            EngineerRosterAssignment.engineer_id == engineer_id,
            EngineerRosterAssignment.is_active == True
        )
        .options(
            selectinload(EngineerRosterAssignment.pattern).selectinload(RosterPattern.phases)
        )
    )
    return result.scalar_one_or_none()


def calculate_roster_working_hours(
    assignment: EngineerRosterAssignment,
    target_date: datetime
) -> Optional[Tuple[str, str, bool]]:
    """
    Calculate if an engineer is working on a specific date based on their roster pattern.
    Returns (start_time, end_time, is_working) or None if no pattern applies.
    """
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


async def get_engineer_availability(
    db: AsyncSession,
    engineer: Engineer,
    target_date: datetime,
    duration_hours: float,
    admin_access_token: Optional[str] = None
) -> dict:
    day_of_week = target_date.weekday()
    day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    
    roster_assignment = await get_engineer_roster_assignment(db, engineer.id)
    
    if roster_assignment:
        roster_result = calculate_roster_working_hours(roster_assignment, target_date)
        if roster_result:
            start_time, end_time, is_working = roster_result
            if not is_working:
                return {
                    "engineer_id": engineer.id,
                    "engineer_name": engineer.user.full_name if engineer.user else "Unknown",
                    "calendar_email": engineer.calendar_email,
                    "slots": [],
                    "not_working": True,
                    "day_name": day_names[day_of_week],
                    "roster_day_off": True
                }
            start_hour, start_min = parse_time(start_time)
            end_hour, end_min = parse_time(end_time)
        else:
            schedule = await get_engineer_schedule_for_day(db, engineer.id, day_of_week)
            if schedule:
                if not schedule.is_working:
                    return {
                        "engineer_id": engineer.id,
                        "engineer_name": engineer.user.full_name if engineer.user else "Unknown",
                        "calendar_email": engineer.calendar_email,
                        "slots": [],
                        "not_working": True,
                        "day_name": day_names[day_of_week]
                    }
                start_hour, start_min = parse_time(schedule.start_time)
                end_hour, end_min = parse_time(schedule.end_time)
            else:
                start_hour, start_min = parse_time(engineer.working_hours_start)
                end_hour, end_min = parse_time(engineer.working_hours_end)
    else:
        schedule = await get_engineer_schedule_for_day(db, engineer.id, day_of_week)
        
        if schedule:
            if not schedule.is_working:
                return {
                    "engineer_id": engineer.id,
                    "engineer_name": engineer.user.full_name if engineer.user else "Unknown",
                    "calendar_email": engineer.calendar_email,
                    "slots": [],
                    "not_working": True,
                    "day_name": day_names[day_of_week]
                }
            start_hour, start_min = parse_time(schedule.start_time)
            end_hour, end_min = parse_time(schedule.end_time)
        else:
            start_hour, start_min = parse_time(engineer.working_hours_start)
            end_hour, end_min = parse_time(engineer.working_hours_end)
    
    slot_duration = int(duration_hours * 60)
    slots = generate_time_slots(start_hour, start_min, end_hour, end_min, slot_duration)
    
    if admin_access_token:
        start_of_day = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = target_date.replace(hour=23, minute=59, second=59, microsecond=0)
        
        try:
            events = await microsoft_graph.get_calendar_events(
                admin_access_token,
                engineer.calendar_email,
                start_of_day,
                end_of_day
            )
            
            for slot in slots:
                if check_slot_overlap(slot["start_time"], slot["end_time"], events, target_date):
                    slot["is_available"] = False
        except Exception:
            pass
    
    return {
        "engineer_id": engineer.id,
        "engineer_name": engineer.user.full_name if engineer.user else "Unknown",
        "calendar_email": engineer.calendar_email,
        "slots": slots
    }


async def check_specific_slot_availability(
    engineer: Engineer,
    scheduled_datetime: datetime,
    duration_hours: float,
    admin_access_token: Optional[str] = None
) -> bool:
    if not admin_access_token:
        return True
    
    start_of_day = scheduled_datetime.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_day = scheduled_datetime.replace(hour=23, minute=59, second=59, microsecond=0)
    
    try:
        events = await microsoft_graph.get_calendar_events(
            admin_access_token,
            engineer.calendar_email,
            start_of_day,
            end_of_day
        )
        
        slot_end = scheduled_datetime + timedelta(hours=duration_hours)
        
        for event in events:
            event_start = datetime.fromisoformat(event["start"]["dateTime"].replace("Z", "+00:00"))
            event_end = datetime.fromisoformat(event["end"]["dateTime"].replace("Z", "+00:00"))
            
            event_start = event_start.replace(tzinfo=None)
            event_end = event_end.replace(tzinfo=None)
            
            show_as = event.get("showAs", "busy")
            if show_as == "free":
                continue
            
            if scheduled_datetime < event_end and slot_end > event_start:
                return False
        
        return True
    except Exception:
        return True
