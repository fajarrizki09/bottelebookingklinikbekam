import aiosqlite
import logging
from datetime import datetime, date
from typing import Optional
from config import Config
from database.models import (
    THERAPISTS_TABLE, APPOINTMENTS_TABLE, WAITLIST_TABLE,
    HOLIDAY_WEEKLY_TABLE, HOLIDAY_DATES_TABLE, BROADCASTS_TABLE,
    DAILY_HEALTH_CONTENT_TABLE, PRAYER_TIMES_CACHE_TABLE,
    SEED_THERAPISTS, SEED_HOLIDAY_WEEKLY
)
from utils.datetime_helper import now_jakarta, overlaps, from_iso

logger = logging.getLogger(__name__)


class Database:
    def __init__(self, db_path: str = Config.DB_PATH):
        self.db_path = db_path
        self.conn: Optional[aiosqlite.Connection] = None
    
    async def connect(self):
        self.conn = await aiosqlite.connect(self.db_path)
        self.conn.row_factory = aiosqlite.Row
        await self._create_tables()
        await self._migrate_add_inactive_columns()
        await self._migrate_add_waitlist_phone()
        await self._seed_data()
        logger.info(f"Database connected: {self.db_path}")
    
    async def close(self):
        if self.conn:
            await self.conn.close()
            logger.info("Database connection closed")
    
    async def _create_tables(self):
        await self.conn.execute(THERAPISTS_TABLE)
        await self.conn.execute(APPOINTMENTS_TABLE)
        await self.conn.execute(WAITLIST_TABLE)
        await self.conn.execute(HOLIDAY_WEEKLY_TABLE)
        await self.conn.execute(HOLIDAY_DATES_TABLE)
        await self.conn.execute(BROADCASTS_TABLE)
        await self.conn.execute(DAILY_HEALTH_CONTENT_TABLE)
        await self.conn.execute(PRAYER_TIMES_CACHE_TABLE)
        await self.conn.commit()
    
    async def _migrate_add_inactive_columns(self):
        try:
            cursor = await self.conn.execute("PRAGMA table_info(therapists)")
            columns = await cursor.fetchall()
            column_names = [col[1] for col in columns]
            
            if 'inactive_start' not in column_names:
                await self.conn.execute("ALTER TABLE therapists ADD COLUMN inactive_start TEXT DEFAULT NULL")
                logger.info("Migration: Added inactive_start column to therapists table")
            
            if 'inactive_end' not in column_names:
                await self.conn.execute("ALTER TABLE therapists ADD COLUMN inactive_end TEXT DEFAULT NULL")
                logger.info("Migration: Added inactive_end column to therapists table")
            
            await self.conn.commit()
        except Exception as e:
            logger.error(f"Migration error: {e}")
    
    async def _migrate_add_waitlist_phone(self):
        try:
            cursor = await self.conn.execute("PRAGMA table_info(waitlist)")
            columns = await cursor.fetchall()
            column_names = [col[1] for col in columns]
            
            if 'phone' not in column_names:
                await self.conn.execute("ALTER TABLE waitlist ADD COLUMN phone TEXT")
                logger.info("Migration: Added phone column to waitlist table")
            
            await self.conn.commit()
        except Exception as e:
            logger.error(f"Migration error for waitlist: {e}")
    
    async def _seed_data(self):
        cursor = await self.conn.execute("SELECT COUNT(*) FROM therapists")
        count = await cursor.fetchone()
        
        if count[0] == 0:
            await self.conn.executemany(
                "INSERT INTO therapists (name, gender, active) VALUES (?, ?, 1)",
                SEED_THERAPISTS
            )
            logger.info("Seeded therapists table")
        
        for weekday in SEED_HOLIDAY_WEEKLY:
            await self.conn.execute(
                "INSERT OR IGNORE INTO holiday_weekly (weekday) VALUES (?)",
                (weekday,)
            )
        
        await self.conn.commit()
        logger.info("Database seeding completed")
    
    async def get_therapists(self, active_only: bool = True):
        query = "SELECT id, name, gender, active, inactive_start, inactive_end FROM therapists"
        if active_only:
            query += " WHERE active = 1"
        query += " ORDER BY name"
        
        cursor = await self.conn.execute(query)
        return await cursor.fetchall()
    
    async def get_therapist(self, therapist_id: int):
        cursor = await self.conn.execute(
            "SELECT id, name, gender, active, inactive_start, inactive_end FROM therapists WHERE id = ?",
            (therapist_id,)
        )
        return await cursor.fetchone()
    
    async def add_therapist(self, name: str, gender: str):
        cursor = await self.conn.execute(
            "INSERT INTO therapists (name, gender, active) VALUES (?, ?, 1)",
            (name, gender)
        )
        await self.conn.commit()
        return cursor.lastrowid
    
    async def delete_therapist(self, therapist_id: int):
        await self.conn.execute(
            "DELETE FROM therapists WHERE id = ?",
            (therapist_id,)
        )
        await self.conn.commit()
    
    async def update_therapist(self, therapist_id: int, name: str = None, gender: str = None):
        updates = []
        params = []
        
        if name is not None:
            updates.append("name = ?")
            params.append(name)
        
        if gender is not None:
            updates.append("gender = ?")
            params.append(gender)
        
        if not updates:
            return
        
        params.append(therapist_id)
        query = f"UPDATE therapists SET {', '.join(updates)} WHERE id = ?"
        
        await self.conn.execute(query, params)
        await self.conn.commit()
    
    async def toggle_therapist_active(self, therapist_id: int):
        cursor = await self.conn.execute(
            "SELECT active FROM therapists WHERE id = ?",
            (therapist_id,)
        )
        row = await cursor.fetchone()
        
        if not row:
            return False
        
        new_status = 0 if row['active'] == 1 else 1
        
        await self.conn.execute(
            "UPDATE therapists SET active = ?, inactive_start = NULL, inactive_end = NULL WHERE id = ?",
            (new_status, therapist_id)
        )
        await self.conn.commit()
        return new_status == 1
    
    async def schedule_therapist_inactive(self, therapist_id: int, inactive_start: str, inactive_end: str):
        now = now_jakarta().isoformat()
        from_iso_start = from_iso(inactive_start)
        
        if from_iso_start <= now_jakarta():
            await self.conn.execute(
                "UPDATE therapists SET active = 0, inactive_start = ?, inactive_end = ? WHERE id = ?",
                (inactive_start, inactive_end, therapist_id)
            )
        else:
            await self.conn.execute(
                "UPDATE therapists SET inactive_start = ?, inactive_end = ? WHERE id = ?",
                (inactive_start, inactive_end, therapist_id)
            )
        
        await self.conn.commit()
        logger.info(f"Therapist {therapist_id} scheduled inactive from {inactive_start} to {inactive_end}")
    
    async def get_therapists_to_deactivate(self):
        now = now_jakarta().isoformat()
        cursor = await self.conn.execute(
            "SELECT id, name, inactive_start FROM therapists WHERE active = 1 AND inactive_start IS NOT NULL AND inactive_start <= ? AND inactive_end IS NOT NULL",
            (now,)
        )
        return await cursor.fetchall()
    
    async def deactivate_therapist(self, therapist_id: int):
        await self.conn.execute(
            "UPDATE therapists SET active = 0 WHERE id = ?",
            (therapist_id,)
        )
        await self.conn.commit()
        logger.info(f"Therapist {therapist_id} deactivated")
    
    async def get_therapists_to_reactivate(self):
        now = now_jakarta().isoformat()
        cursor = await self.conn.execute(
            "SELECT id, name, inactive_end FROM therapists WHERE active = 0 AND inactive_end IS NOT NULL AND inactive_end <= ?",
            (now,)
        )
        return await cursor.fetchall()
    
    async def reactivate_therapist(self, therapist_id: int):
        await self.conn.execute(
            "UPDATE therapists SET active = 1, inactive_start = NULL, inactive_end = NULL WHERE id = ?",
            (therapist_id,)
        )
        await self.conn.commit()
        logger.info(f"Therapist {therapist_id} reactivated")
    
    async def cancel_scheduled_inactive(self, therapist_id: int):
        await self.conn.execute(
            "UPDATE therapists SET active = 1, inactive_start = NULL, inactive_end = NULL WHERE id = ?",
            (therapist_id,)
        )
        await self.conn.commit()
        logger.info(f"Cancelled inactive schedule for therapist {therapist_id}")
    
    async def therapist_free(self, therapist_id: int, start_iso: str, duration_min: int) -> bool:
        start_dt = from_iso(start_iso)
        
        cursor = await self.conn.execute(
            "SELECT inactive_start, inactive_end FROM therapists WHERE id = ?",
            (therapist_id,)
        )
        therapist = await cursor.fetchone()
        
        if therapist and therapist['inactive_start'] and therapist['inactive_end']:
            inactive_start_dt = from_iso(therapist['inactive_start'])
            inactive_end_dt = from_iso(therapist['inactive_end'])
            inactive_duration = int((inactive_end_dt - inactive_start_dt).total_seconds() / 60)
            
            if overlaps(start_dt, duration_min, therapist['inactive_start'], inactive_duration):
                return False
        
        cursor = await self.conn.execute(
            "SELECT start_dt, duration_min FROM appointments WHERE therapist_id = ? AND status = 'confirmed'",
            (therapist_id,)
        )
        appointments = await cursor.fetchall()
        
        for appt in appointments:
            if overlaps(start_dt, duration_min, appt['start_dt'], appt['duration_min']):
                return False
        
        return True
    
    async def add_appointment(
        self, user_id: int, user_name: str, patient_gender: str,
        therapist_id: int, start_dt: str, duration_min: int, patient_address: str = ""
    ):
        created_at = now_jakarta().isoformat()
        cursor = await self.conn.execute(
            """INSERT INTO appointments 
            (user_id, user_name, patient_gender, patient_address, therapist_id, start_dt, duration_min, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'confirmed', ?)""",
            (user_id, user_name, patient_gender, patient_address, therapist_id, start_dt, duration_min, created_at)
        )
        await self.conn.commit()
        return cursor.lastrowid
    
    async def get_appointments(self, status: Optional[str] = None):
        query = """
        SELECT a.id, a.user_id, a.user_name, a.patient_gender, a.patient_address, a.therapist_id,
               a.start_dt, a.duration_min, a.status, a.created_at,
               t.name as therapist_name
        FROM appointments a
        LEFT JOIN therapists t ON a.therapist_id = t.id
        """
        if status:
            query += " WHERE a.status = ?"
            cursor = await self.conn.execute(query, (status,))
        else:
            cursor = await self.conn.execute(query)
        
        return await cursor.fetchall()
    
    async def get_upcoming_appointments(self):
        now = now_jakarta().isoformat()
        cursor = await self.conn.execute(
            """
            SELECT a.id, a.user_id, a.user_name, a.patient_gender, a.patient_address, a.therapist_id,
                   a.start_dt, a.duration_min, a.status, a.created_at,
                   t.name as therapist_name
            FROM appointments a
            LEFT JOIN therapists t ON a.therapist_id = t.id
            WHERE a.status = 'confirmed' AND a.start_dt > ?
            ORDER BY a.start_dt ASC
            """,
            (now,)
        )
        return await cursor.fetchall()
    
    async def get_all_appointments_for_admin(self, limit: int = 50, offset: int = 0):
        cursor = await self.conn.execute(
            """
            SELECT a.id, a.user_id, a.user_name, a.patient_gender, a.patient_address, a.therapist_id,
                   a.start_dt, a.duration_min, a.status, a.created_at,
                   t.name as therapist_name
            FROM appointments a
            LEFT JOIN therapists t ON a.therapist_id = t.id
            ORDER BY a.start_dt DESC
            LIMIT ? OFFSET ?
            """,
            (limit, offset)
        )
        return await cursor.fetchall()
    
    async def get_user_appointments(self, user_id: int, limit: int = 20, offset: int = 0):
        cursor = await self.conn.execute(
            """
            SELECT a.id, a.user_id, a.user_name, a.patient_gender, a.patient_address, a.therapist_id,
                   a.start_dt, a.duration_min, a.status, a.created_at,
                   t.name as therapist_name
            FROM appointments a
            LEFT JOIN therapists t ON a.therapist_id = t.id
            WHERE a.user_id = ?
            ORDER BY a.start_dt DESC
            LIMIT ? OFFSET ?
            """,
            (user_id, limit, offset)
        )
        return await cursor.fetchall()
    
    async def get_user_upcoming_appointments(self, user_id: int):
        now = now_jakarta().isoformat()
        cursor = await self.conn.execute(
            """
            SELECT a.id, a.user_id, a.user_name, a.patient_gender, a.patient_address, a.therapist_id,
                   a.start_dt, a.duration_min, a.status, a.created_at,
                   t.name as therapist_name
            FROM appointments a
            LEFT JOIN therapists t ON a.therapist_id = t.id
            WHERE a.user_id = ? AND a.status = 'confirmed' AND a.start_dt > ?
            ORDER BY a.start_dt ASC
            """,
            (user_id, now)
        )
        return await cursor.fetchall()
    
    async def cancel_appointment(self, appointment_id: int):
        appt = await self.get_appointment_by_id(appointment_id)
        if appt and appt['status'] != 'cancelled':
            await self.conn.execute(
                "UPDATE appointments SET status = 'cancelled' WHERE id = ?",
                (appointment_id,)
            )
            await self.conn.commit()
            return appt
        return None
    
    async def delete_appointment(self, appointment_id: int):
        await self.conn.execute(
            "DELETE FROM appointments WHERE id = ?",
            (appointment_id,)
        )
        await self.conn.commit()
    
    async def get_appointment_by_id(self, appointment_id: int):
        cursor = await self.conn.execute(
            """
            SELECT a.id, a.user_id, a.user_name, a.patient_gender, a.patient_address, a.therapist_id,
                   a.start_dt, a.duration_min, a.status, a.created_at, a.reminder_job_id,
                   t.name as therapist_name
            FROM appointments a
            LEFT JOIN therapists t ON a.therapist_id = t.id
            WHERE a.id = ?
            """,
            (appointment_id,)
        )
        return await cursor.fetchone()
    
    async def update_appointment_status(self, appointment_id: int, new_status: str):
        appt = await self.get_appointment_by_id(appointment_id)
        old_status = appt['status'] if appt else None
        
        await self.conn.execute(
            "UPDATE appointments SET status = ? WHERE id = ?",
            (new_status, appointment_id)
        )
        await self.conn.commit()
        
        if appt and old_status != 'cancelled' and new_status == 'cancelled':
            return appt
        return None
    
    async def update_appointment(self, appointment_id: int, user_name: Optional[str] = None,
                                patient_address: Optional[str] = None, therapist_id: Optional[int] = None,
                                start_dt: Optional[str] = None, duration_min: Optional[int] = None,
                                reminder_job_id: Optional[str] = None):
        updates = []
        params = []
        
        if user_name is not None:
            updates.append("user_name = ?")
            params.append(user_name)
        if patient_address is not None:
            updates.append("patient_address = ?")
            params.append(patient_address)
        if therapist_id is not None:
            updates.append("therapist_id = ?")
            params.append(therapist_id)
        if start_dt is not None:
            updates.append("start_dt = ?")
            params.append(start_dt)
        if duration_min is not None:
            updates.append("duration_min = ?")
            params.append(duration_min)
        if reminder_job_id is not None:
            updates.append("reminder_job_id = ?")
            params.append(reminder_job_id)
        
        if updates:
            params.append(appointment_id)
            query = f"UPDATE appointments SET {', '.join(updates)} WHERE id = ?"
            await self.conn.execute(query, tuple(params))
            await self.conn.commit()
    
    async def add_to_waitlist(self, chat_id: int, name: str, gender: str, phone: Optional[str] = None, requested_date: Optional[str] = None):
        created_at = now_jakarta().isoformat()
        cursor = await self.conn.execute(
            "INSERT INTO waitlist (chat_id, name, phone, gender, requested_date, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (chat_id, name, phone, gender, requested_date or "", created_at)
        )
        await self.conn.commit()
        return cursor.lastrowid
    
    async def get_waitlist(self):
        cursor = await self.conn.execute(
            "SELECT id, chat_id, name, phone, gender, requested_date, created_at FROM waitlist ORDER BY created_at"
        )
        return await cursor.fetchall()
    
    async def get_waitlist_entry(self, waitlist_id: int):
        cursor = await self.conn.execute(
            "SELECT id, chat_id, name, phone, gender, requested_date, created_at FROM waitlist WHERE id = ?",
            (waitlist_id,)
        )
        return await cursor.fetchone()
    
    async def delete_waitlist_entry(self, waitlist_id: int):
        await self.conn.execute(
            "DELETE FROM waitlist WHERE id = ?",
            (waitlist_id,)
        )
        await self.conn.commit()
    
    async def get_waitlist_by_date(self, date_iso: str):
        cursor = await self.conn.execute(
            """
            SELECT id, chat_id, user_id, name, gender, requested_date, created_at
            FROM waitlist
            WHERE requested_date = ?
            ORDER BY created_at ASC
            """,
            (date_iso,)
        )
        return await cursor.fetchall()
    
    async def is_weekly_holiday(self, date_obj: date) -> bool:
        cursor = await self.conn.execute(
            "SELECT 1 FROM holiday_weekly WHERE weekday = ?",
            (date_obj.weekday(),)
        )
        return await cursor.fetchone() is not None
    
    async def is_date_holiday(self, date_obj: date) -> bool:
        cursor = await self.conn.execute(
            "SELECT 1 FROM holiday_dates WHERE date = ?",
            (date_obj.isoformat(),)
        )
        return await cursor.fetchone() is not None
    
    async def add_holiday_date(self, date_obj: date):
        await self.conn.execute(
            "INSERT OR IGNORE INTO holiday_dates (date) VALUES (?)",
            (date_obj.isoformat(),)
        )
        await self.conn.commit()
    
    async def remove_holiday_date(self, date_obj: date):
        await self.conn.execute(
            "DELETE FROM holiday_dates WHERE date = ?",
            (date_obj.isoformat(),)
        )
        await self.conn.commit()
    
    async def add_holiday_weekly(self, weekday: int):
        await self.conn.execute(
            "INSERT OR IGNORE INTO holiday_weekly (weekday) VALUES (?)",
            (weekday,)
        )
        await self.conn.commit()
    
    async def remove_holiday_weekly(self, weekday: int):
        await self.conn.execute(
            "DELETE FROM holiday_weekly WHERE weekday = ?",
            (weekday,)
        )
        await self.conn.commit()
    
    async def get_holiday_dates(self):
        cursor = await self.conn.execute("SELECT date FROM holiday_dates ORDER BY date")
        return await cursor.fetchall()
    
    async def get_holiday_weekly(self):
        cursor = await self.conn.execute("SELECT weekday FROM holiday_weekly ORDER BY weekday")
        return await cursor.fetchall()
    
    async def create_broadcast(self, admin_id: int, message: str, status: str = 'draft'):
        created_at = now_jakarta().isoformat()
        cursor = await self.conn.execute(
            "INSERT INTO broadcasts (admin_id, message, status, created_at) VALUES (?, ?, ?, ?)",
            (admin_id, message, status, created_at)
        )
        await self.conn.commit()
        return cursor.lastrowid
    
    async def update_broadcast_progress(self, broadcast_id: int, sent_count: int, failed_count: int):
        await self.conn.execute(
            "UPDATE broadcasts SET sent_count = ?, failed_count = ? WHERE id = ?",
            (sent_count, failed_count, broadcast_id)
        )
        await self.conn.commit()
    
    async def complete_broadcast(self, broadcast_id: int):
        completed_at = now_jakarta().isoformat()
        await self.conn.execute(
            "UPDATE broadcasts SET status = 'completed', completed_at = ? WHERE id = ?",
            (completed_at, broadcast_id)
        )
        await self.conn.commit()
    
    async def get_all_user_chat_ids(self):
        cursor = await self.conn.execute(
            "SELECT DISTINCT user_id FROM appointments UNION SELECT DISTINCT chat_id FROM waitlist"
        )
        rows = await cursor.fetchall()
        return [row[0] for row in rows]
    
    async def get_daily_health_content(self, date_str: str):
        cursor = await self.conn.execute(
            "SELECT content FROM daily_health_content WHERE date = ?",
            (date_str,)
        )
        row = await cursor.fetchone()
        return row['content'] if row else None
    
    async def save_daily_health_content(self, date_str: str, content: str):
        created_at = now_jakarta().isoformat()
        await self.conn.execute(
            "INSERT OR REPLACE INTO daily_health_content (date, content, created_at) VALUES (?, ?, ?)",
            (date_str, content, created_at)
        )
        await self.conn.commit()
    
    async def save_prayer_times(self, date_str: str, fajr: str, dhuhr: str, asr: str, maghrib: str, isha: str):
        created_at = now_jakarta().isoformat()
        await self.conn.execute(
            "INSERT OR REPLACE INTO prayer_times_cache (date, fajr, dhuhr, asr, maghrib, isha, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (date_str, fajr, dhuhr, asr, maghrib, isha, created_at)
        )
        await self.conn.commit()
        logger.debug(f"Saved prayer times for {date_str}")
    
    async def get_prayer_times_for_date(self, date_str: str):
        cursor = await self.conn.execute(
            "SELECT date, fajr, dhuhr, asr, maghrib, isha FROM prayer_times_cache WHERE date = ?",
            (date_str,)
        )
        return await cursor.fetchone()
    
    async def get_prayer_times_range(self, start_date: str, end_date: str):
        cursor = await self.conn.execute(
            "SELECT date, fajr, dhuhr, asr, maghrib, isha FROM prayer_times_cache WHERE date >= ? AND date <= ? ORDER BY date",
            (start_date, end_date)
        )
        return await cursor.fetchall()
    
    async def clear_old_prayer_times(self, before_date: str):
        await self.conn.execute(
            "DELETE FROM prayer_times_cache WHERE date < ?",
            (before_date,)
        )
        await self.conn.commit()
        logger.info(f"Cleared prayer times cache before {before_date}")


db = Database()
