import logging
import io
import csv
from datetime import date
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from database.db import db
from config import Config
from utils.datetime_helper import format_datetime_id, format_date_id, parse_date, WEEKDAY_NAMES_ID
from utils.validators import is_valid_therapist_name

logger = logging.getLogger(__name__)

(A_MENU, A_ADD_TH_NAME, A_ADD_TH_GENDER, A_DELETE_TH_SELECT,
 A_DELETE_APPT, A_HOLIDAY_MENU, A_ADD_HOL_DATE, A_ADD_HOL_WEEKLY,
 A_DEL_HOL_DATE_SELECT, A_DEL_HOL_WEEKLY_SELECT, A_VIEW_APPT, A_MANAGE_APPT,
 A_EDIT_APPT_FIELD, A_EDIT_APPT_VALUE, A_WAITLIST_MANAGE,
 A_TH_DETAIL, A_EDIT_TH_NAME, A_EDIT_TH_GENDER, A_SCHEDULE_INACTIVE,
 A_INACTIVE_CUSTOM_DAYS, A_BROADCAST_COMPOSE, A_BROADCAST_CONFIRM) = range(10, 32)


async def is_admin(user_id: int) -> bool:
    return user_id in Config.ADMIN_IDS


async def admin_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if not await is_admin(update.effective_user.id):
        await query.edit_message_text("❌ Anda tidak memiliki akses admin.")
        return ConversationHandler.END
    
    from utils.datetime_helper import now_jakarta, from_iso
    now = now_jakarta()
    
    appointments = await db.get_appointments(status='confirmed')
    upcoming_count = sum(1 for a in appointments if from_iso(a['start_dt']) > now)
    
    waitlist_entries = await db.get_waitlist()
    waitlist_count = len(list(waitlist_entries))
    
    appt_badge = f" ({upcoming_count})" if upcoming_count > 0 else ""
    waitlist_badge = f" ({waitlist_count})" if waitlist_count > 0 else ""
    
    kb = [
        [InlineKeyboardButton("👨‍⚕️ Kelola Terapis", callback_data="admin_therapists")],
        [InlineKeyboardButton(f"📅 Kelola Janji{appt_badge}", callback_data="admin_appointments")],
        [InlineKeyboardButton(f"⏳ Daftar Tunggu{waitlist_badge}", callback_data="admin_waitlist")],
        [InlineKeyboardButton("🏖 Kelola Hari Libur", callback_data="admin_holidays")],
        [InlineKeyboardButton("📊 Export Data", callback_data="admin_export")],
        [InlineKeyboardButton("🔙 Kembali", callback_data="back_to_start")]
    ]
    
    msg = "⚙️ *PANEL ADMIN*\n\nSilakan pilih menu:"
    
    await query.edit_message_text(msg, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(kb))
    
    return A_MENU


async def admin_therapists_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    therapists = await db.get_therapists(active_only=False)
    
    msg = "👨‍⚕️ *KELOLA TERAPIS*\n\n"
    
    kb = []
    for t in therapists:
        status_icon = "✅" if t['active'] else "❌"
        gender_icon = "👨" if t['gender'] == "Laki-laki" else "👩"
        
        therapist_row = [
            InlineKeyboardButton(
                f"{status_icon} {gender_icon} {t['name']}", 
                callback_data=f"th_detail_{t['id']}"
            )
        ]
        kb.append(therapist_row)
    
    if not therapists:
        msg += "_Belum ada terapis terdaftar_\n\n"
    else:
        msg += "Klik terapis untuk melihat detail dan kelola:\n\n"
    
    kb.append([InlineKeyboardButton("➕ Tambah Terapis", callback_data="add_therapist")])
    kb.append([InlineKeyboardButton("🔙 Kembali ke Admin", callback_data="admin_menu")])
    kb.append([InlineKeyboardButton("🏠 Menu Utama", callback_data="back_to_start")])
    
    await query.edit_message_text(msg, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(kb))
    
    return A_MENU


async def add_therapist_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text("Ketik nama terapis yang ingin ditambahkan:")
    
    return A_ADD_TH_NAME


async def add_therapist_name_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    
    valid, error_msg = is_valid_therapist_name(name)
    if not valid:
        await update.message.reply_text(f"❌ {error_msg}\n\nSilakan masukkan nama yang valid:")
        return A_ADD_TH_NAME
    
    context.user_data['new_therapist_name'] = name
    
    kb = [
        [InlineKeyboardButton("👨 Laki-laki", callback_data="gender_m")],
        [InlineKeyboardButton("👩 Perempuan", callback_data="gender_f")],
        [InlineKeyboardButton("🏠 Menu Utama", callback_data="back_to_start")]
    ]
    
    await update.message.reply_text(
        f"Pilih jenis kelamin untuk terapis *{name}*:",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(kb)
    )
    
    return A_ADD_TH_GENDER


async def add_therapist_gender_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    gender = "Laki-laki" if query.data == "gender_m" else "Perempuan"
    name = context.user_data.get('new_therapist_name', 'Unknown')
    
    try:
        therapist_id = await db.add_therapist(name, gender)
        
        kb = [
            [InlineKeyboardButton("⚙️ Kembali ke Admin", callback_data="admin_menu")],
            [InlineKeyboardButton("🏠 Menu Utama", callback_data="back_to_start")]
        ]
        
        await query.edit_message_text(
            f"✅ Terapis *{name}* ({gender}) berhasil ditambahkan dengan ID {therapist_id}.",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(kb)
        )
        logger.info(f"Therapist added: {name} ({gender})")
    except Exception as e:
        logger.error(f"Error adding therapist: {e}")
        kb = [
            [InlineKeyboardButton("⚙️ Kembali ke Admin", callback_data="admin_menu")],
            [InlineKeyboardButton("🏠 Menu Utama", callback_data="back_to_start")]
        ]
        await query.edit_message_text(
            "❌ Terjadi kesalahan. Silakan coba lagi.",
            reply_markup=InlineKeyboardMarkup(kb)
        )
    
    return A_MENU


async def delete_therapist_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    therapists = await db.get_therapists(active_only=False)
    
    if not therapists:
        kb = [
            [InlineKeyboardButton("🔙 Kembali ke Admin", callback_data="admin_menu")],
            [InlineKeyboardButton("🏠 Menu Utama", callback_data="back_to_start")]
        ]
        await query.edit_message_text(
            "Tidak ada terapis untuk dihapus.",
            reply_markup=InlineKeyboardMarkup(kb)
        )
        return A_MENU
    
    kb = [[InlineKeyboardButton(f"{t['name']} ({t['gender']})", callback_data=f"delther_{t['id']}")] 
          for t in therapists]
    kb.append([InlineKeyboardButton("🔙 Kembali ke Admin", callback_data="admin_menu")])
    kb.append([InlineKeyboardButton("🏠 Menu Utama", callback_data="back_to_start")])
    
    await query.edit_message_text(
        "Pilih terapis yang ingin dihapus:",
        reply_markup=InlineKeyboardMarkup(kb)
    )
    
    return A_DELETE_TH_SELECT


