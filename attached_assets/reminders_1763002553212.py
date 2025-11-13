import logging
from datetime import datetime, timedelta
from telegram.ext import Application
from database.db import db
from utils.datetime_helper import from_iso, now_jakarta, format_datetime_id, is_same_day
from utils.formatters import format_reminder_message

logger = logging.getLogger(__name__)


async def send_single_reminder(app: Application, appt_id: int, user_id: int, patient_name: str, 
                               therapist_name: str, start_dt_iso: str):
    try:
        appt_dt = from_iso(start_dt_iso)
        now = now_jakarta()
        datetime_str = format_datetime_id(start_dt_iso)
        
        is_today = is_same_day(now, appt_dt)
        
        message = format_reminder_message(patient_name, therapist_name, datetime_str, is_today)
        
        await app.bot.send_message(
            chat_id=user_id,
            text=message,
            parse_mode='Markdown'
        )
        
        logger.info(f"Reminder sent to user {user_id} for appointment {appt_id} (is_today={is_today})")
        
    except Exception as e:
        logger.error(f"Error sending reminder to user {user_id} for appointment {appt_id}: {e}")
