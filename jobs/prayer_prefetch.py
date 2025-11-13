import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from utils.prayer_times import prefetch_prayer_times_bulk
from utils.datetime_helper import JAKARTA_TZ
from config import Config

logger = logging.getLogger(__name__)


async def prayer_times_prefetch_job():
    """
    Daily job to pre-fetch prayer times for the next N days.
    Runs at 00:00 WIB daily.
    """
    try:
        logger.info("Starting daily prayer times pre-fetch job...")
        success_count = await prefetch_prayer_times_bulk(days_ahead=Config.PRAYER_PREFETCH_DAYS)
        logger.info(f"Prayer times pre-fetch job completed: {success_count} days cached")
    except Exception as e:
        logger.error(f"Error in prayer times pre-fetch job: {e}")


def setup_prayer_prefetch_scheduler(scheduler: AsyncIOScheduler):
    """
    Setup scheduler for daily prayer times pre-fetch.
    Runs at 00:00 WIB every day.
    """
    scheduler.add_job(
        prayer_times_prefetch_job,
        'cron',
        hour=0,
        minute=0,
        timezone=JAKARTA_TZ,
        id='prayer_times_prefetch',
        replace_existing=True,
        misfire_grace_time=3600
    )
    logger.info("Prayer times pre-fetch scheduler configured: Daily at 00:00 WIB")