async def delete_therapist_confirm_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "admin_menu":
        return await admin_menu_callback(update, context)
    
    therapist_id = int(query.data.split("_")[1])
    
    try:
        therapist = await db.get_therapist(therapist_id)
        await db.delete_therapist(therapist_id)
        
        kb = [
            [InlineKeyboardButton("⚙️ Kembali ke Admin", callback_data="admin_menu")],
            [InlineKeyboardButton("🏠 Menu Utama", callback_data="back_to_start")]
        ]
        
        await query.edit_message_text(
            f"✅ Terapis {therapist['name']} berhasil dihapus.",
            reply_markup=InlineKeyboardMarkup(kb)
        )
        logger.info(f"Therapist deleted: {therapist['name']}")
    except Exception as e:
        logger.error(f"Error deleting therapist: {e}")
        kb = [
            [InlineKeyboardButton("⚙️ Kembali ke Admin", callback_data="admin_menu")],
            [InlineKeyboardButton("🏠 Menu Utama", callback_data="back_to_start")]
        ]
        await query.edit_message_text(
            "❌ Terjadi kesalahan. Silakan coba lagi.",
            reply_markup=InlineKeyboardMarkup(kb)
        )
    
    return A_MENU


async def therapist_detail_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    therapist_id = int(query.data.split("_")[2])
    therapist = await db.get_therapist(therapist_id)
    
    if not therapist:
        kb = [[InlineKeyboardButton("🔙 Kembali", callback_data="admin_therapists")]]
        await query.edit_message_text(
            "❌ Terapis tidak ditemukan.",
            reply_markup=InlineKeyboardMarkup(kb)
        )
        return A_MENU
    
    status = "✅ Aktif" if therapist['active'] else "❌ Nonaktif"
    gender_icon = "👨" if therapist['gender'] == "Laki-laki" else "👩"
    
    msg = (
        f"👨‍⚕️ *DETAIL TERAPIS*\n\n"
        f"{gender_icon} *Nama:* {therapist['name']}\n"
        f"👤 *Jenis Kelamin:* {therapist['gender']}\n"
        f"📊 *Status:* {status}\n"
    )
    
    if therapist['inactive_start'] and therapist['inactive_end']:
        msg += f"\n📅 *Jadwal Nonaktif:*\n"
        msg += f"Mulai: {format_date_id(parse_date(therapist['inactive_start'][:10]), include_year=True)}\n"
        msg += f"Sampai: {format_date_id(parse_date(therapist['inactive_end'][:10]), include_year=True)}\n"
    
    toggle_text = "❌ Nonaktifkan" if therapist['active'] else "✅ Aktifkan"
    
    kb = [
        [InlineKeyboardButton("✏️ Edit Nama", callback_data=f"edit_th_name_{therapist_id}")],
        [InlineKeyboardButton("🔄 Ubah Gender", callback_data=f"edit_th_gender_{therapist_id}")],
        [InlineKeyboardButton(toggle_text, callback_data=f"toggle_th_{therapist_id}")]
    ]
    
    if therapist['inactive_start'] and therapist['inactive_end']:
        kb.append([InlineKeyboardButton("❌ Batalkan Jadwal Nonaktif", callback_data=f"cancel_inactive_{therapist_id}")])
    else:
        kb.append([InlineKeyboardButton("📅 Jadwalkan Nonaktif", callback_data=f"schedule_inactive_{therapist_id}")])
    
    kb.extend([
        [InlineKeyboardButton("🗑 Hapus Terapis", callback_data=f"delther_{therapist_id}")],
        [InlineKeyboardButton("🔙 Kembali", callback_data="admin_therapists")],
        [InlineKeyboardButton("🏠 Menu Utama", callback_data="back_to_start")]
    ])
    
    await query.edit_message_text(msg, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(kb))
    
    return A_TH_DETAIL


async def toggle_therapist_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    therapist_id = int(query.data.split("_")[2])
    
    try:
        therapist = await db.get_therapist(therapist_id)
        is_active = await db.toggle_therapist_active(therapist_id)
        
        status = "diaktifkan" if is_active else "dinonaktifkan"
        
        kb = [[InlineKeyboardButton("🔙 Kembali", callback_data=f"th_detail_{therapist_id}")]]
        
        await query.edit_message_text(
            f"✅ Terapis *{therapist['name']}* berhasil {status}.",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(kb)
        )
        
        logger.info(f"Therapist toggled: {therapist['name']} - Active: {is_active}")
    except Exception as e:
        logger.error(f"Error toggling therapist: {e}")
        kb = [[InlineKeyboardButton("🔙 Kembali", callback_data="admin_therapists")]]
        await query.edit_message_text(
            "❌ Terjadi kesalahan. Silakan coba lagi.",
            reply_markup=InlineKeyboardMarkup(kb)
        )
    
    return A_TH_DETAIL


async def edit_therapist_name_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    therapist_id = int(query.data.split("_")[3])
    context.user_data['edit_therapist_id'] = therapist_id
    
    therapist = await db.get_therapist(therapist_id)
    
    kb = [[InlineKeyboardButton("🔙 Batal", callback_data=f"th_detail_{therapist_id}")]]
    
    await query.edit_message_text(
        f"Ketik nama baru untuk terapis *{therapist['name']}*:",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(kb)
    )
    
    return A_EDIT_TH_NAME


async def edit_therapist_name_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    therapist_id = context.user_data.get('edit_therapist_id')
    
    if not therapist_id:
        await update.message.reply_text("❌ Terjadi kesalahan. Silakan coba lagi.")
        return A_MENU
    
    valid, error_msg = is_valid_therapist_name(name)
    if not valid:
        kb = [[InlineKeyboardButton("🔙 Batal", callback_data=f"th_detail_{therapist_id}")]]
        await update.message.reply_text(
            f"❌ {error_msg}\n\nSilakan masukkan nama yang valid:",
            reply_markup=InlineKeyboardMarkup(kb)
        )
        return A_EDIT_TH_NAME
    
    try:
        old_therapist = await db.get_therapist(therapist_id)
        await db.update_therapist(therapist_id, name=name)
        
        kb = [[InlineKeyboardButton("🔙 Kembali", callback_data=f"th_detail_{therapist_id}")]]
        
        await update.message.reply_text(
            f"✅ Nama terapis berhasil diubah dari *{old_therapist['name']}* menjadi *{name}*.",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(kb)
        )
        
        logger.info(f"Therapist name updated: {old_therapist['name']} -> {name}")
    except Exception as e:
        logger.error(f"Error updating therapist name: {e}")
        kb = [[InlineKeyboardButton("🔙 Kembali", callback_data="admin_therapists")]]
        await update.message.reply_text(
            "❌ Terjadi kesalahan. Silakan coba lagi.",
            reply_markup=InlineKeyboardMarkup(kb)
        )
    
    return A_TH_DETAIL


