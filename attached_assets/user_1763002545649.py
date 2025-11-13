import logging
from datetime import date, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from database.db import db
from config import Config
from utils.datetime_helper import (
    format_date_id, format_datetime_id, format_datetime_short,
    parse_date, generate_time_slots, from_iso
)
from utils.formatters import format_confirmation_message, format_success_message
from utils.validators import is_valid_patient_name, is_valid_address, is_valid_phone
from utils.date_picker import create_calendar_keyboard, get_next_month, get_prev_month

logger = logging.getLogger(__name__)


def log_error_with_context(error: Exception, update: Update, context: ContextTypes.DEFAULT_TYPE, function_name: str):
    """Enhanced error logging dengan user_id, callback_data, dan context"""
    user_id = update.effective_user.id if update.effective_user else "Unknown"
    username = update.effective_user.username if update.effective_user else "Unknown"
    callback_data = update.callback_query.data if update.callback_query else "No callback"
    
    logger.error(
        f"ERROR in {function_name}\n"
        f"  User ID: {user_id} (@{username})\n"
        f"  Callback Data: {callback_data}\n"
        f"  User Data: {context.user_data}\n"
        f"  Error: {str(error)}",
        exc_info=True
    )

(S_START, S_PAT_GENDER, S_CHOOSE_DATE, S_CHOOSE_TIME,
 S_CHOOSE_THER, S_ASK_NAME, S_ASK_ADDRESS, S_CONFIRM,
 S_WAITLIST_NAME, S_WAITLIST_PHONE) = range(10)


async def make_appointment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    try:
        kb = [
            [InlineKeyboardButton("👨 Laki-laki", callback_data="pat_m")],
            [InlineKeyboardButton("👩 Perempuan", callback_data="pat_f")],
            [InlineKeyboardButton("🔙 Kembali", callback_data="back_to_start")]
        ]
        
        msg = (
            "👤 *JENIS KELAMIN PASIEN*\n\n"
            "Silakan pilih jenis kelamin pasien untuk mencocokkan dengan terapis yang sesuai:"
        )
        
        await query.edit_message_text(
            msg,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(kb)
        )
        
        return S_PAT_GENDER
    except Exception as e:
        log_error_with_context(e, update, context, "make_appointment_callback")
        await query.edit_message_text("❌ Terjadi kesalahan. Silakan coba lagi atau hubungi admin.")
        return S_START


async def show_calendar(update: Update, context: ContextTypes.DEFAULT_TYPE, year: int = None, month: int = None):
    """
    Show interactive calendar for date selection.
    Reused by gender callback and calendar navigation.
    """
    query = update.callback_query
    
    if year is None or month is None:
        today = date.today()
        year = today.year
        month = today.month
    
    context.user_data['cal_year'] = year
    context.user_data['cal_month'] = month
    
    today = date.today()
    max_date = today + timedelta(days=Config.MAX_DAYS_AHEAD)
    
    available_dates = set()
    check_date = date(year, month, 1)
    import calendar
    last_day_of_month = calendar.monthrange(year, month)[1]
    
    for day in range(1, last_day_of_month + 1):
        check_date = date(year, month, day)
        
        if check_date < today or check_date > max_date:
            continue
        
        if await db.is_weekly_holiday(check_date) or await db.is_date_holiday(check_date):
            continue
        
        slots = await generate_time_slots(check_date)
        if slots:
            available_dates.add(check_date)
    
    kb, header_text = create_calendar_keyboard(year, month, available_dates, max_date)
    
    gender = context.user_data.get('patient_gender', '')
    
    msg = (
        f"📅 *PILIH TANGGAL KUNJUNGAN*\n\n"
        f"👤 Pasien: {gender}\n"
        f"Angka = Tersedia | \\[Angka] = Penuh atau Libur | (Angka) = Lewat\n\n"
        f"{header_text}"
    )
    
    kb.append([InlineKeyboardButton("🔙 Kembali", callback_data="back_to_gender"), InlineKeyboardButton("🏠 Menu Utama", callback_data="back_to_start")])
    
    await query.edit_message_text(
        msg,
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(kb)
    )
    
    return S_CHOOSE_DATE


async def calendar_noop_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle no-op calendar callbacks to avoid 'query is too old' errors"""
    query = update.callback_query
    await query.answer()
    return None


async def calendar_nav_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle calendar navigation (prev/next month)"""
    query = update.callback_query
    await query.answer()
    
    parts = query.data.split("_")
    direction = parts[1]
    year = int(parts[2])
    month = int(parts[3])
    
    if direction == "next":
        year, month = get_next_month(year, month)
    elif direction == "prev":
        year, month = get_prev_month(year, month)
    
    return await show_calendar(update, context, year, month)


