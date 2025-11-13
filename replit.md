# Overview

This is a Telegram bot for managing appointments at "Rumah Sehat Dani Sabri," a healthcare facility specializing in cupping therapy (bekam). The bot allows patients to book appointments with therapists based on gender preferences, view their appointments, and receive reminders. It includes Islamic calendar integration for sunnah cupping dates and provides daily health tips. Administrators can manage therapists, appointments, waitlists, holidays, and broadcast messages to users.

# Recent Changes

## November 13, 2025 (Latest)
- **Admin Waitlist Phone Number Bug Fix**: Completely resolved phone number display issue in admin panel waitlist management:
  - **Root Cause**: `get_waitlist_entry()` SQL query was missing `phone` column in SELECT statement, causing phone data not to be retrieved
  - **Secondary Issue**: Code used `aiosqlite.Row.get()` method which doesn't exist, would cause AttributeError
  - **Fix Applied**:
    1. Added `phone` column to `get_waitlist_entry()` SELECT query in `database/db.py`
    2. Implemented defensive row-to-dict conversion in `handlers/admin.py` for both `admin_waitlist_callback()` and `view_waitlist_entry_callback()`
    3. Changed from `item.get('phone')` to `dict(item).get('phone') or 'Tidak ada'` for safe NULL handling
  - **Result**: Phone numbers now display correctly in both waitlist list view (button labels) and detail view (contact information)
  - **Edge Cases Handled**: NULL phone values from pre-migration records safely display as "Tidak ada"
  - Rationale: Admin needs contact information to follow up with users on waitlist. Previous code would crash or fail to display phone numbers despite them being stored in database