async def edit_therapist_gender_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    therapist_id = int(query.data.split("_")[3])
    context.user_data['edit_therapist_id'] = therapist_id
    
    therapist = await db.get_therapist(therapist_id)
    
    kb = [
        [InlineKeyboardButton("👨 Laki-laki", callback_data=f"set_gender_m_{therapist_id}")],
        [InlineKeyboardButton("👩 Perempuan", callback_data=f"set_gender_f_{therapist_id}")],
        [InlineKeyboardButton("🔙 Batal", callback_data=f"th_detail_{therapist_id}")]
    ]
    
    await query.edit_message_text(
        f"Pilih jenis kelamin baru untuk terapis *{therapist['name']}*:",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(kb)
    )
    
    return A_EDIT_TH_GENDER


async def set_therapist_gender_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    parts = query.data.split("_")
    gender_code = parts[2]
    therapist_id = int(parts[3])
    
    gender = "Laki-laki" if gender_code == "m" else "Perempuan"
    
    try:
        old_therapist = await db.get_therapist(therapist_id)
        await db.update_therapist(therapist_id, gender=gender)
        
        kb = [[InlineKeyboardButton("🔙 Kembali", callback_data=f"th_detail_{therapist_id}")]]
        
        await query.edit_message_text(
            f"✅ Jenis kelamin terapis *{old_therapist['name']}* berhasil diubah menjadi *{gender}*.",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(kb)
        )
        
        logger.info(f"Therapist gender updated: {old_therapist['name']} - {old_therapist['gender']} -> {gender}")
    except Exception as e:
        logger.error(f"Error updating therapist gender: {e}")
        kb = [[InlineKeyboardButton("🔙 Kembali", callback_data="admin_therapists")]]
        await query.edit_message_text(
            "❌ Terjadi kesalahan. Silakan coba lagi.",
            reply_markup=InlineKeyboardMarkup(kb)
        )
    
    return A_TH_DETAIL


async def admin_appointments_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    appointments = await db.get_upcoming_appointments()
    
    if not appointments:
        msg = "📅 *KELOLA JANJI*\n\nTidak ada janji mendatang."
    else:
        msg = "📅 *KELOLA JANJI*\n\n"
        for appt in appointments[:10]:
            datetime_str = format_datetime_id(appt['start_dt'])
            status_icon = "✅" if appt['status'] == 'confirmed' else "⏳"
            msg += f"{status_icon} {appt['user_name']} - {appt['therapist_name']} - {datetime_str}\n"
        
        if len(appointments) > 10:
            msg += f"\n_...dan {len(appointments) - 10} janji lainnya_"
    
    kb = [
        [InlineKeyboardButton("👁 Lihat & Kelola Janji", callback_data="view_appointment")],
        [InlineKeyboardButton("🗑 Hapus Janji", callback_data="delete_appointment")],
        [InlineKeyboardButton("🔙 Kembali ke Admin", callback_data="admin_menu")],
        [InlineKeyboardButton("🏠 Menu Utama", callback_data="back_to_start")]
    ]
    
    await query.edit_message_text(msg, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(kb))
    
    return A_MENU


async def delete_appointment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    appointments = await db.get_upcoming_appointments()
    
    if not appointments:
        kb = [
            [InlineKeyboardButton("🔙 Kembali ke Admin", callback_data="admin_menu")],
            [InlineKeyboardButton("🏠 Menu Utama", callback_data="back_to_start")]
        ]
        await query.edit_message_text(
            "Tidak ada janji untuk dihapus.",
            reply_markup=InlineKeyboardMarkup(kb)
        )
        return A_MENU
    
    kb = []
    for appt in appointments[:20]:
        datetime_str = format_datetime_id(appt['start_dt'])
        label = f"{appt['user_name']} - {datetime_str}"
        kb.append([InlineKeyboardButton(label, callback_data=f"delappt_{appt['id']}")])
    
    kb.append([InlineKeyboardButton("🔙 Kembali ke Admin", callback_data="admin_menu")])
    kb.append([InlineKeyboardButton("🏠 Menu Utama", callback_data="back_to_start")])
    
    await query.edit_message_text(
        "Pilih janji yang ingin dihapus:",
        reply_markup=InlineKeyboardMarkup(kb)
    )
    
    return A_DELETE_APPT


async def delete_appointment_confirm_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "admin_menu":
        return await admin_menu_callback(update, context)
    
    appointment_id = int(query.data.split("_")[1])
    
    try:
        await db.delete_appointment(appointment_id)
        
        kb = [
            [InlineKeyboardButton("⚙️ Kembali ke Admin", callback_data="admin_menu")],
            [InlineKeyboardButton("🏠 Menu Utama", callback_data="back_to_start")]
        ]
        
        await query.edit_message_text(
            f"✅ Janji berhasil dihapus.",
            reply_markup=InlineKeyboardMarkup(kb)
        )
        logger.info(f"Appointment deleted: {appointment_id}")
    except Exception as e:
        logger.error(f"Error deleting appointment: {e}")
        kb = [
            [InlineKeyboardButton("⚙️ Kembali ke Admin", callback_data="admin_menu")],
            [InlineKeyboardButton("🏠 Menu Utama", callback_data="back_to_start")]
        ]
        await query.edit_message_text(
            "❌ Terjadi kesalahan. Silakan coba lagi.",
            reply_markup=InlineKeyboardMarkup(kb)
        )
    
    return A_MENU