async def patient_gender_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    try:
        gender = "Laki-laki" if query.data == "pat_m" else "Perempuan"
        context.user_data['patient_gender'] = gender
        
        therapists = await db.get_therapists(active_only=True)
        gender_therapists = [t for t in therapists if t['gender'] == gender]
        
        if not gender_therapists:
            kb = [
                [InlineKeyboardButton("🔙 Pilih Gender Lain", callback_data="back_to_gender")],
                [InlineKeyboardButton("⏳ Daftar Tunggu", callback_data="join_waitlist_no_therapist")],
                [InlineKeyboardButton("🏠 Menu Utama", callback_data="back_to_start")]
            ]
            
            msg = (
                f"❌ *TERAPIS TIDAK TERSEDIA*\n\n"
                f"Maaf, saat ini tidak ada terapis {gender.lower()} yang aktif.\n\n"
                f"Admin telah diberitahu tentang hal ini. Anda dapat:\n"
                f"• Pilih gender lain\n"
                f"• Bergabung dengan daftar tunggu\n"
                f"• Hubungi admin langsung"
            )
            
            await query.edit_message_text(
                msg,
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(kb)
            )
            
            from config import Config
            for admin_id in Config.ADMIN_IDS:
                try:
                    await query.bot.send_message(
                        chat_id=admin_id,
                        text=f"⚠️ *PERINGATAN*\n\nUser mencoba booking terapis {gender.lower()} tapi tidak ada yang aktif.\n\nUser: {query.from_user.username or query.from_user.first_name}",
                        parse_mode='Markdown'
                    )
                except Exception as e:
                    logger.error(f"Failed to notify admin {admin_id}: {e}")
            
            return S_PAT_GENDER
        
        return await show_calendar(update, context)
    except Exception as e:
        log_error_with_context(e, update, context, "patient_gender_callback")
        await query.edit_message_text("❌ Terjadi kesalahan. Silakan coba lagi atau hubungi admin.")
        return S_START


async def date_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    date_iso = query.data.split("_", 1)[1]
    date_obj = parse_date(date_iso)
    
    if not date_obj:
        kb = [[InlineKeyboardButton("🔙 Kembali", callback_data="back_to_choose_date"), InlineKeyboardButton("🏠 Menu Utama", callback_data="back_to_start")]]
        await query.edit_message_text(
            "Tanggal tidak valid.",
            reply_markup=InlineKeyboardMarkup(kb)
        )
        return S_CHOOSE_DATE
    
    context.user_data['requested_date'] = date_obj.isoformat()
    
    slots = await generate_time_slots(date_obj)
    if not slots:
        kb = [[InlineKeyboardButton("🔙 Kembali", callback_data="back_to_choose_date"), InlineKeyboardButton("🏠 Menu Utama", callback_data="back_to_start")]]
        await query.edit_message_text(
            f"Hari {date_iso} adalah hari libur atau tidak ada slot tersedia.",
            reply_markup=InlineKeyboardMarkup(kb)
        )
        return S_CHOOSE_DATE
    
    kb = []
    row = []
    
    for slot in slots:
        label = from_iso(slot).strftime("%H:%M")
        row.append(InlineKeyboardButton(label, callback_data=f"time_{slot}"))
        
        if len(row) >= 3:
            kb.append(row)
            row = []
    
    if row:
        kb.append(row)
    
    kb.append([InlineKeyboardButton("👨‍⚕️ Lihat Terapis", callback_data="view_therapists_for_date")])
    kb.append([InlineKeyboardButton("🔍 Lihat Semua Terapis", callback_data="show_any")])
    kb.append([InlineKeyboardButton("⏳ Daftar Tunggu", callback_data="join_waitlist")])
    kb.append([InlineKeyboardButton("🔙 Kembali", callback_data="back_to_choose_date"), InlineKeyboardButton("🏠 Menu Utama", callback_data="back_to_start")])
    
    date_formatted = format_date_id(date_obj, include_year=True)
    gender = context.user_data.get('patient_gender', '')
    
    msg = (
        f"⏰ *PILIH WAKTU*\n\n"
        f"📅 Tanggal: {date_formatted}\n"
        f"👤 Pasien: {gender}\n\n"
        f"Pilih waktu yang tersedia:"
    )
    
    await query.edit_message_text(
        msg,
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(kb)
    )
    
    return S_CHOOSE_TIME


