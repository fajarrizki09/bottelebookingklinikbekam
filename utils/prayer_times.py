import httpx
from datetime import datetime, timedelta, date
from typing import Dict, List, Optional
from utils.datetime_helper import JAKARTA_TZ, now_jakarta
import logging

logger = logging.getLogger(__name__)

PRAYER_BREAK_MINUTES = 20

JAKARTA_LAT = -6.2088
JAKARTA_LNG = 106.8456

_prayer_times_cache = {}


def _convert_date_format(date_str: str) -> str:
    """Convert date from YYYY-MM-DD to DD-MM-YYYY for API."""
    try:
        if '-' in date_str and len(date_str.split('-')[0]) == 4:
            parts = date_str.split('-')
            return f"{parts[2]}-{parts[1]}-{parts[0]}"
        return date_str
    except Exception:
        return date_str


def _convert_to_iso_date(date_str: str) -> str:
    """Convert date from DD-MM-YYYY to YYYY-MM-DD for database."""
    try:
        if '-' in date_str and len(date_str.split('-')[0]) == 2:
            parts = date_str.split('-')
            return f"{parts[2]}-{parts[1]}-{parts[0]}"
        return date_str
    except Exception:
        return date_str


async def get_prayer_times(city: str = "Jakarta", country: str = "Indonesia", date_str: str = None) -> Optional[Dict]:
    """
    Fetch prayer times with database-first caching strategy.
    Priority: 1) Database cache, 2) Memory cache, 3) API call
    """
    if date_str is None:
        date_obj = now_jakarta().date()
        date_str = date_obj.strftime('%d-%m-%Y')
    
    iso_date = _convert_to_iso_date(date_str)
    
    if date_str in _prayer_times_cache:
        logger.debug(f"Using memory cache for prayer times {date_str}")
        return _prayer_times_cache[date_str]
    
    try:
        from database.db import db
        
        cached_prayer = await db.get_prayer_times_for_date(iso_date)
        if cached_prayer:
            result = {
                "Fajr": cached_prayer['fajr'],
                "Dhuhr": cached_prayer['dhuhr'],
                "Asr": cached_prayer['asr'],
                "Maghrib": cached_prayer['maghrib'],
                "Isha": cached_prayer['isha']
            }
            _prayer_times_cache[date_str] = result
            logger.debug(f"Using database cache for prayer times {date_str}")
            return result
    except Exception as e:
        logger.warning(f"Database cache lookup failed for {date_str}: {e}")
    
    api_date = _convert_date_format(date_str)
    
    try:
        url = f"https://api.aladhan.com/v1/timings/{api_date}"
        params = {
            "latitude": JAKARTA_LAT,
            "longitude": JAKARTA_LNG,
            "method": 2
        }
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            
            data = response.json()
            if data.get("code") == 200 and "data" in data:
                timings = data["data"]["timings"]
                result = {
                    "Fajr": timings.get("Fajr"),
                    "Dhuhr": timings.get("Dhuhr"),
                    "Asr": timings.get("Asr"),
                    "Maghrib": timings.get("Maghrib"),
                    "Isha": timings.get("Isha")
                }
                _prayer_times_cache[date_str] = result
                logger.info(f"Fetched prayer times from API for {date_str}")
                
                try:
                    from database.db import db
                    await db.save_prayer_times(
                        iso_date,
                        result["Fajr"],
                        result["Dhuhr"],
                        result["Asr"],
                        result["Maghrib"],
                        result["Isha"]
                    )
                except Exception as e:
                    logger.warning(f"Failed to save prayer times to database for {date_str}: {e}")
                
                return result
            
            logger.warning(f"Invalid response from prayer times API for {date_str}: code={data.get('code')}, status={data.get('status')}")
            return None
    
    except httpx.HTTPError as e:
        logger.error(f"HTTP error fetching prayer times for {date_str}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error fetching prayer times for {date_str}: {e}")
        return None