async def view_appointment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "view_appointment":
        context.user_data['appt_page'] = 0
    
    page = context.user_data.get('appt_page', 0)
    page_size = 20
    
    appointments = await db.get_all_appointments_for_admin(limit=page_size + 1, offset=page * page_size)
    
    if not appointments and page > 0:
        context.user_data['appt_page'] = max(0, page - 1)
        appointments = await db.get_all_appointments_for_admin(limit=page_size + 1, offset=context.user_data['appt_page'] * page_size)
        page = context.user_data['appt_page']
    
    if not appointments:
        context.user_data['appt_page'] = 0
        kb = [
            [InlineKeyboardButton("🔙 Kembali ke Admin", callback_data="admin_menu")],
            [InlineKeyboardButton("🏠 Menu Utama", callback_data="back_to_start")]
        ]
        await query.edit_message_text(
            "Tidak ada janji untuk ditampilkan.",
            reply_markup=InlineKeyboardMarkup(kb)
        )
        return A_MENU
    
    has_more = len(appointments) > page_size
    display_appointments = appointments[:page_size]
    
    msg = f"📋 *DAFTAR JANJI* (Halaman {page + 1})\n\n"
    msg += "_Menampilkan semua janji (confirmed, completed, cancelled)_\n\n"
    
    kb = []
    for appt in display_appointments:
        datetime_str = format_datetime_id(appt['start_dt'])
        status_icon = "✅" if appt['status'] == 'confirmed' else "✔" if appt['status'] == 'completed' else "❌"
        label = f"{status_icon} {appt['user_name']} - {datetime_str}"
        kb.append([InlineKeyboardButton(label, callback_data=f"mgappt_{appt['id']}")])
    
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("◀ Sebelumnya", callback_data="appt_page_prev"))
    if has_more:
        nav_buttons.append(InlineKeyboardButton("Berikutnya ▶", callback_data="appt_page_next"))
    
    if nav_buttons:
        kb.append(nav_buttons)
    
    kb.append([InlineKeyboardButton("🔙 Kembali ke Admin", callback_data="admin_menu")])
    kb.append([InlineKeyboardButton("🏠 Menu Utama", callback_data="back_to_start")])
    
    if has_more:
        msg += f"\n_...ada lebih banyak janji lagi_"
    
    await query.edit_message_text(
        msg,
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(kb)
    )
    
    return A_VIEW_APPT


async def appt_page_nav_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    current_page = context.user_data.get('appt_page', 0)
    
    if query.data == "appt_page_next":
        context.user_data['appt_page'] = current_page + 1
    elif query.data == "appt_page_prev":
        context.user_data['appt_page'] = max(0, current_page - 1)
    
    return await view_appointment_callback(update, context)


async def manage_appointment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "admin_menu":
        return await admin_menu_callback(update, context)
    
    appointment_id = int(query.data.split("_")[1])
    appt = await db.get_appointment_by_id(appointment_id)
    
    if not appt:
        await query.edit_message_text("❌ Janji tidak ditemukan.")
        return A_MENU
    
    context.user_data['manage_appt_id'] = appointment_id
    
    datetime_str = format_datetime_id(appt['start_dt'])
    status_emoji = "✅" if appt['status'] == 'confirmed' else "✔" if appt['status'] == 'completed' else "❌"
    
    msg = f"📋 *DETAIL JANJI*\n\n"
    msg += f"ID: {appt['id']}\n"
    msg += f"Nama: {appt['user_name']}\n"
    msg += f"Gender: {appt['patient_gender']}\n"
    msg += f"Alamat: {appt['patient_address']}\n"
    msg += f"Terapis: {appt['therapist_name']}\n"
    msg += f"Waktu: {datetime_str}\n"
    msg += f"Durasi: {appt['duration_min']} menit\n"
    msg += f"Status: {status_emoji} {appt['status']}\n"
    
    kb = [
        [InlineKeyboardButton("✏️ Edit Janji", callback_data="edit_appt_menu")],
        [InlineKeyboardButton("🔄 Ubah Status", callback_data="change_status_menu")],
        [InlineKeyboardButton("🗑 Hapus Janji", callback_data=f"delappt_{appointment_id}")],
        [InlineKeyboardButton("🔙 Kembali ke Daftar", callback_data="view_appointment")],
        [InlineKeyboardButton("🏠 Menu Utama", callback_data="back_to_start")]
    ]
    
    await query.edit_message_text(msg, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(kb))
    
    return A_MANAGE_APPT


async def change_status_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    appointment_id = context.user_data.get('manage_appt_id')
    
    kb = [
        [InlineKeyboardButton("✅ Confirmed (Dikonfirmasi)", callback_data=f"chgstatus_confirmed_{appointment_id}")],
        [InlineKeyboardButton("✔ Completed (Selesai)", callback_data=f"chgstatus_completed_{appointment_id}")],
        [InlineKeyboardButton("❌ Cancelled (Dibatalkan)", callback_data=f"chgstatus_cancelled_{appointment_id}")],
        [InlineKeyboardButton("🔙 Kembali", callback_data=f"mgappt_{appointment_id}")]
    ]
    
    await query.edit_message_text(
        "Pilih status baru untuk janji ini:",
        reply_markup=InlineKeyboardMarkup(kb)
    )
    
    return A_MANAGE_APPT


async def change_status_confirm_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    parts = query.data.split("_")
    new_status = parts[1]
    appointment_id = int(parts[2])
    
    try:
        from utils.waitlist_notify import notify_waitlist_for_slot
        
        cancelled_appt = await db.update_appointment_status(appointment_id, new_status)
        
        status_text = "Dikonfirmasi" if new_status == 'confirmed' else "Selesai" if new_status == 'completed' else "Dibatalkan"
        
        kb = [
            [InlineKeyboardButton("📋 Lihat Detail", callback_data=f"mgappt_{appointment_id}")],
            [InlineKeyboardButton("🔙 Ke Daftar Janji", callback_data="view_appointment")],
            [InlineKeyboardButton("🏠 Menu Utama", callback_data="back_to_start")]
        ]
        
        await query.edit_message_text(
            f"✅ Status janji berhasil diubah menjadi *{status_text}*.",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(kb)
        )
        logger.info(f"Appointment {appointment_id} status changed to {new_status}")
        
        if cancelled_appt:
            await notify_waitlist_for_slot(context.application, cancelled_appt)
    except Exception as e:
        logger.error(f"Error updating appointment status: {e}")
        await query.edit_message_text("❌ Terjadi kesalahan. Silakan coba lagi.")
    
    return A_MANAGE_APPT


async def edit_appt_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    appointment_id = context.user_data.get('manage_appt_id')
    
    kb = [
        [InlineKeyboardButton("📝 Edit Nama", callback_data="editfield_name")],
        [InlineKeyboardButton("🏠 Edit Alamat", callback_data="editfield_address")],
        [InlineKeyboardButton("👨‍⚕️ Edit Terapis", callback_data="editfield_therapist")],
        [InlineKeyboardButton("🕒 Edit Waktu", callback_data="editfield_time")],
        [InlineKeyboardButton("🔙 Kembali", callback_data=f"mgappt_{appointment_id}")]
    ]
    
    await query.edit_message_text(
        "Pilih field yang ingin diubah:",
        reply_markup=InlineKeyboardMarkup(kb)
    )
    
    return A_EDIT_APPT_FIELD