async def view_therapists_for_date_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    date_iso = context.user_data.get('requested_date')
    gender = context.user_data.get('patient_gender')
    
    if not date_iso or not gender:
        kb = [[InlineKeyboardButton("🔙 Kembali", callback_data="back_to_start")]]
        await query.edit_message_text(
            "❌ Data tidak ditemukan.",
            reply_markup=InlineKeyboardMarkup(kb)
        )
        return S_START
    
    date_obj = parse_date(date_iso)
    therapists = await db.get_therapists(active_only=True)
    
    gender_therapists = [t for t in therapists if t['gender'] == gender]
    
    if not gender_therapists:
        kb = [[InlineKeyboardButton("🔙 Kembali", callback_data="back_to_choose_date")]]
        date_formatted = format_date_id(date_obj, include_year=True)
        await query.edit_message_text(
            f"❌ Tidak ada terapis {gender.lower()} yang aktif saat ini.\n\n"
            f"Silakan hubungi admin atau pilih tanggal lain.",
            reply_markup=InlineKeyboardMarkup(kb)
        )
        return S_CHOOSE_DATE
    
    slots = await generate_time_slots(date_obj)
    
    therapist_availability = {}
    for t in gender_therapists:
        free_slots = []
        for slot in slots:
            is_free = await db.therapist_free(t['id'], slot, Config.SESSION_MINUTES)
            if is_free:
                free_slots.append(slot)
        
        therapist_availability[t['id']] = {
            'name': t['name'],
            'gender': t['gender'],
            'free_slots': free_slots,
            'earliest': free_slots[0] if free_slots else None
        }
    
    date_formatted = format_date_id(date_obj, include_year=True)
    
    msg = (
        f"👨‍⚕️ *DAFTAR TERAPIS*\n\n"
        f"📅 Tanggal: {date_formatted}\n"
        f"👤 Jenis kelamin: {gender}\n\n"
    )
    
    has_availability = False
    for tid, info in therapist_availability.items():
        gender_icon = "👨" if info['gender'] == "Laki-laki" else "👩"
        
        if info['earliest']:
            has_availability = True
            earliest_time = from_iso(info['earliest']).strftime("%H:%M")
            msg += f"{gender_icon} *{info['name']}*\n"
            msg += f"   └ Tersedia dari: {earliest_time} ({len(info['free_slots'])} slot)\n\n"
        else:
            msg += f"{gender_icon} *{info['name']}*\n"
            msg += f"   └ ❌ Penuh\n\n"
    
    if has_availability:
        msg += f"_Silakan pilih waktu untuk melihat terapis yang tersedia._"
    else:
        msg += f"_Semua terapis penuh pada tanggal ini._"
    
    kb = [
        [InlineKeyboardButton("🔙 Kembali Pilih Waktu", callback_data="back_to_choose_time")],
        [InlineKeyboardButton("🏠 Menu Utama", callback_data="back_to_start")]
    ]
    
    await query.edit_message_text(
        msg,
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(kb)
    )
    
    return S_CHOOSE_TIME


async def time_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if not query.data.startswith("time_"):
        kb = [[InlineKeyboardButton("🏠 Kembali ke Menu Utama", callback_data="back_to_start")]]
        await query.edit_message_text(
            "Pilihan tidak valid.",
            reply_markup=InlineKeyboardMarkup(kb)
        )
        return S_START
    
    slot_iso = query.data.split("_", 1)[1]
    context.user_data['requested_start'] = slot_iso
    
    gender = context.user_data.get('patient_gender')
    therapists = await db.get_therapists(active_only=True)
    
    available = []
    for therapist in therapists:
        if therapist['gender'] == gender:
            is_free = await db.therapist_free(therapist['id'], slot_iso, Config.SESSION_MINUTES)
            if is_free:
                available.append(therapist)
    
    if not available:
        kb = [
            [InlineKeyboardButton("🔍 Tampilkan semua terapis", callback_data="show_any")],
            [InlineKeyboardButton("⏳ Gabung daftar tunggu", callback_data="join_waitlist")],
            [InlineKeyboardButton("🔙 Pilih waktu lain", callback_data="pick_other_time")],
            [InlineKeyboardButton("🏠 Kembali ke Menu Utama", callback_data="back_to_start")]
        ]
        
        await query.edit_message_text(
            f"Maaf, tidak ada terapis {gender.lower()} kosong pada {format_datetime_short(slot_iso)}.",
            reply_markup=InlineKeyboardMarkup(kb)
        )
        return S_CHOOSE_TIME
    
    kb = [[InlineKeyboardButton(f"✅ {t['name']}", callback_data=f"ther_{t['id']}")] for t in available]
    kb.append([InlineKeyboardButton("🔙 Kembali", callback_data="back_to_choose_time"), InlineKeyboardButton("🏠 Menu Utama", callback_data="back_to_start")])
    
    msg = (
        f"👨‍⚕️ *PILIH TERAPIS*\n\n"
        f"🕒 Waktu: {format_datetime_short(slot_iso)}\n"
        f"👤 Jenis kelamin: {gender}\n\n"
        f"Terapis yang tersedia:"
    )
    
    await query.edit_message_text(
        msg,
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(kb)
    )
    
    return S_CHOOSE_THER


async def show_any_or_waitlist_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "pick_other_time":
        return await show_calendar(update, context)
    
    if query.data == "join_waitlist" or query.data == "join_waitlist_no_therapist":
        kb = [
            [InlineKeyboardButton("🔙 Kembali", callback_data="back_to_choose_time")],
            [InlineKeyboardButton("🏠 Menu Utama", callback_data="back_to_start")]
        ]
        
        await query.edit_message_text(
            "📝 *DAFTAR TUNGGU*\n\n"
            "Untuk mendaftar ke daftar tunggu, kami memerlukan informasi kontak Anda.\n\n"
            "Silakan ketik *nama lengkap* Anda:",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(kb)
        )
        return S_WAITLIST_NAME
    
    if query.data == "show_any":
        slot_iso = context.user_data.get('requested_start')
        
        if not slot_iso:
            return await view_therapists_for_date_callback(update, context)
        
        gender = context.user_data.get('patient_gender', '')
        therapists = await db.get_therapists(active_only=True)
        available = []
        
        for therapist in therapists:
            if therapist['gender'] == gender:
                is_free = await db.therapist_free(therapist['id'], slot_iso, Config.SESSION_MINUTES)
                if is_free:
                    available.append(therapist)
        
        if not available:
            kb = [[InlineKeyboardButton("🏠 Kembali ke Menu Utama", callback_data="back_to_start")]]
            await query.edit_message_text(
                f"Tidak ada terapis {gender.lower()} yang tersedia pada {format_datetime_id(slot_iso)}.",
                reply_markup=InlineKeyboardMarkup(kb)
            )
            return S_START
        
        kb = [[InlineKeyboardButton(f"✅ {t['name']}", callback_data=f"ther_{t['id']}")] 
              for t in available]
        kb.append([InlineKeyboardButton("🔙 Kembali", callback_data="back_to_choose_time"), InlineKeyboardButton("🏠 Menu Utama", callback_data="back_to_start")])
        
        await query.edit_message_text(
            f"👨‍⚕️ *SEMUA TERAPIS {gender.upper()}*\n\n"
            f"🕒 Waktu: {format_datetime_short(slot_iso)}\n\n"
            f"Terapis yang tersedia:",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(kb)
        )
        return S_CHOOSE_THER
    
    return S_START


