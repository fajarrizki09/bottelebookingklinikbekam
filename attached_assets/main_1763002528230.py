#!/usr/bin/env python3
import logging
import sys
from datetime import timedelta
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ConversationHandler, PicklePersistence, filters
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from config import Config
from database.db import db
from handlers.common import start_cmd, help_cmd, cancel_cmd, back_to_start_callback, timeout_handler, fallback_handler, global_callback_handler, S_START
from handlers.user import (
    make_appointment_callback, patient_gender_callback, date_callback,
    time_callback, show_any_or_waitlist_callback, view_therapists_for_date_callback,
    therapist_callback, patient_name_text, patient_address_text, confirmation_callback,
    my_appointments_callback, view_my_appointment_callback, cancel_my_appointment_callback,
    back_to_gender_callback, back_to_choose_date_callback, back_to_choose_time_callback,
    back_to_choose_therapist_callback, back_to_name_callback, back_to_address_callback,
    calendar_nav_callback, calendar_noop_callback,
    waitlist_name_text, waitlist_phone_text, waitlist_confirm_callback,
    S_PAT_GENDER, S_CHOOSE_DATE, S_CHOOSE_TIME,
    S_CHOOSE_THER, S_ASK_NAME, S_ASK_ADDRESS, S_CONFIRM,
    S_WAITLIST_NAME, S_WAITLIST_PHONE
)
from handlers.admin import (
    admin_menu_callback, admin_therapists_callback, add_therapist_callback,
    add_therapist_name_text, add_therapist_gender_callback, delete_therapist_callback,
    delete_therapist_confirm_callback, admin_appointments_callback,
    delete_appointment_callback, delete_appointment_confirm_callback,
    admin_waitlist_callback, admin_holidays_callback, add_holiday_date_callback,
    add_holiday_date_text, admin_export_callback,
    view_appointment_callback, manage_appointment_callback, appt_page_nav_callback,
    change_status_menu_callback, change_status_confirm_callback, edit_appt_menu_callback,
    edit_field_select_callback, edit_therapist_confirm_callback, edit_appt_value_text,
    view_waitlist_entry_callback, confirm_slot_available_callback,
    inform_waitlist_full_callback, delete_waitlist_entry_callback,
    therapist_detail_callback, toggle_therapist_callback, edit_therapist_name_callback,
    edit_therapist_name_text, edit_therapist_gender_callback, set_therapist_gender_callback,
    add_holiday_date_selected_callback, holiday_calendar_nav_callback, holiday_calendar_noop_callback,
    schedule_inactive_callback, schedule_inactive_duration_callback, schedule_inactive_custom_callback,
    schedule_inactive_custom_days_text, cancel_inactive_schedule_callback,
    A_MENU, A_ADD_TH_NAME, A_ADD_TH_GENDER, A_DELETE_TH_SELECT,
    A_DELETE_APPT, A_HOLIDAY_MENU, A_ADD_HOL_DATE, A_VIEW_APPT, A_MANAGE_APPT,
    A_EDIT_APPT_FIELD, A_EDIT_APPT_VALUE, A_WAITLIST_MANAGE,
    A_TH_DETAIL, A_EDIT_TH_NAME, A_EDIT_TH_GENDER, A_SCHEDULE_INACTIVE, A_INACTIVE_CUSTOM_DAYS
)
from jobs.reminders import send_single_reminder
from jobs.sunnah_notifications import schedule_sunnah_notifications
from jobs.therapist_activator import setup_therapist_activator
from jobs.prayer_prefetch import setup_prayer_prefetch_scheduler
from utils.datetime_helper import from_iso, now_jakarta
from utils.prayer_times import prefetch_prayer_times_bulk

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

global_scheduler = None


async def error_handler(update: object, context) -> None:
    logger.error("Exception while handling an update:", exc_info=context.error)
    
    if update and hasattr(update, 'effective_message') and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "❌ Terjadi kesalahan. Silakan coba lagi atau hubungi admin."
            )
        except Exception as e:
            logger.error(f"Error sending error message to user: {e}")


def schedule_reminder(app: Application, appt_id: int, user_id: int, patient_name: str, 
                       therapist_name: str, start_dt_iso: str) -> str:
    global global_scheduler
    
    appt_dt = from_iso(start_dt_iso)
    reminder_time = appt_dt - timedelta(minutes=Config.REMINDER_MINUTES_BEFORE)
    
    now = now_jakarta()
    if reminder_time <= now:
        logger.warning(f"Cannot schedule reminder for appointment {appt_id} - reminder time is in the past")
        return None
    
    job_id = f"reminder_{appt_id}"
    
    try:
        global_scheduler.add_job(
            send_single_reminder,
            'date',
            run_date=reminder_time,
            args=[app, appt_id, user_id, patient_name, therapist_name, start_dt_iso],
            id=job_id,
            replace_existing=True
        )
        logger.info(f"Scheduled reminder for appointment {appt_id} at {reminder_time}")
        return job_id
    except Exception as e:
        logger.error(f"Error scheduling reminder: {e}")
        return None