async def edit_field_select_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    field = query.data.split("_")[1]
    context.user_data['edit_field'] = field
    
    if field == 'therapist':
        therapists = await db.get_therapists(active_only=True)
        
        kb = []
        for t in therapists:
            kb.append([InlineKeyboardButton(f"{t['name']} ({t['gender']})", callback_data=f"settherapist_{t['id']}")])
        
        kb.append([InlineKeyboardButton("🔙 Kembali", callback_data="edit_appt_menu")])
        
        await query.edit_message_text(
            "Pilih terapis baru:",
            reply_markup=InlineKeyboardMarkup(kb)
        )
        return A_EDIT_APPT_VALUE
    
    elif field == 'time':
        await query.edit_message_text(
            "Ketik waktu baru dalam format:\nYYYY-MM-DD HH:MM\n\nContoh: 2025-11-15 10:00"
        )
        return A_EDIT_APPT_VALUE
    
    elif field == 'name':
        await query.edit_message_text(
            "Ketik nama pasien yang baru:"
        )
        return A_EDIT_APPT_VALUE
    
    elif field == 'address':
        await query.edit_message_text(
            "Ketik alamat pasien yang baru:"
        )
        return A_EDIT_APPT_VALUE
    
    return A_EDIT_APPT_FIELD


async def edit_therapist_confirm_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    therapist_id = int(query.data.split("_")[1])
    appointment_id = context.user_data.get('manage_appt_id')
    
    try:
        await db.update_appointment(appointment_id, therapist_id=therapist_id)
        
        therapist = await db.get_therapist(therapist_id)
        
        kb = [
            [InlineKeyboardButton("📋 Lihat Detail", callback_data=f"mgappt_{appointment_id}")],
            [InlineKeyboardButton("🏠 Menu Utama", callback_data="back_to_start")]
        ]
        
        await query.edit_message_text(
            f"✅ Terapis berhasil diubah menjadi *{therapist['name']}*.",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(kb)
        )
        logger.info(f"Appointment {appointment_id} therapist changed to {therapist_id}")
    except Exception as e:
        logger.error(f"Error updating appointment therapist: {e}")
        await query.edit_message_text("❌ Terjadi kesalahan. Silakan coba lagi.")
    
    return A_MANAGE_APPT


async def edit_appt_value_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    field = context.user_data.get('edit_field')
    appointment_id = context.user_data.get('manage_appt_id')
    new_value = update.message.text.strip()
    
    kb = [
        [InlineKeyboardButton("📋 Lihat Detail", callback_data=f"mgappt_{appointment_id}")],
        [InlineKeyboardButton("🏠 Menu Utama", callback_data="back_to_start")]
    ]
    
    try:
        if field == 'name':
            await db.update_appointment(appointment_id, user_name=new_value)
            await update.message.reply_text(
                f"✅ Nama pasien berhasil diubah menjadi *{new_value}*.",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(kb)
            )
            logger.info(f"Appointment {appointment_id} name changed to {new_value}")
        
        elif field == 'address':
            await db.update_appointment(appointment_id, patient_address=new_value)
            await update.message.reply_text(
                f"✅ Alamat berhasil diubah.",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(kb)
            )
            logger.info(f"Appointment {appointment_id} address changed")
        
        elif field == 'time':
            from datetime import datetime
            from utils.datetime_helper import tz_jakarta
            
            try:
                dt = datetime.strptime(new_value, "%Y-%m-%d %H:%M")
                dt = tz_jakarta.localize(dt)
                await db.update_appointment(appointment_id, start_dt=dt.isoformat())
                await update.message.reply_text(
                    f"✅ Waktu berhasil diubah menjadi *{new_value}*.",
                    parse_mode='Markdown',
                    reply_markup=InlineKeyboardMarkup(kb)
                )
                logger.info(f"Appointment {appointment_id} time changed to {new_value}")
            except ValueError:
                await update.message.reply_text(
                    "❌ Format waktu salah. Gunakan format: YYYY-MM-DD HH:MM"
                )
                return A_EDIT_APPT_VALUE
    
    except Exception as e:
        logger.error(f"Error updating appointment: {e}")
        await update.message.reply_text("❌ Terjadi kesalahan. Silakan coba lagi.")
    
    return A_MANAGE_APPT


async def admin_waitlist_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    waitlist = await db.get_waitlist()
    
    if not waitlist:
        msg = "⏳ *DAFTAR TUNGGU*\n\nTidak ada yang menunggu."
        kb = [
            [InlineKeyboardButton("🔙 Kembali ke Admin", callback_data="admin_menu")],
            [InlineKeyboardButton("🏠 Menu Utama", callback_data="back_to_start")]
        ]
    else:
        msg = "⏳ *DAFTAR TUNGGU*\n\nKlik entry untuk manage follow-up:\n\n"
        kb = []
        
        for i, item in enumerate(waitlist, 1):
            item_dict = dict(item)
            date_str = item_dict.get('requested_date') or "Tidak ditentukan"
            phone_display = item_dict.get('phone') or 'Tidak ada'
            label = f"{i}. {item_dict['name']} ({item_dict['gender']}) - {phone_display}"
            kb.append([InlineKeyboardButton(label, callback_data=f"wl_view_{item_dict['id']}")])
        
        kb.append([InlineKeyboardButton("🔙 Kembali ke Admin", callback_data="admin_menu")])
        kb.append([InlineKeyboardButton("🏠 Menu Utama", callback_data="back_to_start")])
    
    await query.edit_message_text(msg, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(kb))
    
    return A_WAITLIST_MANAGE


async def admin_holidays_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    weekly = await db.get_holiday_weekly()
    dates = await db.get_holiday_dates()
    
    msg = "🏖 *KELOLA HARI LIBUR*\n\n"
    
    if weekly:
        msg += "*Libur Mingguan:*\n"
        for w in weekly:
            msg += f"• {WEEKDAY_NAMES_ID[w['weekday']]}\n"
    else:
        msg += "*Libur Mingguan:* Tidak ada\n"
    
    msg += "\n"
    
    if dates:
        msg += "*Libur Tanggal Tertentu:*\n"
        for d in dates[:10]:
            msg += f"• {d['date']}\n"
    else:
        msg += "*Libur Tanggal Tertentu:* Tidak ada\n"
    
    kb = [
        [InlineKeyboardButton("➕ Tambah Libur Tanggal", callback_data="add_holiday_date")],
        [InlineKeyboardButton("🔙 Kembali ke Admin", callback_data="admin_menu")],
        [InlineKeyboardButton("🏠 Menu Utama", callback_data="back_to_start")]
    ]
    
    await query.edit_message_text(msg, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(kb))
    
    return A_HOLIDAY_MENU