async def therapist_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    therapist_id = int(query.data.split("_")[1])
    context.user_data['therapist_id'] = therapist_id
    
    therapist = await db.get_therapist(therapist_id)
    if not therapist:
        kb = [[InlineKeyboardButton("🏠 Kembali ke Menu Utama", callback_data="back_to_start")]]
        await query.edit_message_text(
            "Terapis tidak ditemukan.",
            reply_markup=InlineKeyboardMarkup(kb)
        )
        return S_START
    
    context.user_data['therapist_name'] = therapist['name']
    
    time_str = format_datetime_short(context.user_data.get('requested_start', ''))
    
    kb = [
        [InlineKeyboardButton("🔙 Kembali", callback_data="back_to_choose_therapist")],
        [InlineKeyboardButton("🏠 Menu Utama", callback_data="back_to_start")]
    ]
    
    msg = (
        f"✏️ *MASUKKAN NAMA PASIEN*\n\n"
        f"Terapis: {therapist['name']}\n"
        f"Waktu: {time_str}\n\n"
        f"Silakan ketik nama lengkap pasien:\n\n"
        f"_Atau klik tombol di bawah untuk kembali_"
    )
    
    await query.edit_message_text(msg, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(kb))
    
    return S_ASK_NAME


async def patient_name_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    
    valid, error_msg = is_valid_patient_name(name)
    if not valid:
        await update.message.reply_text(f"❌ {error_msg}\n\nSilakan masukkan nama yang valid atau ketik /cancel untuk membatalkan:")
        return S_ASK_NAME
    
    context.user_data['patient_name'] = name
    
    time_str = format_datetime_short(context.user_data.get('requested_start', ''))
    therapist_name = context.user_data.get('therapist_name', '?')
    
    kb = [
        [InlineKeyboardButton("🔙 Kembali", callback_data="back_to_name")],
        [InlineKeyboardButton("🏠 Menu Utama", callback_data="back_to_start")]
    ]
    
    msg = (
        f"📍 *MASUKKAN ALAMAT PASIEN*\n\n"
        f"Nama: {name}\n"
        f"Terapis: {therapist_name}\n"
        f"Waktu: {time_str}\n\n"
        f"Silakan ketik alamat lengkap pasien:\n\n"
        f"_Atau klik tombol di bawah untuk kembali_"
    )
    
    await update.message.reply_text(msg, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(kb))
    
    return S_ASK_ADDRESS


async def patient_address_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    address = update.message.text.strip()
    
    valid, error_msg = is_valid_address(address)
    if not valid:
        await update.message.reply_text(f"❌ {error_msg}\n\nSilakan masukkan alamat yang valid atau ketik /cancel untuk membatalkan:")
        return S_ASK_ADDRESS
    
    context.user_data['patient_address'] = address
    
    name = context.user_data.get('patient_name', '?')
    gender = context.user_data.get('patient_gender', '?')
    time_iso = context.user_data.get('requested_start', '?')
    therapist_name = context.user_data.get('therapist_name', '?')
    
    datetime_str = format_datetime_id(time_iso)
    
    msg = format_confirmation_message(
        name, gender, therapist_name, datetime_str, Config.SESSION_MINUTES, address
    )
    
    kb = [
        [InlineKeyboardButton("✅ Ya, Konfirmasi Booking", callback_data="confirm_yes")],
        [InlineKeyboardButton("✏️ Edit Data", callback_data="back_to_address")],
        [InlineKeyboardButton("❌ Batalkan", callback_data="confirm_no"), InlineKeyboardButton("🏠 Menu Utama", callback_data="back_to_start")]
    ]
    
    await update.message.reply_text(
        msg,
        parse_mode='MarkdownV2',
        reply_markup=InlineKeyboardMarkup(kb)
    )
    
    return S_CONFIRM