- **Prayer Times API Critical Fix**: Resolved excessive API requests and HTTP 302 redirect errors:
  - Root cause 1: Missing `httpx` package in requirements.txt (code used httpx but package wasn't installed, causing import failures)
  - Root cause 2: Aladhan API endpoint format changed - now requires date as path parameter instead of query parameter
  - Fixed requirements.txt: Replaced `requests==2.32.3` with `httpx==0.28.1` 
  - Fixed prayer_times.py: Changed URL format from `/v1/timings?date=DD-MM-YYYY&...` to `/v1/timings/DD-MM-YYYY?...`
  - Result: Bot now successfully pre-fetches 30 days of prayer times with HTTP 200 responses (no more 302 redirects)
  - Performance: Prayer times pre-fetch completes in ~6 seconds for 30 days, all subsequent requests use database cache
  - Rationale: HTTP 302 redirects caused excessive API calls and blocked event loop, making bot unresponsive. New URL format eliminates redirects entirely.

## November 12, 2025
- **Prayer Times API Optimization**: Drastically improved bot responsiveness by eliminating blocking API requests:
  - Added persistent database cache (`prayer_times_cache` table) that survives bot restarts
  - Implemented async prayer times fetching using `httpx.AsyncClient` instead of blocking `requests`
  - Added daily pre-fetch scheduler (runs at 00:00 WIB) that caches 30 days of prayer times ahead
  - Added startup pre-fetch that automatically populates cache when bot initializes
  - Reduced prayer times fetch from 8+ seconds to <1 second (30 days) using async HTTP
  - Made `generate_time_slots()` async and updated all 4 calling sites with `await`
  - Rationale: Original synchronous requests blocked the event loop during booking flows, causing poor UX. New approach: 1 API call per day (pre-fetch) instead of multiple calls per booking, with database-first caching strategy.
- **Appointment Status Update Fix**: Created `utils/waitlist_notify.py` module to resolve crash when updating appointment status to "selesai". Module provides placeholder for future waitlist notification feature.
- **Calendar Visual Optimization**: Replaced emoji indicators with text-based notation for better performance and clarity:
  - Plain number (e.g., "1") = Available dates (clickable)
  - Number in brackets (e.g., "[1]") = Full/unavailable dates
  - Number in parentheses (e.g., "(1)") = Past dates
  - Rationale: Telegram inline keyboard buttons don't support HTML/CSS color formatting. Text notation provides clear visual distinction without emoji rendering overhead.
- **Gender Filter Bug Fix**: Fixed critical bug in "Lihat Semua Terapis" button where users could select therapists of opposite gender. Now properly filters by patient's selected gender.
- **Enhanced Error Logging**: Added `log_error_with_context()` helper that captures user_id, username, callback_data, and user context for better debugging
- **Improved Button Responsiveness**: Wrapped critical callbacks with proper error handling and ensured all buttons respond instantly with `await query.answer()`
- **Prayer Times API Fix**: Changed from city/country endpoint to latitude/longitude endpoint for more reliable prayer time fetching
- **Smart Caching**: Optimized prayer times caching to only store successful responses, allowing retry on transient failures
- **Performance**: Reduced API calls by grouping slots by date in filter function

# User Preferences

Preferred communication style: Simple, everyday language.
Calendar display preference: Text-based notation without emojis for faster rendering (plain number=available, [number]=full, (number)=past).

# System Architecture

## Bot Framework
- **Technology**: Python-based Telegram bot using `python-telegram-bot` library (version 22.5)
- **Conversation Management**: Multi-state conversation handlers with persistent state using pickle files
- **Rationale**: Telegram provides a familiar interface for Indonesian users, with built-in message formatting and inline keyboards for interactive workflows

## Data Storage
- **Database**: SQLite via `aiosqlite` for async operations
- **Schema Design**:
  - `therapists`: Stores therapist information with gender, active status, and scheduled inactive periods
  - `appointments`: Manages bookings with user info, therapist assignments, time slots, and status tracking
  - `waitlist`: Queues users when no slots are available
  - `holiday_weekly` and `holiday_dates`: Defines business closure days
  - `broadcasts`: Stores broadcast message history
  - `daily_health_content`: Caches AI-generated daily health tips
  - `prayer_times_cache`: Stores pre-fetched prayer times (persistent cache that survives restarts)
- **Rationale**: SQLite chosen for simplicity and zero-configuration deployment; sufficient for single-clinic appointment volumes

## Scheduling System
- **Scheduler**: APScheduler (AsyncIOScheduler) for background jobs
- **Key Jobs**:
  - Appointment reminders (30 minutes before scheduled time)
  - Sunnah date notifications (7, 3, 1 days before Islamic calendar dates)
  - Automatic therapist activation/deactivation based on scheduled inactive periods
  - Prayer times pre-fetch (daily at 00:00 WIB, caches 30 days ahead)
- **Time Management**: Asia/Jakarta timezone enforcement throughout, configurable working hours and break times
- **Rationale**: APScheduler integrates well with async Python, allowing scheduled tasks to run alongside the bot without separate processes

## Appointment Slot Generation
- **Algorithm**: Generates time slots based on configurable intervals (default 40 minutes), respecting:
  - Working hours (START_HOUR to END_HOUR)
  - Break periods (BREAK_START_HOUR to BREAK_END_HOUR)
  - Prayer times (20-minute buffer around Islamic prayer times via Aladhan API)
  - Holidays (weekly recurring and specific dates)
  - Therapist availability and gender matching
- **Conflict Detection**: Prevents overlapping appointments for the same therapist using datetime overlap calculation
- **Rationale**: Prayer time integration respects Islamic practice; gender matching ensures cultural appropriateness for cupping therapy

## User Interface Flow
- **User Journey**:
  1. Gender selection (for therapist matching)
  2. Interactive calendar date picker showing availability
  3. Time slot selection with visual indicators
  4. Therapist selection (if multiple available)
  5. Patient details collection (name, address)
  6. Confirmation before final booking
- **Admin Panel**: Separate conversation flow for managing therapists, viewing/editing appointments, handling waitlists, and configuring holidays
- **Rationale**: Step-by-step wizard reduces user errors; calendar UI provides visual availability feedback

## Islamic Calendar Integration
- **Library**: `hijri-converter` for Gregorian-Hijri date conversion
- **Sunnah Dates**: Automatically identifies days 17, 19, and 21 of each Hijri month as recommended cupping dates
- **Notifications**: Proactive messaging to all users about upcoming sunnah dates
- **Rationale**: Aligns with Islamic tradition that certain dates are optimal for cupping therapy

## Content Generation
- **Health Tips**: Optional OpenAI GPT-4o-mini integration for daily health content
- **Fallback**: Default health tips if API key not configured
- **Caching**: Daily tips cached in database to minimize API costs
- **Rationale**: Provides value-added content while maintaining functionality without external API dependency

## Configuration Management
- **Environment Variables**: All deployment-specific settings in `.env` file
- **Validation**: Config class validates critical settings at startup (token, admin IDs, time ranges)
- **Rationale**: Enables different configurations per environment without code changes; early validation prevents runtime failures

## State Persistence
- **Method**: PicklePersistence for conversation state
- **Scope**: Preserves user context across bot restarts
- **Rationale**: Users can resume interrupted booking flows without starting over

## Error Handling and Logging
- **Logging**: Standard Python logging throughout all modules
- **Timeout Handlers**: Conversation timeouts with graceful fallback to main menu
- **Rationale**: Comprehensive logging aids debugging; timeouts prevent stuck conversation states

## Modularity
- **Structure**:
  - `handlers/`: Separate modules for user flows, admin flows, and common functions
  - `database/`: Database abstraction layer
  - `utils/`: Reusable helpers for datetime, formatting, validation, calendar UI
  - `jobs/`: Background task definitions
  - `services/`: External service integrations
- **Rationale**: Clear separation of concerns improves maintainability and testability

# External Dependencies

## Telegram Bot API
- **Purpose**: Primary user interface and message delivery
- **Configuration**: Requires `TOKEN` in environment variables
- **Library**: `python-telegram-bot` v22.5

## OpenAI API (Optional)
- **Purpose**: Generate contextual daily health tips
- **Configuration**: `OPENAI_API_KEY` in environment (optional)
- **Model**: GPT-4o-mini for cost efficiency
- **Fallback**: System functions without API key using default content

## Aladhan Prayer Times API
- **Purpose**: Fetch Islamic prayer times for Jakarta
- **Endpoint**: `https://api.aladhan.com/v1/timings`
- **Parameters**: Uses latitude/longitude (-6.2088, 106.8456) for reliable results
- **Integration**: Used to block appointment slots during prayer times (20-minute buffer)
- **Caching Strategy**: 
  - **Database-first**: Checks persistent cache in `prayer_times_cache` table before API calls
  - **Daily pre-fetch**: Scheduler runs at 00:00 WIB to cache next 30 days (configurable via `PRAYER_PREFETCH_DAYS`)
  - **Startup pre-fetch**: Automatically populates cache when bot initializes
  - **API fallback**: Only makes external request if database cache misses
- **Performance**: 
  - Async implementation using `httpx.AsyncClient` (non-blocking)
  - Pre-fetch completes in < 1 second for 30 days
  - Reduces API calls from multiple per booking to 1 per day (scheduled)
  - Database cache survives bot restarts

## Hijri Calendar Conversion
- **Library**: `hijri-converter` v2.3.1
- **Purpose**: Convert between Gregorian and Hijri dates
- **Usage**: Identify sunnah cupping dates and display in Islamic calendar format

## Python Libraries
- **Core**:
  - `python-telegram-bot==22.5`: Bot framework
  - `aiosqlite==0.20.0`: Async SQLite operations
  - `apscheduler==3.10.4`: Job scheduling
  - `python-dotenv==1.0.1`: Environment variable management
  - `pytz==2024.2`: Timezone handling
  - `httpx==0.28.1`: Async HTTP client for prayer times API
- **Optional**:
  - `openai==1.58.1`: AI-generated content

## Database
- **Type**: SQLite (local file-based)
- **Location**: Configurable via `DB_PATH` environment variable (default: `bekam.db`)
- **Rationale**: No separate database server required; suitable for single-instance deployment