async def show_holiday_calendar(update: Update, context: ContextTypes.DEFAULT_TYPE, year: int = None, month: int = None):
    query = update.callback_query
    
    from datetime import date
    from utils.date_picker import create_calendar_keyboard
    import calendar
    
    today = date.today()
    if year is None or month is None:
        year, month = today.year, today.month
    
    max_date = date(today.year + 2, 12, 31)
    
    existing_holidays = await db.get_holiday_dates()
    holiday_set = {parse_date(h['date']) for h in existing_holidays if parse_date(h['date'])}
    
    available_dates = set()
    for day in range(1, calendar.monthrange(year, month)[1] + 1):
        check_date = date(year, month, day)
        if check_date >= today and check_date not in holiday_set:
            available_dates.add(check_date)
    
    kb, header_text = create_calendar_keyboard(year, month, available_dates, max_date)
    
    msg = (
        f"📅 *TAMBAH HARI LIBUR*\n\n"
        f"{header_text}\n\n"
        f"Pilih tanggal yang ingin ditambahkan sebagai hari libur:\n"
        f"🟢 = Tersedia (dapat dipilih)\n"
        f"⚪ = Sudah libur atau tidak dapat dipilih"
    )
    
    kb.append([InlineKeyboardButton("🔙 Kembali", callback_data="admin_holidays")])
    kb.append([InlineKeyboardButton("🏠 Menu Utama", callback_data="back_to_start")])
    
    await query.edit_message_text(
        msg,
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(kb)
    )
    
    return A_ADD_HOL_DATE


async def add_holiday_date_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await show_holiday_calendar(update, context)


async def holiday_calendar_nav_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    parts = query.data.split("_")
    direction = parts[1]
    year = int(parts[2])
    month = int(parts[3])
    
    from utils.date_picker import get_next_month, get_prev_month
    
    if direction == "next":
        year, month = get_next_month(year, month)
    elif direction == "prev":
        year, month = get_prev_month(year, month)
    
    return await show_holiday_calendar(update, context, year, month)


async def holiday_calendar_noop_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    return None


async def add_holiday_date_selected_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    date_iso = query.data.split("_", 1)[1]
    date_obj = parse_date(date_iso)
    
    if not date_obj:
        kb = [[InlineKeyboardButton("🔙 Kembali", callback_data="admin_holidays")]]
        await query.edit_message_text(
            "❌ Tanggal tidak valid.",
            reply_markup=InlineKeyboardMarkup(kb)
        )
        return A_HOLIDAY_MENU
    
    try:
        await db.add_holiday_date(date_obj)
        
        kb = [
            [InlineKeyboardButton("🏖 Kembali ke Holidays", callback_data="admin_holidays")],
            [InlineKeyboardButton("🏠 Menu Utama", callback_data="back_to_start")]
        ]
        
        date_formatted = format_date_id(date_obj, include_year=True)
        await query.edit_message_text(
            f"✅ *Hari libur ditambahkan*\n\n📅 Tanggal: {date_formatted}",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(kb)
        )
        logger.info(f"Holiday date added: {date_obj.isoformat()}")
    except Exception as e:
        logger.error(f"Error adding holiday date: {e}")
        kb = [[InlineKeyboardButton("🔙 Kembali", callback_data="admin_holidays")]]
        await query.edit_message_text(
            "❌ Terjadi kesalahan. Silakan coba lagi.",
            reply_markup=InlineKeyboardMarkup(kb)
        )
    
    return A_HOLIDAY_MENU


async def add_holiday_date_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    date_obj = parse_date(text)
    
    if not date_obj:
        await update.message.reply_text("Format salah. Gunakan YYYY-MM-DD. Contoh: 2025-12-25")
        return A_ADD_HOL_DATE
    
    try:
        await db.add_holiday_date(date_obj)
        
        kb = [
            [InlineKeyboardButton("⚙️ Kembali ke Admin", callback_data="admin_menu")],
            [InlineKeyboardButton("🏠 Menu Utama", callback_data="back_to_start")]
        ]
        
        await update.message.reply_text(
            f"✅ Tanggal {date_obj.isoformat()} ditambahkan sebagai hari libur.",
            reply_markup=InlineKeyboardMarkup(kb)
        )
        logger.info(f"Holiday date added: {date_obj.isoformat()}")
    except Exception as e:
        logger.error(f"Error adding holiday date: {e}")
        await update.message.reply_text("❌ Terjadi kesalahan. Silakan coba lagi.")
    
    return A_MENU


async def admin_export_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    try:
        appointments = await db.get_appointments()
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        writer.writerow(['ID', 'User ID', 'Nama Pasien', 'Gender', 'Alamat', 'Terapis', 'Waktu', 'Durasi', 'Status', 'Dibuat'])
        
        for appt in appointments:
            writer.writerow([
                appt['id'],
                appt['user_id'],
                appt['user_name'],
                appt['patient_gender'],
                appt.get('patient_address', ''),
                appt['therapist_name'],
                appt['start_dt'],
                appt['duration_min'],
                appt['status'],
                appt['created_at']
            ])
        
        output.seek(0)
        
        await query.message.reply_document(
            document=output.getvalue().encode('utf-8'),
            filename='appointments_export.csv',
            caption="📊 Data janji bekam (CSV)"
        )
        
        kb = [
            [InlineKeyboardButton("⚙️ Kembali ke Admin", callback_data="admin_menu")],
            [InlineKeyboardButton("🏠 Menu Utama", callback_data="back_to_start")]
        ]
        
        await query.edit_message_text(
            "✅ Data berhasil di-export.",
            reply_markup=InlineKeyboardMarkup(kb)
        )
        
        logger.info("Appointments exported to CSV")
        
    except Exception as e:
        logger.error(f"Error exporting data: {e}")
        kb = [
            [InlineKeyboardButton("⚙️ Kembali ke Admin", callback_data="admin_menu")],
            [InlineKeyboardButton("🏠 Menu Utama", callback_data="back_to_start")]
        ]
        await query.edit_message_text(
            "❌ Terjadi kesalahan saat export data.",
            reply_markup=InlineKeyboardMarkup(kb)
        )
    
    return A_MENU

