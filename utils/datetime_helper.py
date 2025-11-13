import pytz
from datetime import datetime, timedelta, date
from typing import List, Optional

JAKARTA_TZ = pytz.timezone('Asia/Jakarta')
WEEKDAY_NAMES_ID = ['Senin', 'Selasa', 'Rabu', 'Kamis', 'Jumat', 'Sabtu', 'Minggu']

def now_jakarta() -> datetime:
    return datetime.now(JAKARTA_TZ)

def from_iso(iso_str: str) -> datetime:
    if not iso_str:
        return now_jakarta()
    dt = datetime.fromisoformat(iso_str.replace('Z', '+00:00'))
    if dt.tzinfo is None:
        return JAKARTA_TZ.localize(dt)
    return dt.astimezone(JAKARTA_TZ)

def format_datetime_id(iso_str: str) -> str:
    dt = from_iso(iso_str)
    weekday = WEEKDAY_NAMES_ID[dt.weekday()]
    return f"{weekday}, {dt.day:02d}-{dt.month:02d}-{dt.year} pukul {dt.hour:02d}:{dt.minute:02d} WIB"

def format_datetime_short(iso_str: str) -> str:
    dt = from_iso(iso_str)
    return f"{dt.day:02d}-{dt.month:02d}-{dt.year} {dt.hour:02d}:{dt.minute:02d}"

def format_date_id(date_obj: date, include_year: bool = False) -> str:
    weekday = WEEKDAY_NAMES_ID[date_obj.weekday()]
    if include_year:
        return f"{weekday}, {date_obj.day:02d}-{date_obj.month:02d}-{date_obj.year}"
    return f"{weekday}, {date_obj.day:02d}-{date_obj.month:02d}"

def parse_date(date_str: str) -> Optional[date]:
    try:
        return datetime.strptime(date_str, '%Y-%m-%d').date()
    except:
        return None

def is_same_day(dt1: datetime, dt2: datetime) -> bool:
    return dt1.date() == dt2.date()

def overlaps(start1: datetime, duration1: int, start2_iso: str, duration2: int) -> bool:
    start2 = from_iso(start2_iso)
    end1 = start1 + timedelta(minutes=duration1)
    end2 = start2 + timedelta(minutes=duration2)
    return start1 < end2 and start2 < end1

async def generate_time_slots(date_obj: date) -> List[str]:
    from config import Config
    
    now = now_jakarta()
    today = now.date()
    
    if date_obj < today:
        return []
    
    slots = []
    current_dt = JAKARTA_TZ.localize(datetime.combine(date_obj, datetime.min.time()))
    current_dt = current_dt.replace(hour=Config.START_HOUR, minute=0, second=0, microsecond=0)
    end_dt = current_dt.replace(hour=Config.END_HOUR, minute=0)
    
    while current_dt < end_dt:
        if current_dt.hour < Config.BREAK_START_HOUR or current_dt.hour >= Config.BREAK_END_HOUR:
            if date_obj == today:
                if current_dt > now + timedelta(minutes=Config.MIN_BOOKING_BUFFER_MINUTES):
                    slots.append(current_dt.isoformat())
            else:
                slots.append(current_dt.isoformat())
        
        current_dt += timedelta(minutes=Config.INTERVAL_MINUTES)
    
    try:
        from utils.prayer_times import filter_slots_by_prayer_times
        slots = await filter_slots_by_prayer_times(slots)
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Could not filter by prayer times: {e}")
    
    return slots