async def confirmation_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    try:
        if query.data == "confirm_no":
            kb = [
                [InlineKeyboardButton("🩺 Buat Janji Baru", callback_data="make")],
                [InlineKeyboardButton("🏠 Kembali ke Menu Utama", callback_data="back_to_start")]
            ]
            await query.edit_message_text(
                "❌ Janji dibatalkan.",
                reply_markup=InlineKeyboardMarkup(kb)
            )
            return S_START
        
        user_id = update.effective_user.id
        patient_name = context.user_data.get('patient_name', 'Unknown')
        patient_gender = context.user_data.get('patient_gender', 'Unknown')
        patient_address = context.user_data.get('patient_address', '')
        therapist_id = context.user_data.get('therapist_id')
        therapist_name = context.user_data.get('therapist_name', '?')
        start_iso = context.user_data.get('requested_start')
        
        try:
            appt_id = await db.add_appointment(
                user_id, patient_name, patient_gender,
                therapist_id, start_iso, Config.SESSION_MINUTES, patient_address
            )
            
            schedule_reminder = context.application.bot_data.get('schedule_reminder')
            if schedule_reminder:
                job_id = schedule_reminder(
                    context.application, appt_id, user_id, patient_name, 
                    therapist_name, start_iso
                )
                if job_id:
                    await db.update_appointment(appt_id, reminder_job_id=job_id)
            
            datetime_str = format_datetime_id(start_iso)
            success_msg = format_success_message(
                patient_name, therapist_name, datetime_str, Config.SESSION_MINUTES, patient_address
            )
            
            kb = [
                [InlineKeyboardButton("📋 Lihat Janji Saya", callback_data="my_appointments")],
                [InlineKeyboardButton("🩺 Buat Janji Baru", callback_data="make"), InlineKeyboardButton("🏠 Menu Utama", callback_data="back_to_start")]
            ]
            
            await query.edit_message_text(
                success_msg,
                parse_mode='MarkdownV2',
                reply_markup=InlineKeyboardMarkup(kb)
            )
            
            logger.info(f"Booking created - User: {user_id} (@{update.effective_user.username}), Patient: {patient_name}, Therapist: {therapist_name}, Time: {start_iso}")
            
        except Exception as e:
            log_error_with_context(e, update, context, "confirmation_callback - database operation")
            kb = [[InlineKeyboardButton("🏠 Kembali ke Menu Utama", callback_data="back_to_start")]]
            await query.edit_message_text(
                "❌ Terjadi kesalahan saat membuat janji. Silakan coba lagi atau hubungi admin.",
                reply_markup=InlineKeyboardMarkup(kb)
            )
        
        return S_START
    except Exception as e:
        log_error_with_context(e, update, context, "confirmation_callback")
        await query.edit_message_text("❌ Terjadi kesalahan. Silakan coba lagi atau hubungi admin.")
        return S_START


async def my_appointments_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    appointments = await db.get_user_appointments(user_id, limit=20)
    
    if not appointments:
        kb = [
            [InlineKeyboardButton("🩺 Buat Janji Baru", callback_data="make")],
            [InlineKeyboardButton("🏠 Menu Utama", callback_data="back_to_start")]
        ]
        
        msg = (
            "📋 *JANJI SAYA*\n"
            "━━━━━━━━━━━━━━━━━\n\n"
            "Anda belum memiliki janji.\n\n"
            "Silakan buat janji baru untuk booking terapi bekam."
        )
        
        await query.edit_message_text(
            msg,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(kb)
        )
        return S_START
    
    from utils.datetime_helper import now_jakarta
    now = now_jakarta()
    upcoming = [a for a in appointments if a['status'] == 'confirmed' and from_iso(a['start_dt']) > now]
    past = [a for a in appointments if a not in upcoming]
    
    msg = "📋 *JANJI SAYA*\n" + "━" * 17 + "\n\n"
    
    if upcoming:
        msg += "🔜 *Janji Mendatang:*\n\n"
        for appt in upcoming[:5]:
            datetime_str = format_datetime_short(appt['start_dt'])
            status_icon = "✅"
            msg += f"{status_icon} {datetime_str}\n"
            msg += f"   👨‍⚕️ {appt['therapist_name']}\n"
            msg += f"   👤 {appt['user_name']}\n\n"
    
    if past:
        msg += "📅 *Riwayat Janji:*\n\n"
        for appt in past[:5]:
            datetime_str = format_datetime_short(appt['start_dt'])
            status_icon = "✅" if appt['status'] == 'confirmed' else "✔️" if appt['status'] == 'completed' else "❌"
            msg += f"{status_icon} {datetime_str} - {appt['therapist_name']}\n"
    
    if len(appointments) > 10:
        msg += f"\n_...dan {len(appointments) - 10} janji lainnya_"
    
    kb = []
    
    for appt in upcoming[:3]:
        datetime_str = format_datetime_short(appt['start_dt'])
        kb.append([InlineKeyboardButton(f"📝 {datetime_str} - {appt['therapist_name']}", callback_data=f"view_my_appt_{appt['id']}")])
    
    kb.append([InlineKeyboardButton("🩺 Buat Janji Baru", callback_data="make")])
    kb.append([InlineKeyboardButton("🏠 Menu Utama", callback_data="back_to_start")])
    
    await query.edit_message_text(
        msg,
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(kb)
    )
    
    return S_START


