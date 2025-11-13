import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from database.db import db

logger = logging.getLogger(__name__)


async def check_and_toggle_therapists():
    try:
        therapists_to_deactivate = await db.get_therapists_to_deactivate()
        for therapist in therapists_to_deactivate:
            await db.deactivate_therapist(therapist['id'])
            logger.info(f"Auto-deactivated therapist: {therapist['name']}")
        
        therapists_to_reactivate = await db.get_therapists_to_reactivate()
        for therapist in therapists_to_reactivate:
            await db.reactivate_therapist(therapist['id'])
            logger.info(f"Auto-reactivated therapist: {therapist['name']}")
    
    except Exception as e:
        logger.error(f"Error in therapist activation check: {e}")


def setup_therapist_activator(scheduler: AsyncIOScheduler):
    scheduler.add_job(
        check_and_toggle_therapists,
        'interval',
        minutes=5,
        id='therapist_activator',
        replace_existing=True
    )
    logger.info("Therapist auto-activator scheduler configured: Every 5 minutes")
