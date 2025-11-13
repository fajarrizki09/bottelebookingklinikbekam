import logging
from datetime import datetime, time
from telegram.ext import Application
from database.db import db
from utils.hijri_helper import get_next_sunnah_dates, format_sunnah_notification
from utils.datetime_helper import now_jakarta, JAKARTA_TZ

logger = logging.getLogger(__name__)


async def send_sunnah_notification(app: Application):
    """
    Mengirim notifikasi tanggal bekam sunnah ke semua user yang pernah booking.
    Job ini dijadwalkan untuk berjalan setiap hari jam 09:00 WIB.
    """
    try:
        logger.info("Starting sunnah notification job...")
        
        upcoming_dates = get_next_sunnah_dates(months_ahead=1)
        
        if not upcoming_dates:
            logger.info("No upcoming sunnah dates found")
            return
        
        next_sunnah = upcoming_dates[0]
        today = now_jakarta().date()
        days_until = (next_sunnah['gregorian_date'] - today).days
        
        if days_until not in [7, 3, 1]:
            logger.info(f"Not sending notification today. Next sunnah date in {days_until} days")
            return
        
        appointments = await db.get_appointments()
        
        unique_users = {}
        for appt in appointments:
            user_id = appt['user_id']
            if user_id not in unique_users:
                unique_users[user_id] = {
                    'user_id': user_id,
                    'user_name': appt['user_name']
                }
        
        if not unique_users:
            logger.info("No users found to send notifications")
            return
        
        notification_msg = format_sunnah_notification(next_sunnah)
        
        success_count = 0
        error_count = 0
        
        for user_info in unique_users.values():
            try:
                await app.bot.send_message(
                    chat_id=user_info['user_id'],
                    text=notification_msg,
                    parse_mode='Markdown'
                )
                success_count += 1
                logger.info(f"Sent sunnah notification to user {user_info['user_id']} ({user_info['user_name']})")
            except Exception as e:
                error_count += 1
                logger.error(f"Failed to send sunnah notification to user {user_info['user_id']}: {e}")
        
        logger.info(f"Sunnah notification job completed. Success: {success_count}, Errors: {error_count}")
        
    except Exception as e:
        logger.error(f"Error in sunnah notification job: {e}")


def schedule_sunnah_notifications(scheduler, app: Application):
    """
    Setup scheduler untuk notifikasi tanggal bekam sunnah.
    Akan berjalan setiap hari jam 09:00 WIB dan mengirim notifikasi 
    7 hari, 3 hari, dan 1 hari sebelum tanggal sunnah.
    """
    try:
        scheduler.add_job(
            send_sunnah_notification,
            'cron',
            hour=9,
            minute=0,
            timezone=JAKARTA_TZ,
            args=[app],
            id='sunnah_notification',
            replace_existing=True,
            misfire_grace_time=3600
        )
        logger.info("Sunnah notification scheduler configured: Daily at 09:00 WIB")
    except Exception as e:
        logger.error(f"Error scheduling sunnah notifications: {e}")