async def view_my_appointment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    appointment_id = int(query.data.split("_")[-1])
    appt = await db.get_appointment_by_id(appointment_id)
    
    if not appt or appt['user_id'] != update.effective_user.id:
        kb = [[InlineKeyboardButton("🏠 Menu Utama", callback_data="back_to_start")]]
        await query.edit_message_text(
            "❌ Janji tidak ditemukan atau Anda tidak memiliki akses.",
            reply_markup=InlineKeyboardMarkup(kb)
        )
        return S_START
    
    datetime_str = format_datetime_id(appt['start_dt'])
    status_emoji = "✅" if appt['status'] == 'confirmed' else "✔️" if appt['status'] == 'completed' else "❌"
    
    msg = (
        "📋 *DETAIL JANJI*\n"
        + "━" * 17 + "\n\n"
        f"👤 *Nama:* {appt['user_name']}\n"
        f"⚧ *Jenis Kelamin:* {appt['patient_gender']}\n"
        f"📍 *Alamat:* {appt['patient_address']}\n"
        f"👨‍⚕️ *Terapis:* {appt['therapist_name']}\n"
        f"🕒 *Waktu:* {datetime_str}\n"
        f"⏱ *Durasi:* {appt['duration_min']} menit\n"
        f"📊 *Status:* {status_emoji} {appt['status']}"
    )
    
    kb = []
    
    if appt['status'] == 'confirmed':
        kb.append([InlineKeyboardButton("❌ Batalkan Janji", callback_data=f"cancel_my_appt_{appt['id']}")])
    
    kb.append([InlineKeyboardButton("🔙 Lihat Semua Janji", callback_data="my_appointments")])
    kb.append([InlineKeyboardButton("🏠 Menu Utama", callback_data="back_to_start")])
    
    await query.edit_message_text(
        msg,
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(kb)
    )
    
    return S_START


async def cancel_my_appointment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    appointment_id = int(query.data.split("_")[-1])
    
    try:
        appt = await db.get_appointment_by_id(appointment_id)
        
        if not appt or appt['user_id'] != update.effective_user.id:
            logger.warning(f"Cancel attempt - appointment {appointment_id} not found or unauthorized by user {update.effective_user.id}")
            kb = [
                [InlineKeyboardButton("📋 Lihat Janji Saya", callback_data="my_appointments")],
                [InlineKeyboardButton("🏠 Menu Utama", callback_data="back_to_start")]
            ]
            await query.edit_message_text(
                "❌ Janji tidak ditemukan atau Anda tidak memiliki akses.",
                reply_markup=InlineKeyboardMarkup(kb)
            )
            return S_START
        
        logger.info(f"User {update.effective_user.id} initiating cancel for appointment {appointment_id}")
        
        cancelled_appt = await db.cancel_appointment(appointment_id)
        
        if not cancelled_appt:
            logger.warning(f"Appointment {appointment_id} was already cancelled or not found")
            kb = [
                [InlineKeyboardButton("📋 Lihat Janji Saya", callback_data="my_appointments")],
                [InlineKeyboardButton("🏠 Menu Utama", callback_data="back_to_start")]
            ]
            await query.edit_message_text(
                "❌ Janji ini sudah dibatalkan sebelumnya.",
                reply_markup=InlineKeyboardMarkup(kb)
            )
            return S_START
        
        try:
            if context.application and context.application.bot_data:
                cancel_reminder = context.application.bot_data.get('cancel_reminder')
                if cancel_reminder and appt.get('reminder_job_id'):
                    cancel_reminder(appt['reminder_job_id'])
                    logger.info(f"Cancelled reminder job {appt['reminder_job_id']} for appointment {appointment_id}")
                else:
                    logger.debug(f"No reminder job to cancel for appointment {appointment_id}")
            else:
                logger.warning("context.application or bot_data not available for reminder cancellation")
        except Exception as e:
            logger.error(f"Non-critical error cancelling reminder for appointment {appointment_id}: {e}")
        
        kb = [
            [InlineKeyboardButton("📋 Lihat Janji Saya", callback_data="my_appointments")],
            [InlineKeyboardButton("🩺 Buat Janji Baru", callback_data="make"), InlineKeyboardButton("🏠 Menu Utama", callback_data="back_to_start")]
        ]
        
        await query.edit_message_text(
            "✅ *Janji Berhasil Dibatalkan*\n\n"
            "Janji Anda telah dibatalkan. Terima kasih.",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(kb)
        )
        
        logger.info(f"Appointment {appointment_id} successfully cancelled by user {update.effective_user.id}")
        
        try:
            from utils.waitlist_notify import notify_waitlist_for_slot
            
            if context.application:
                await notify_waitlist_for_slot(context.application, cancelled_appt)
                logger.info(f"Waitlist notification triggered for cancelled appointment {appointment_id}")
            else:
                logger.warning("context.application not available for waitlist notification")
        except Exception as e:
            logger.error(f"Non-critical error notifying waitlist for appointment {appointment_id}: {e}")
        
    except Exception as e:
        logger.error(f"Critical error cancelling appointment {appointment_id}: {e}", exc_info=True)
        kb = [
            [InlineKeyboardButton("🔄 Coba Lagi", callback_data=f"cancel_my_appt_{appointment_id}")],
            [InlineKeyboardButton("🔙 Kembali ke Detail", callback_data=f"view_my_appt_{appointment_id}"), InlineKeyboardButton("📋 Lihat Semua Janji", callback_data="my_appointments")],
            [InlineKeyboardButton("🏠 Menu Utama", callback_data="back_to_start")]
        ]
        await query.edit_message_text(
            "❌ Terjadi kesalahan saat membatalkan janji. Silakan coba lagi atau hubungi admin.",
            reply_markup=InlineKeyboardMarkup(kb)
        )
    
    return S_START