async def prefetch_prayer_times_bulk(days_ahead: int = 30) -> int:
    """
    Pre-fetch prayer times for multiple days and save to database.
    Returns the number of days successfully fetched.
    This should be called by scheduler daily at 00:00 WIB.
    """
    logger.info(f"Starting prayer times pre-fetch for {days_ahead} days ahead")
    success_count = 0
    today = now_jakarta().date()
    
    for i in range(days_ahead):
        target_date = today + timedelta(days=i)
        date_str = target_date.strftime('%d-%m-%Y')
        iso_date = target_date.isoformat()
        
        try:
            from database.db import db
            
            cached = await db.get_prayer_times_for_date(iso_date)
            if cached:
                logger.debug(f"Prayer times already cached for {iso_date}, skipping")
                success_count += 1
                continue
        except Exception as e:
            logger.warning(f"Error checking cache for {iso_date}: {e}")
        
        try:
            url = f"https://api.aladhan.com/v1/timings/{date_str}"
            params = {
                "latitude": JAKARTA_LAT,
                "longitude": JAKARTA_LNG,
                "method": 2
            }
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                
                data = response.json()
                if data.get("code") == 200 and "data" in data:
                    timings = data["data"]["timings"]
                    
                    from database.db import db
                    await db.save_prayer_times(
                        iso_date,
                        timings.get("Fajr"),
                        timings.get("Dhuhr"),
                        timings.get("Asr"),
                        timings.get("Maghrib"),
                        timings.get("Isha")
                    )
                    
                    success_count += 1
                    logger.info(f"Pre-fetched and saved prayer times for {iso_date}")
                else:
                    logger.warning(f"Invalid API response for {date_str}")
        
        except Exception as e:
            logger.error(f"Error pre-fetching prayer times for {date_str}: {e}")
    
    logger.info(f"Prayer times pre-fetch completed: {success_count}/{days_ahead} days")
    
    try:
        from database.db import db
        yesterday = (today - timedelta(days=1)).isoformat()
        await db.clear_old_prayer_times(yesterday)
    except Exception as e:
        logger.error(f"Error clearing old prayer times: {e}")
    
    return success_count


def parse_prayer_time(time_str: str, date_obj: date) -> Optional[datetime]:
    """Parse prayer time string (HH:MM) into datetime object."""
    try:
        hour, minute = time_str.split(":")
        dt = datetime.combine(date_obj, datetime.min.time())
        dt = dt.replace(hour=int(hour), minute=int(minute))
        return JAKARTA_TZ.localize(dt)
    except Exception as e:
        logger.error(f"Error parsing prayer time {time_str}: {e}")
        return None


async def get_blocked_time_ranges(date_obj: date) -> List[tuple]:
    """Get list of time ranges blocked for prayer (prayer time + buffer)."""
    date_str = date_obj.strftime('%d-%m-%Y')
    prayer_times_dict = await get_prayer_times(date_str=date_str)
    
    if not prayer_times_dict:
        logger.debug(f"No prayer times available for {date_str}, returning empty blocked ranges")
        return []
    
    blocked_ranges = []
    
    for prayer_name, time_str in prayer_times_dict.items():
        if not time_str:
            continue
        
        prayer_dt = parse_prayer_time(time_str, date_obj)
        if not prayer_dt:
            continue
        
        block_start = prayer_dt - timedelta(minutes=10)
        block_end = prayer_dt + timedelta(minutes=10)
        blocked_ranges.append((block_start, block_end))
    
    return blocked_ranges


async def is_time_blocked_by_prayer(dt: datetime) -> bool:
    """Check if a given datetime falls within prayer time blocks."""
    date_obj = dt.date()
    blocked_ranges = await get_blocked_time_ranges(date_obj)
    
    for start, end in blocked_ranges:
        if start <= dt < end:
            return True
    
    return False


async def filter_slots_by_prayer_times(slots: List[str]) -> List[str]:
    """
    Filter out time slots that conflict with prayer times.
    Optimized to call database/API only once per unique date.
    """
    if not slots:
        return []
    
    from utils.datetime_helper import from_iso
    
    date_groups = {}
    for slot_iso in slots:
        slot_dt = from_iso(slot_iso)
        date_key = slot_dt.date()
        if date_key not in date_groups:
            date_groups[date_key] = []
        date_groups[date_key].append((slot_iso, slot_dt))
    
    filtered_slots = []
    for date_obj, slot_list in date_groups.items():
        blocked_ranges = await get_blocked_time_ranges(date_obj)
        
        for slot_iso, slot_dt in slot_list:
            is_blocked = False
            for start, end in blocked_ranges:
                if start <= slot_dt < end:
                    is_blocked = True
                    break
            
            if not is_blocked:
                filtered_slots.append(slot_iso)
    
    filtered_slots.sort()
    return filtered_slots