async def view_waitlist_entry_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    waitlist_id = int(query.data.split("_")[2])
    entry = await db.get_waitlist_entry(waitlist_id)
    
    if not entry:
        await query.edit_message_text(
            "❌ Entry tidak ditemukan.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Kembali", callback_data="admin_waitlist")
            ]])
        )
        return A_MENU
    
    entry_dict = dict(entry)
    
    context.user_data['wl_id'] = waitlist_id
    context.user_data['wl_chat_id'] = entry_dict['chat_id']
    context.user_data['wl_name'] = entry_dict['name']
    
    date_str = entry_dict.get('requested_date') or "Tidak ditentukan"
    phone_str = entry_dict.get('phone') or 'Tidak ada'
    
    msg = (
        f"⏳ *DETAIL DAFTAR TUNGGU*\n\n"
        f"👤 Nama: {entry_dict['name']}\n"
        f"🚻 Jenis Kelamin: {entry_dict['gender']}\n"
        f"📞 Nomor Telepon: {phone_str}\n"
        f"📅 Tanggal Request: {date_str}\n"
        f"📝 Dibuat: {entry_dict['created_at'][:10]}\n\n"
        f"*Pilih aksi follow-up:*"
    )
    
    kb = [
        [InlineKeyboardButton("✅ Konfirmasi Slot Tersedia", callback_data=f"wl_confirm_{waitlist_id}")],
        [InlineKeyboardButton("❌ Informasikan Penuh", callback_data=f"wl_inform_full_{waitlist_id}")],
        [InlineKeyboardButton("🗑️ Hapus dari Waitlist", callback_data=f"wl_delete_{waitlist_id}")],
        [InlineKeyboardButton("🔙 Kembali", callback_data="admin_waitlist")]
    ]
    
    await query.edit_message_text(msg, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(kb))
    
    return A_WAITLIST_MANAGE


async def confirm_slot_available_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    waitlist_id = int(query.data.split("_")[2])
    entry = await db.get_waitlist_entry(waitlist_id)
    
    if not entry:
        await query.edit_message_text(
            "❌ Entry tidak ditemukan.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Kembali", callback_data="admin_waitlist")
            ]])
        )
        return A_MENU
    
    try:
        notification_msg = (
            f"✅ *Kabar Gembira!*\n\n"
            f"Halo {entry['name']},\n\n"
            f"Kami ingin memberitahu bahwa *SLOT BEKAM SUDAH TERSEDIA*!\n\n"
            f"Silakan booking sekarang dengan mengetik /start\n\n"
            f"Terima kasih sudah menunggu 🙏"
        )
        
        await context.bot.send_message(
            chat_id=entry['chat_id'],
            text=notification_msg,
            parse_mode='Markdown'
        )
        
        await db.delete_waitlist_entry(waitlist_id)
        
        kb = [[InlineKeyboardButton("🔙 Kembali ke Waitlist", callback_data="admin_waitlist")]]
        await query.edit_message_text(
            f"✅ Notifikasi berhasil dikirim ke *{entry['name']}*.\n\nEntry telah dihapus dari waitlist.",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(kb)
        )
        
        logger.info(f"Waitlist notification sent to {entry['chat_id']}")
        
    except Exception as e:
        logger.error(f"Error sending waitlist notification: {e}")
        kb = [[InlineKeyboardButton("🔙 Kembali", callback_data="admin_waitlist")]]
        await query.edit_message_text(
            "❌ Gagal mengirim notifikasi. User mungkin memblokir bot.",
            reply_markup=InlineKeyboardMarkup(kb)
        )
    
    return A_MENU


async def inform_waitlist_full_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    waitlist_id = int(query.data.split("_")[3])
    entry = await db.get_waitlist_entry(waitlist_id)
    
    if not entry:
        await query.edit_message_text(
            "❌ Entry tidak ditemukan.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Kembali", callback_data="admin_waitlist")
            ]])
        )
        return A_MENU
    
    try:
        notification_msg = (
            f"📋 *Info Daftar Tunggu*\n\n"
            f"Halo {entry['name']},\n\n"
            f"Terima kasih sudah sabar menunggu. Untuk saat ini slot bekam masih *PENUH*.\n\n"
            f"Anda akan tetap di daftar tunggu dan kami akan menghubungi ketika ada slot tersedia.\n\n"
            f"Terima kasih atas pengertiannya 🙏"
        )
        
        await context.bot.send_message(
            chat_id=entry['chat_id'],
            text=notification_msg,
            parse_mode='Markdown'
        )
        
        kb = [[InlineKeyboardButton("🔙 Kembali ke Waitlist", callback_data="admin_waitlist")]]
        await query.edit_message_text(
            f"✅ Notifikasi 'penuh' berhasil dikirim ke *{entry['name']}*.\n\nEntry masih di waitlist.",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(kb)
        )
        
        logger.info(f"Full notification sent to {entry['chat_id']}")
        
    except Exception as e:
        logger.error(f"Error sending full notification: {e}")
        kb = [[InlineKeyboardButton("🔙 Kembali", callback_data="admin_waitlist")]]
        await query.edit_message_text(
            "❌ Gagal mengirim notifikasi. User mungkin memblokir bot.",
            reply_markup=InlineKeyboardMarkup(kb)
        )
    
    return A_MENU


async def delete_waitlist_entry_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    waitlist_id = int(query.data.split("_")[2])
    entry = await db.get_waitlist_entry(waitlist_id)
    
    if not entry:
        await query.edit_message_text(
            "❌ Entry tidak ditemukan.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Kembali", callback_data="admin_waitlist")
            ]])
        )
        return A_MENU
    
    await db.delete_waitlist_entry(waitlist_id)
    
    kb = [[InlineKeyboardButton("🔙 Kembali ke Waitlist", callback_data="admin_waitlist")]]
    await query.edit_message_text(
        f"✅ *{entry['name']}* berhasil dihapus dari waitlist.",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(kb)
    )
    
    logger.info(f"Waitlist entry {waitlist_id} deleted")
    
    return A_MENU