async def back_to_gender_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle back to gender selection - re-render gender picker"""
    query = update.callback_query
    await query.answer()
    
    kb = [
        [InlineKeyboardButton("👨 Laki-laki", callback_data="pat_m")],
        [InlineKeyboardButton("👩 Perempuan", callback_data="pat_f")],
        [InlineKeyboardButton("🏠 Kembali ke Menu Utama", callback_data="back_to_start")]
    ]
    
    msg = (
        "👤 *JENIS KELAMIN PASIEN*\n\n"
        "Silakan pilih jenis kelamin pasien untuk mencocokkan dengan terapis yang sesuai:"
    )
    
    await query.edit_message_text(
        msg,
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(kb)
    )
    
    return S_PAT_GENDER


async def back_to_choose_date_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle back to date selection - re-render calendar with preserved gender"""
    return await show_calendar(update, context)


async def back_to_choose_time_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle back to time selection - re-render time picker with preserved date"""
    query = update.callback_query
    await query.answer()
    
    date_iso = context.user_data.get('requested_date')
    if not date_iso:
        await query.edit_message_text("Error: Tanggal tidak ditemukan.")
        return S_START
    
    date_obj = parse_date(date_iso)
    gender = context.user_data.get('patient_gender', '')
    
    slots = await generate_time_slots(date_obj)
    kb = []
    row = []
    
    for slot in slots:
        label = from_iso(slot).strftime("%H:%M")
        row.append(InlineKeyboardButton(label, callback_data=f"time_{slot}"))
        
        if len(row) >= 3:
            kb.append(row)
            row = []
    
    if row:
        kb.append(row)
    
    kb.append([InlineKeyboardButton("🔍 Lihat Semua Terapis", callback_data="show_any")])
    kb.append([InlineKeyboardButton("⏳ Daftar Tunggu", callback_data="join_waitlist")])
    kb.append([InlineKeyboardButton("🔙 Kembali", callback_data="back_to_choose_date"), InlineKeyboardButton("🏠 Menu Utama", callback_data="back_to_start")])
    
    date_formatted = format_date_id(date_obj, include_year=True)
    
    msg = (
        f"⏰ *PILIH WAKTU*\n\n"
        f"📅 Tanggal: {date_formatted}\n"
        f"👤 Pasien: {gender}\n\n"
        f"Pilih waktu yang tersedia:"
    )
    
    await query.edit_message_text(
        msg,
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(kb)
    )
    
    return S_CHOOSE_TIME


async def back_to_choose_therapist_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle back to therapist selection - re-render therapist picker"""
    query = update.callback_query
    await query.answer()
    
    slot_iso = context.user_data.get('requested_start')
    gender = context.user_data.get('patient_gender')
    
    if not slot_iso:
        await query.edit_message_text("Error: Waktu tidak ditemukan.")
        return S_START
    
    therapists = await db.get_therapists(active_only=True)
    
    available = []
    for therapist in therapists:
        if therapist['gender'] == gender:
            is_free = await db.therapist_free(therapist['id'], slot_iso, Config.SESSION_MINUTES)
            if is_free:
                available.append(therapist)
    
    if not available:
        kb = [
            [InlineKeyboardButton("🔙 Kembali", callback_data="back_to_choose_time")],
            [InlineKeyboardButton("🏠 Menu Utama", callback_data="back_to_start")]
        ]
        await query.edit_message_text(
            f"Maaf, tidak ada terapis {gender.lower()} tersedia.",
            reply_markup=InlineKeyboardMarkup(kb)
        )
        return S_CHOOSE_TIME
    
    kb = [[InlineKeyboardButton(f"✅ {t['name']}", callback_data=f"ther_{t['id']}")] for t in available]
    kb.append([InlineKeyboardButton("🔙 Kembali", callback_data="back_to_choose_time"), InlineKeyboardButton("🏠 Menu Utama", callback_data="back_to_start")])
    
    msg = (
        f"👨‍⚕️ *PILIH TERAPIS*\n\n"
        f"🕒 Waktu: {format_datetime_short(slot_iso)}\n"
        f"👤 Jenis kelamin: {gender}\n\n"
        f"Terapis yang tersedia:"
    )
    
    await query.edit_message_text(
        msg,
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(kb)
    )
    
    return S_CHOOSE_THER