def cancel_reminder(job_id: str):
    global global_scheduler
    
    if not job_id:
        return
    
    try:
        global_scheduler.remove_job(job_id)
        logger.info(f"Cancelled reminder job: {job_id}")
    except Exception as e:
        logger.debug(f"Could not cancel reminder job {job_id}: {e}")


async def post_init(application: Application) -> None:
    await db.connect()
    
    application.bot_data['schedule_reminder'] = schedule_reminder
    application.bot_data['cancel_reminder'] = cancel_reminder
    
    try:
        logger.info("Pre-fetching prayer times on bot startup...")
        success_count = await prefetch_prayer_times_bulk(days_ahead=Config.PRAYER_PREFETCH_DAYS)
        logger.info(f"Startup prayer times pre-fetch completed: {success_count} days cached")
    except Exception as e:
        logger.error(f"Error during startup prayer times pre-fetch: {e}")
    
    logger.info("Bot initialized successfully with persistence")


async def post_shutdown(application: Application) -> None:
    await db.close()
    logger.info("Bot shutdown complete")


def main():
    global global_scheduler
    
    logger.info("Starting Bekam Booking Bot with session persistence...")
    
    persistence = PicklePersistence(filepath=Config.PERSISTENCE_PATH)
    
    application = (
        Application.builder()
        .token(Config.TOKEN)
        .persistence(persistence)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )
    
    main_conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start_cmd),
            CallbackQueryHandler(make_appointment_callback, pattern="^make$")
        ],
        states={
            S_START: [
                CallbackQueryHandler(make_appointment_callback, pattern="^make$"),
                CallbackQueryHandler(my_appointments_callback, pattern="^my_appointments$"),
                CallbackQueryHandler(view_my_appointment_callback, pattern="^view_my_appt_"),
                CallbackQueryHandler(cancel_my_appointment_callback, pattern="^cancel_my_appt_"),
                CallbackQueryHandler(admin_menu_callback, pattern="^admin_menu$"),
                CallbackQueryHandler(back_to_start_callback, pattern="^back_to_start$")
            ],
            S_PAT_GENDER: [
                CallbackQueryHandler(patient_gender_callback, pattern="^pat_[mf]$"),
                CallbackQueryHandler(back_to_gender_callback, pattern="^back_to_gender$"),
                CallbackQueryHandler(show_any_or_waitlist_callback, pattern="^join_waitlist_no_therapist$"),
                CallbackQueryHandler(back_to_start_callback, pattern="^back_to_start$")
            ],
            S_CHOOSE_DATE: [
                CallbackQueryHandler(date_callback, pattern="^date_"),
                CallbackQueryHandler(calendar_nav_callback, pattern="^cal_(prev|next)_"),
                CallbackQueryHandler(calendar_noop_callback, pattern="^cal_noop$"),
                CallbackQueryHandler(back_to_gender_callback, pattern="^back_to_gender$"),
                CallbackQueryHandler(back_to_start_callback, pattern="^back_to_start$")
            ],
            S_CHOOSE_TIME: [
                CallbackQueryHandler(time_callback, pattern="^time_"),
                CallbackQueryHandler(view_therapists_for_date_callback, pattern="^view_therapists_for_date$"),
                CallbackQueryHandler(show_any_or_waitlist_callback, pattern="^(show_any|join_waitlist|pick_other_time)$"),
                CallbackQueryHandler(back_to_choose_date_callback, pattern="^back_to_choose_date$"),
                CallbackQueryHandler(back_to_choose_time_callback, pattern="^back_to_choose_time$"),
                CallbackQueryHandler(back_to_start_callback, pattern="^back_to_start$")
            ],
            S_CHOOSE_THER: [
                CallbackQueryHandler(therapist_callback, pattern="^ther_"),
                CallbackQueryHandler(back_to_choose_time_callback, pattern="^back_to_choose_time$"),
                CallbackQueryHandler(back_to_start_callback, pattern="^back_to_start$")
            ],
            S_ASK_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, patient_name_text),
                CallbackQueryHandler(back_to_choose_therapist_callback, pattern="^back_to_choose_therapist$"),
                CallbackQueryHandler(back_to_start_callback, pattern="^back_to_start$")
            ],
            S_ASK_ADDRESS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, patient_address_text),
                CallbackQueryHandler(back_to_name_callback, pattern="^back_to_name$"),
                CallbackQueryHandler(back_to_start_callback, pattern="^back_to_start$")
            ],
            S_CONFIRM: [
                CallbackQueryHandler(confirmation_callback, pattern="^confirm_"),
                CallbackQueryHandler(back_to_address_callback, pattern="^back_to_address$"),
                CallbackQueryHandler(back_to_start_callback, pattern="^back_to_start$")
            ],
            S_WAITLIST_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, waitlist_name_text),
                CallbackQueryHandler(back_to_choose_time_callback, pattern="^back_to_choose_time$"),
                CallbackQueryHandler(back_to_start_callback, pattern="^back_to_start$")
            ],
            S_WAITLIST_PHONE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, waitlist_phone_text),
                CallbackQueryHandler(waitlist_confirm_callback, pattern="^waitlist_confirm$"),
                CallbackQueryHandler(back_to_choose_time_callback, pattern="^back_to_choose_time$"),
                CallbackQueryHandler(back_to_start_callback, pattern="^back_to_start$")
            ],
            A_MENU: [
                CallbackQueryHandler(admin_therapists_callback, pattern="^admin_therapists$"),
                CallbackQueryHandler(add_therapist_callback, pattern="^add_therapist$"),
                CallbackQueryHandler(delete_therapist_callback, pattern="^delete_therapist$"),
                CallbackQueryHandler(therapist_detail_callback, pattern="^th_detail_"),
                CallbackQueryHandler(admin_appointments_callback, pattern="^admin_appointments$"),
                CallbackQueryHandler(view_appointment_callback, pattern="^view_appointment$"),
                CallbackQueryHandler(delete_appointment_callback, pattern="^delete_appointment$"),
                CallbackQueryHandler(admin_waitlist_callback, pattern="^admin_waitlist$"),
                CallbackQueryHandler(admin_holidays_callback, pattern="^admin_holidays$"),
                CallbackQueryHandler(admin_export_callback, pattern="^admin_export$"),
                CallbackQueryHandler(admin_menu_callback, pattern="^admin_menu$"),
                CallbackQueryHandler(back_to_start_callback, pattern="^back_to_start$")
            ],
            A_ADD_TH_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, add_therapist_name_text)
            ],
            A_ADD_TH_GENDER: [
                CallbackQueryHandler(add_therapist_gender_callback, pattern="^gender_[mf]$"),
                CallbackQueryHandler(back_to_start_callback, pattern="^back_to_start$")
            ],
            A_DELETE_TH_SELECT: [
                CallbackQueryHandler(delete_therapist_confirm_callback, pattern="^(delther_|admin_menu)"),
                CallbackQueryHandler(back_to_start_callback, pattern="^back_to_start$")
            ],
            A_TH_DETAIL: [
                CallbackQueryHandler(toggle_therapist_callback, pattern="^toggle_th_"),
                CallbackQueryHandler(edit_therapist_name_callback, pattern="^edit_th_name_"),
                CallbackQueryHandler(edit_therapist_gender_callback, pattern="^edit_th_gender_"),
                CallbackQueryHandler(schedule_inactive_callback, pattern="^schedule_inactive_"),
                CallbackQueryHandler(cancel_inactive_schedule_callback, pattern="^cancel_inactive_"),
                CallbackQueryHandler(delete_therapist_confirm_callback, pattern="^delther_"),
                CallbackQueryHandler(admin_therapists_callback, pattern="^admin_therapists$"),
                CallbackQueryHandler(therapist_detail_callback, pattern="^th_detail_"),
                CallbackQueryHandler(back_to_start_callback, pattern="^back_to_start$")
            ],
            A_SCHEDULE_INACTIVE: [
                CallbackQueryHandler(schedule_inactive_duration_callback, pattern="^inactive_dur_"),
                CallbackQueryHandler(schedule_inactive_custom_callback, pattern="^inactive_custom_"),
                CallbackQueryHandler(therapist_detail_callback, pattern="^th_detail_")
            ],
            A_INACTIVE_CUSTOM_DAYS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, schedule_inactive_custom_days_text),
                CallbackQueryHandler(therapist_detail_callback, pattern="^th_detail_")
            ],
            A_EDIT_TH_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, edit_therapist_name_text),
                CallbackQueryHandler(therapist_detail_callback, pattern="^th_detail_")
            ],
            A_EDIT_TH_GENDER: [
                CallbackQueryHandler(set_therapist_gender_callback, pattern="^set_gender_[mf]_"),
                CallbackQueryHandler(therapist_detail_callback, pattern="^th_detail_")
            ],
            A_DELETE_APPT: [
                CallbackQueryHandler(delete_appointment_confirm_callback, pattern="^(delappt_|admin_menu)"),
                CallbackQueryHandler(back_to_start_callback, pattern="^back_to_start$")
            ],
            A_HOLIDAY_MENU: [
                CallbackQueryHandler(add_holiday_date_callback, pattern="^add_holiday_date$"),
                CallbackQueryHandler(admin_menu_callback, pattern="^admin_menu$"),
                CallbackQueryHandler(back_to_start_callback, pattern="^back_to_start$")
            ],
            A_ADD_HOL_DATE: [
                CallbackQueryHandler(add_holiday_date_selected_callback, pattern="^date_"),
                CallbackQueryHandler(holiday_calendar_nav_callback, pattern="^cal_(prev|next)_"),
                CallbackQueryHandler(holiday_calendar_noop_callback, pattern="^cal_noop$"),
                CallbackQueryHandler(admin_holidays_callback, pattern="^admin_holidays$"),
                CallbackQueryHandler(back_to_start_callback, pattern="^back_to_start$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, add_holiday_date_text)
            ],
            A_VIEW_APPT: [
                CallbackQueryHandler(manage_appointment_callback, pattern="^mgappt_"),
                CallbackQueryHandler(appt_page_nav_callback, pattern="^appt_page_(next|prev)$"),
                CallbackQueryHandler(admin_menu_callback, pattern="^admin_menu$"),
                CallbackQueryHandler(back_to_start_callback, pattern="^back_to_start$")
            ],
            A_MANAGE_APPT: [
                CallbackQueryHandler(manage_appointment_callback, pattern="^mgappt_"),
                CallbackQueryHandler(view_appointment_callback, pattern="^view_appointment$"),
                CallbackQueryHandler(change_status_menu_callback, pattern="^change_status_menu$"),
                CallbackQueryHandler(change_status_confirm_callback, pattern="^chgstatus_"),
                CallbackQueryHandler(edit_appt_menu_callback, pattern="^edit_appt_menu$"),
                CallbackQueryHandler(delete_appointment_confirm_callback, pattern="^delappt_"),
                CallbackQueryHandler(admin_menu_callback, pattern="^admin_menu$"),
                CallbackQueryHandler(back_to_start_callback, pattern="^back_to_start$")
            ],
            A_EDIT_APPT_FIELD: [
                CallbackQueryHandler(edit_field_select_callback, pattern="^editfield_"),
                CallbackQueryHandler(manage_appointment_callback, pattern="^mgappt_"),
                CallbackQueryHandler(edit_appt_menu_callback, pattern="^edit_appt_menu$"),
                CallbackQueryHandler(back_to_start_callback, pattern="^back_to_start$")
            ],
            A_EDIT_APPT_VALUE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, edit_appt_value_text),
                CallbackQueryHandler(edit_therapist_confirm_callback, pattern="^settherapist_"),
                CallbackQueryHandler(edit_appt_menu_callback, pattern="^edit_appt_menu$"),
                CallbackQueryHandler(back_to_start_callback, pattern="^back_to_start$")
            ],
            A_WAITLIST_MANAGE: [
                CallbackQueryHandler(view_waitlist_entry_callback, pattern="^wl_view_"),
                CallbackQueryHandler(confirm_slot_available_callback, pattern="^wl_confirm_"),
                CallbackQueryHandler(inform_waitlist_full_callback, pattern="^wl_inform_full_"),
                CallbackQueryHandler(delete_waitlist_entry_callback, pattern="^wl_delete_"),
                CallbackQueryHandler(admin_waitlist_callback, pattern="^admin_waitlist$"),
                CallbackQueryHandler(admin_menu_callback, pattern="^admin_menu$"),
                CallbackQueryHandler(back_to_start_callback, pattern="^back_to_start$")
            ]
        },
        fallbacks=[
            CommandHandler("cancel", cancel_cmd),
            CommandHandler("help", help_cmd),
            MessageHandler(filters.ALL & ~filters.COMMAND, fallback_handler),
            CallbackQueryHandler(fallback_handler)
        ],
        conversation_timeout=600,
        name="main_conversation",
        persistent=True,
        allow_reentry=True
    )
    
    application.add_handler(main_conv_handler)
    
    application.add_error_handler(error_handler)
    
    global_scheduler = AsyncIOScheduler()
    global_scheduler.start()
    logger.info("Dynamic reminder scheduler started")
    
    schedule_sunnah_notifications(global_scheduler, application)
    logger.info("Sunnah notification scheduler configured")
    
    setup_therapist_activator(global_scheduler)
    logger.info("Therapist auto-activator scheduler configured")
    
    setup_prayer_prefetch_scheduler(global_scheduler)
    logger.info("Prayer times pre-fetch scheduler configured")
    
    logger.info("Bot is running with session persistence. Press Ctrl+C to stop.")
    application.run_polling(allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    main()
