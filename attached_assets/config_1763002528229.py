import os
import sys
from dotenv import load_dotenv

load_dotenv()


class Config:
    TOKEN = os.getenv("TOKEN", "")
    
    ADMIN_IDS_STR = os.getenv("ADMIN_IDS", "")
    ADMIN_IDS = [int(x.strip()) for x in ADMIN_IDS_STR.split(",") if x.strip().isdigit()]
    
    DB_PATH = os.getenv("DB_PATH", "bekam.db")
    PERSISTENCE_PATH = os.getenv("PERSISTENCE_PATH", "bot_persistence.pkl")
    TIMEZONE = os.getenv("TIMEZONE", "Asia/Jakarta")
    
    START_HOUR = int(os.getenv("START_HOUR", "9"))
    END_HOUR = int(os.getenv("END_HOUR", "18"))
    BREAK_START_HOUR = int(os.getenv("BREAK_START_HOUR", "12"))
    BREAK_END_HOUR = int(os.getenv("BREAK_END_HOUR", "13"))
    
    INTERVAL_MINUTES = int(os.getenv("INTERVAL_MINUTES", "40"))
    SESSION_MINUTES = int(os.getenv("SESSION_MINUTES", os.getenv("INTERVAL_MINUTES", "40")))
    MAX_DAYS_AHEAD = int(os.getenv("MAX_DAYS_AHEAD", "30"))
    PRAYER_PREFETCH_DAYS = int(os.getenv("PRAYER_PREFETCH_DAYS", "30"))
    
    REMINDER_MINUTES_BEFORE = int(os.getenv("REMINDER_MINUTES_BEFORE", "30"))
    MIN_BOOKING_BUFFER_MINUTES = int(os.getenv("MIN_BOOKING_BUFFER_MINUTES", "5"))
    
    @classmethod
    def validate(cls):
        errors = []
        
        if not cls.TOKEN:
            errors.append("TOKEN is required in .env file")
        
        if not cls.ADMIN_IDS:
            errors.append("ADMIN_IDS is required and must contain valid integers")
        
        if cls.START_HOUR < 0 or cls.START_HOUR > 23:
            errors.append("START_HOUR must be between 0 and 23")
        
        if cls.END_HOUR < 0 or cls.END_HOUR > 23:
            errors.append("END_HOUR must be between 0 and 23")
        
        if cls.START_HOUR >= cls.END_HOUR:
            errors.append("START_HOUR must be less than END_HOUR")
        
        if cls.INTERVAL_MINUTES < 1:
            errors.append("INTERVAL_MINUTES must be at least 1")
        
        if cls.SESSION_MINUTES < 1:
            errors.append("SESSION_MINUTES must be at least 1")
        
        if errors:
            print("Configuration errors:")
            for error in errors:
                print(f"  - {error}")
            sys.exit(1)
        
        print("Configuration validated successfully")


Config.validate()