async def back_to_name_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle back to name input - re-prompt for patient name"""
    query = update.callback_query
    await query.answer()
    
    therapist_name = context.user_data.get('therapist_name', '?')
    time_str = format_datetime_short(context.user_data.get('requested_start', ''))
    
    kb = [
        [InlineKeyboardButton("🔙 Kembali", callback_data="back_to_choose_therapist")],
        [InlineKeyboardButton("🏠 Menu Utama", callback_data="back_to_start")]
    ]
    
    msg = (
        f"✏️ *MASUKKAN NAMA PASIEN*\n\n"
        f"Terapis: {therapist_name}\n"
        f"Waktu: {time_str}\n\n"
        f"Silakan ketik nama lengkap pasien:\n\n"
        f"_Atau klik tombol di bawah untuk kembali_"
    )
    
    await query.edit_message_text(msg, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(kb))
    
    return S_ASK_NAME


async def back_to_address_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle back to address input - re-prompt for patient address"""
    query = update.callback_query
    await query.answer()
    
    name = context.user_data.get('patient_name', '?')
    therapist_name = context.user_data.get('therapist_name', '?')
    time_str = format_datetime_short(context.user_data.get('requested_start', ''))
    
    kb = [
        [InlineKeyboardButton("🔙 Kembali", callback_data="back_to_name")],
        [InlineKeyboardButton("🏠 Menu Utama", callback_data="back_to_start")]
    ]
    
    msg = (
        f"📍 *MASUKKAN ALAMAT PASIEN*\n\n"
        f"Nama: {name}\n"
        f"Terapis: {therapist_name}\n"
        f"Waktu: {time_str}\n\n"
        f"Silakan ketik alamat lengkap pasien:\n\n"
        f"_Atau klik tombol di bawah untuk kembali_"
    )
    
    await query.edit_message_text(msg, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(kb))
    
    return S_ASK_ADDRESS


async def waitlist_name_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle waitlist name input"""
    name = update.message.text.strip()
    
    is_valid, error_msg = is_valid_patient_name(name)
    if not is_valid:
        await update.message.reply_text(
            f"❌ {error_msg}\n\n"
            f"Silakan ketik nama lengkap Anda:"
        )
        return S_WAITLIST_NAME
    
    context.user_data['waitlist_name'] = name
    
    kb = [
        [InlineKeyboardButton("🔙 Kembali", callback_data="back_to_choose_time")],
        [InlineKeyboardButton("🏠 Menu Utama", callback_data="back_to_start")]
    ]
    
    await update.message.reply_text(
        f"✅ Nama: {name}\n\n"
        f"Sekarang, silakan ketik *nomor telepon* yang bisa dihubungi:\n\n"
        f"_Format: 08xxxxxxxxxx atau +62xxxxxxxxxx_",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(kb)
    )
    
    return S_WAITLIST_PHONE


async def waitlist_phone_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle waitlist phone input"""
    phone = update.message.text.strip()
    
    is_valid, error_msg = is_valid_phone(phone)
    if not is_valid:
        await update.message.reply_text(
            f"❌ {error_msg}\n\n"
            f"Silakan ketik nomor telepon yang valid:\n"
            f"_Format: 08xxxxxxxxxx atau +62xxxxxxxxxx_",
            parse_mode='Markdown'
        )
        return S_WAITLIST_PHONE
    
    context.user_data['waitlist_phone'] = phone
    
    name = context.user_data.get('waitlist_name', '')
    date_iso = context.user_data.get('requested_date', '')
    gender = context.user_data.get('patient_gender', 'Tidak diketahui')
    
    kb = [
        [InlineKeyboardButton("✅ Konfirmasi & Daftar", callback_data="waitlist_confirm")],
        [InlineKeyboardButton("❌ Batal", callback_data="back_to_start")]
    ]
    
    date_formatted = format_date_id(parse_date(date_iso), include_year=True) if date_iso else 'Tidak ditentukan'
    
    await update.message.reply_text(
        f"📝 *KONFIRMASI DATA DAFTAR TUNGGU*\n\n"
        f"👤 Nama: {name}\n"
        f"📱 Telepon: {phone}\n"
        f"👥 Jenis kelamin: {gender}\n"
        f"📅 Tanggal: {date_formatted}\n\n"
        f"Apakah data sudah benar?",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(kb)
    )
    
    return S_WAITLIST_PHONE


async def waitlist_confirm_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle waitlist confirmation and save to database"""
    query = update.callback_query
    await query.answer()
    
    name = context.user_data.get('waitlist_name', '')
    phone = context.user_data.get('waitlist_phone', '')
    gender = context.user_data.get('patient_gender', 'Tidak diketahui')
    date_iso = context.user_data.get('requested_date')
    chat_id = update.effective_chat.id
    
    await db.add_to_waitlist(chat_id, name, gender, phone, date_iso)
    
    context.user_data.pop('waitlist_name', None)
    context.user_data.pop('waitlist_phone', None)
    
    kb = [
        [InlineKeyboardButton("🩺 Buat Janji Baru", callback_data="make")],
        [InlineKeyboardButton("🏠 Kembali ke Menu Utama", callback_data="back_to_start")]
    ]
    
    date_formatted = format_date_id(parse_date(date_iso), include_year=True) if date_iso else 'Tidak ditentukan'
    
    await query.edit_message_text(
        f"✅ *BERHASIL MENDAFTAR*\n\n"
        f"Anda telah ditambahkan ke daftar tunggu.\n\n"
        f"👤 Nama: {name}\n"
        f"📱 Telepon: {phone}\n"
        f"📅 Tanggal: {date_formatted}\n"
        f"👥 Jenis kelamin: {gender}\n\n"
        f"Admin akan menghubungi Anda jika ada slot tersedia.",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(kb)
    )
    
    return S_START
