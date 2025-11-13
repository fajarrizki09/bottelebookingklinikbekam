THERAPISTS_TABLE = """
CREATE TABLE IF NOT EXISTS therapists (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    gender TEXT NOT NULL,
    active INTEGER DEFAULT 1,
    inactive_start TEXT DEFAULT NULL,
    inactive_end TEXT DEFAULT NULL
)
"""

APPOINTMENTS_TABLE = """
CREATE TABLE IF NOT EXISTS appointments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    user_name TEXT NOT NULL,
    patient_gender TEXT NOT NULL,
    patient_address TEXT DEFAULT '',
    therapist_id INTEGER NOT NULL,
    start_dt TEXT NOT NULL,
    duration_min INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'confirmed',
    created_at TEXT NOT NULL,
    reminder_job_id TEXT DEFAULT NULL,
    FOREIGN KEY (therapist_id) REFERENCES therapists(id)
)
"""

WAITLIST_TABLE = """
CREATE TABLE IF NOT EXISTS waitlist (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    phone TEXT,
    gender TEXT NOT NULL,
    requested_date TEXT,
    created_at TEXT NOT NULL
)
"""

HOLIDAY_WEEKLY_TABLE = """
CREATE TABLE IF NOT EXISTS holiday_weekly (
    weekday INTEGER PRIMARY KEY
)
"""

HOLIDAY_DATES_TABLE = """
CREATE TABLE IF NOT EXISTS holiday_dates (
    date TEXT PRIMARY KEY
)
"""

BROADCASTS_TABLE = """
CREATE TABLE IF NOT EXISTS broadcasts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    admin_id INTEGER NOT NULL,
    message TEXT NOT NULL,
    status TEXT DEFAULT 'draft',
    sent_count INTEGER DEFAULT 0,
    failed_count INTEGER DEFAULT 0,
    created_at TEXT NOT NULL,
    completed_at TEXT DEFAULT NULL
)
"""

DAILY_HEALTH_CONTENT_TABLE = """
CREATE TABLE IF NOT EXISTS daily_health_content (
    date TEXT PRIMARY KEY,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL
)
"""

PRAYER_TIMES_CACHE_TABLE = """
CREATE TABLE IF NOT EXISTS prayer_times_cache (
    date TEXT PRIMARY KEY,
    fajr TEXT NOT NULL,
    dhuhr TEXT NOT NULL,
    asr TEXT NOT NULL,
    maghrib TEXT NOT NULL,
    isha TEXT NOT NULL,
    created_at TEXT NOT NULL
)
"""

SEED_THERAPISTS = [
    ("Pak Marsudi", "Laki-laki"),
    ("Mba Tyas", "Perempuan"),
    ("Pak Irfan", "Laki-laki"),
    ("Mba Nurul", "Perempuan"),
]

SEED_HOLIDAY_WEEKLY = [2]