async def schedule_inactive_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    therapist_id = int(query.data.split("_")[2])
    therapist = await db.get_therapist(therapist_id)
    
    if not therapist:
        kb = [[InlineKeyboardButton("🔙 Kembali", callback_data="admin_therapists")]]
        await query.edit_message_text(
            "❌ Terapis tidak ditemukan.",
            reply_markup=InlineKeyboardMarkup(kb)
        )
        return A_MENU
    
    context.user_data['schedule_inactive_therapist_id'] = therapist_id
    
    kb = [
        [InlineKeyboardButton("1 hari", callback_data=f"inactive_dur_1_{therapist_id}")],
        [InlineKeyboardButton("3 hari", callback_data=f"inactive_dur_3_{therapist_id}")],
        [InlineKeyboardButton("7 hari (1 minggu)", callback_data=f"inactive_dur_7_{therapist_id}")],
        [InlineKeyboardButton("14 hari (2 minggu)", callback_data=f"inactive_dur_14_{therapist_id}")],
        [InlineKeyboardButton("30 hari (1 bulan)", callback_data=f"inactive_dur_30_{therapist_id}")],
        [InlineKeyboardButton("✏️ Custom (ketik jumlah hari)", callback_data=f"inactive_custom_{therapist_id}")],
        [InlineKeyboardButton("🔙 Batal", callback_data=f"th_detail_{therapist_id}")]
    ]
    
    msg = (
        f"📅 *JADWALKAN NONAKTIF*\n\n"
        f"Terapis: *{therapist['name']}*\n\n"
        f"Pilih durasi nonaktif (mulai sekarang):"
    )
    
    await query.edit_message_text(msg, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(kb))
    
    return A_SCHEDULE_INACTIVE


async def schedule_inactive_duration_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    parts = query.data.split("_")
    days = int(parts[2])
    therapist_id = int(parts[3])
    
    try:
        from utils.datetime_helper import now_jakarta
        from datetime import timedelta
        
        therapist = await db.get_therapist(therapist_id)
        start_time = now_jakarta()
        end_time = start_time + timedelta(days=days)
        
        await db.schedule_therapist_inactive(
            therapist_id,
            start_time.isoformat(),
            end_time.isoformat()
        )
        
        kb = [[InlineKeyboardButton("🔙 Kembali", callback_data=f"th_detail_{therapist_id}")]]
        
        await query.edit_message_text(
            f"✅ Terapis *{therapist['name']}* dijadwalkan nonaktif selama *{days} hari*.\n\n"
            f"Mulai: {format_datetime_id(start_time.isoformat())}\n"
            f"Sampai: {format_datetime_id(end_time.isoformat())}\n\n"
            f"Status akan otomatis berubah pada waktu yang dijadwalkan.",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(kb)
        )
        
        logger.info(f"Therapist {therapist_id} scheduled inactive for {days} days")
    except Exception as e:
        logger.error(f"Error scheduling inactive: {e}")
        kb = [[InlineKeyboardButton("🔙 Kembali", callback_data=f"th_detail_{therapist_id}")]]
        await query.edit_message_text(
            "❌ Terjadi kesalahan. Silakan coba lagi.",
            reply_markup=InlineKeyboardMarkup(kb)
        )
    
    return A_TH_DETAIL


async def schedule_inactive_custom_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    therapist_id = int(query.data.split("_")[2])
    context.user_data['schedule_inactive_therapist_id'] = therapist_id
    
    kb = [[InlineKeyboardButton("🔙 Batal", callback_data=f"th_detail_{therapist_id}")]]
    
    await query.edit_message_text(
        "✏️ *CUSTOM DURASI*\n\n"
        "Ketik jumlah hari nonaktif (angka saja, 1-365):",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(kb)
    )
    
    return A_INACTIVE_CUSTOM_DAYS


async def schedule_inactive_custom_days_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    therapist_id = context.user_data.get('schedule_inactive_therapist_id')
    
    if not therapist_id:
        await update.message.reply_text("❌ Terjadi kesalahan. Silakan coba lagi.")
        return A_MENU
    
    try:
        days = int(update.message.text.strip())
        
        if days < 1 or days > 365:
            kb = [[InlineKeyboardButton("🔙 Batal", callback_data=f"th_detail_{therapist_id}")]]
            await update.message.reply_text(
                "❌ Jumlah hari harus antara 1-365.\n\nSilakan ketik jumlah hari yang valid:",
                reply_markup=InlineKeyboardMarkup(kb)
            )
            return A_INACTIVE_CUSTOM_DAYS
        
        from utils.datetime_helper import now_jakarta
        from datetime import timedelta
        
        therapist = await db.get_therapist(therapist_id)
        start_time = now_jakarta()
        end_time = start_time + timedelta(days=days)
        
        await db.schedule_therapist_inactive(
            therapist_id,
            start_time.isoformat(),
            end_time.isoformat()
        )
        
        kb = [[InlineKeyboardButton("🔙 Kembali", callback_data=f"th_detail_{therapist_id}")]]
        
        await update.message.reply_text(
            f"✅ Terapis *{therapist['name']}* dijadwalkan nonaktif selama *{days} hari*.\n\n"
            f"Mulai: {format_datetime_id(start_time.isoformat())}\n"
            f"Sampai: {format_datetime_id(end_time.isoformat())}\n\n"
            f"Status akan otomatis berubah pada waktu yang dijadwalkan.",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(kb)
        )
        
        logger.info(f"Therapist {therapist_id} scheduled inactive for {days} days (custom)")
    except ValueError:
        kb = [[InlineKeyboardButton("🔙 Batal", callback_data=f"th_detail_{therapist_id}")]]
        await update.message.reply_text(
            "❌ Input tidak valid. Silakan ketik angka (1-365):",
            reply_markup=InlineKeyboardMarkup(kb)
        )
        return A_INACTIVE_CUSTOM_DAYS
    except Exception as e:
        logger.error(f"Error scheduling inactive (custom): {e}")
        kb = [[InlineKeyboardButton("🔙 Kembali", callback_data=f"th_detail_{therapist_id}")]]
        await update.message.reply_text(
            "❌ Terjadi kesalahan. Silakan coba lagi.",
            reply_markup=InlineKeyboardMarkup(kb)
        )
    
    return A_TH_DETAIL


async def cancel_inactive_schedule_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    therapist_id = int(query.data.split("_")[2])
    
    try:
        therapist = await db.get_therapist(therapist_id)
        await db.cancel_scheduled_inactive(therapist_id)
        
        kb = [[InlineKeyboardButton("🔙 Kembali", callback_data=f"th_detail_{therapist_id}")]]
        
        await query.edit_message_text(
            f"✅ Jadwal nonaktif untuk terapis *{therapist['name']}* telah dibatalkan.",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(kb)
        )
        
        logger.info(f"Cancelled inactive schedule for therapist {therapist_id}")
    except Exception as e:
        logger.error(f"Error cancelling inactive schedule: {e}")
        kb = [[InlineKeyboardButton("🔙 Kembali", callback_data=f"th_detail_{therapist_id}")]]
        await query.edit_message_text(
            "❌ Terjadi kesalahan. Silakan coba lagi.",
            reply_markup=InlineKeyboardMarkup(kb)
        )
    
    return A_TH_DETAIL
