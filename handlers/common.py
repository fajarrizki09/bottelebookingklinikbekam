import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from config import Config

logger = logging.getLogger(__name__)

S_START = 0


async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    kb = [
        [InlineKeyboardButton("🩺 Buat Janji Baru", callback_data="make")],
        [InlineKeyboardButton("📋 Lihat Janji Saya", callback_data="my_appointments")]
    ]
    
    if user and user.id in Config.ADMIN_IDS:
        kb.append([InlineKeyboardButton("⚙️ Panel Admin", callback_data="admin_menu")])
    
    from utils.hijri_helper import get_upcoming_sunnah_date, get_days_until_next_sunnah
    from services.health_content import get_daily_health_tip
    
    # --- INFO HARI SUNNAH BEKAM ---
    try:
        next_sunnah = get_upcoming_sunnah_date()
        days_until = get_days_until_next_sunnah(next_sunnah)

        logger.info(f"DEBUG >> next_sunnah={next_sunnah}, days_until={days_until}")

        sunnah_info = ""
        if next_sunnah and days_until >= 0:
            hijri_day = next_sunnah['hijri_day']
            hijri_month = next_sunnah['hijri_month_name']

            if days_until == 0:
                sunnah_info = (
                    f"\n🌙 *Hari ini {hijri_day} {hijri_month}* — *Hari Sunnah Bekam!* 🌙\n"
                    "Rasulullah ﷺ bersabda:\n"
                    "_“Sebaik-baik hari untuk berbekam adalah tanggal 17, 19, dan 21 Hijriyah.”_ (HR. Tirmidzi)\n"
                    "💡 Mari manfaatkan kesempatan ini untuk menjaga kesehatan sesuai sunnah Rasulullah ﷺ.\n"
                )
            elif days_until <= 7:
                sunnah_info = (
                    f"\n🌙 *Tanggal Sunnah Bekam berikutnya:* {hijri_day} {hijri_month} "
                    f"(*{days_until} hari lagi*)\n"
                    "💡 Siapkan diri untuk berbekam pada hari sunnah agar mendapat keberkahan dan kesehatan. 🤲\n"
                )
            else:
                sunnah_info = (
                    f"\n🌙 *Tanggal Sunnah Bekam berikutnya:* {hijri_day} {hijri_month} "
                    f"(*{days_until} hari lagi*)\n"
                )
    except Exception as e:
        logger.error(f"Error getting sunnah date: {e}")
        sunnah_info = ""

    # --- TIPS KESEHATAN ---
    try:
        health_tip = await get_daily_health_tip()
    except Exception as e:
        logger.error(f"Error getting health tip: {e}")
        health_tip = (
            "💡 *Tips Kesehatan Hari Ini:*\n\n"
            "🌿 Minum air putih minimal 8 gelas sehari untuk menjaga kesehatan tubuh\n"
            "🏃 Lakukan olahraga ringan minimal 30 menit setiap hari\n"
            "🥗 Konsumsi makanan bergizi seimbang\n"
            "😴 Tidur cukup 7–8 jam per hari\n"
            "🧘 Kelola stres dengan baik\n\n"
            "Jaga kesehatan Anda dengan gaya hidup sehat!"
        )
    
    # --- PESAN UTAMA ---
    welcome_msg = (
        "🩺 *RUMAH SEHAT DANI SABRI*\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "✨ *Assalamu'alaikum Warahmatullahi Wabarakatuh* ✨\n\n"
        "Selamat datang di layanan *Reservasi Bekam Online*!\n"
        f"{sunnah_info}\n"
        "🌟 *Keutamaan Bekam dalam Islam:*\n"
        "Rasulullah ﷺ bersabda:\n"
        "_\"Sebaik-baik pengobatan yang kalian lakukan adalah berbekam.\"_ (HR. Bukhari & Muslim)\n\n"
        "💡 *Manfaat Bekam:*\n"
        "• Melancarkan peredaran darah\n"
        "• Mengeluarkan racun dari tubuh\n"
        "• Meningkatkan sistem kekebalan tubuh\n"
        "• Mengurangi nyeri dan pegal-pegal\n\n"
        f"{health_tip}\n\n"
        "📋 Silakan pilih menu di bawah untuk melanjutkan:"
    )
    
    return welcome_msg, InlineKeyboardMarkup(kb)


# --- HANDLER COMMAND / CALLBACKS ---

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_msg, reply_markup = await show_main_menu(update, context)
    await update.message.reply_text(
        welcome_msg,
        parse_mode='Markdown',
        reply_markup=reply_markup
    )
    return S_START


async def back_to_start_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data.clear()
    
    welcome_msg, reply_markup = await show_main_menu(update, context)
    await query.edit_message_text(
        welcome_msg,
        parse_mode='Markdown',
        reply_markup=reply_markup
    )
    return S_START


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "🩺 *RESERVASI BEKAM RUMAH SEHAT DANI SABRI - BANTUAN*\n\n"
        "Cara Membuat Janji:\n"
        "1. Ketik /start untuk memulai\n"
        "2. Pilih jenis kelamin pasien\n"
        "3. Pilih tanggal yang tersedia\n"
        "4. Pilih waktu yang tersedia\n"
        "5. Pilih terapis\n"
        "6. Masukkan nama pasien\n"
        "7. Masukkan alamat pasien\n"
        "8. Konfirmasi booking\n\n"
        "Fitur Lain:\n"
        "• Daftar tunggu jika tidak ada slot tersedia\n"
        "• Reminder otomatis 30 menit sebelum jadwal\n"
        "• Data tersimpan saat bot restart\n\n"
        "Butuh bantuan?\n"
        "Hubungi admin untuk bantuan lebih lanjut."
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")


async def cancel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    kb = [[InlineKeyboardButton("🔄 Mulai dari Awal", callback_data="make")]]
    await update.message.reply_text(
        "❌ *Operasi Dibatalkan*\n\n"
        "Silakan klik tombol di bawah atau ketik /start untuk memulai lagi.",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(kb)
    )
    return ConversationHandler.END


async def timeout_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    kb = [[InlineKeyboardButton("🔄 Mulai dari Awal", callback_data="make")]]
    msg = (
        "⏱️ *Sesi Berakhir*\n\n"
        "Maaf, sesi Anda telah berakhir karena tidak ada aktivitas selama 10 menit.\n\n"
        "💡 Silakan klik tombol di bawah atau ketik /start untuk memulai lagi."
    )
    try:
        if update.message:
            await update.message.reply_text(msg, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(kb))
        elif update.callback_query:
            await update.callback_query.answer("Sesi Anda telah berakhir")
            try:
                await update.callback_query.message.reply_text(msg, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(kb))
            except:
                await update.callback_query.message.edit_text(msg, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(kb))
    except Exception as e:
        logger.error(f"Error in timeout_handler: {e}")
    return ConversationHandler.END


async def fallback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    kb = [[InlineKeyboardButton("🔄 Mulai dari Awal", callback_data="make")]]
    msg = (
        "❓ *Perintah Tidak Dikenali*\n\n"
        "Maaf, sepertinya ada yang salah atau sesi Anda sudah berakhir.\n\n"
        "💡 *Kemungkinan penyebab:*\n"
        "• Bot baru saja di-restart\n"
        "• Sesi Anda telah timeout (10 menit tidak aktif)\n"
        "• Perintah tidak valid\n\n"
        "💬 *Jika tombol tidak bekerja, ketik:* /start"
    )
    try:
        if update.message:
            await update.message.reply_text(msg, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(kb))
        elif update.callback_query:
            await update.callback_query.answer("Perintah tidak dikenali")
            try:
                await update.callback_query.message.reply_text(msg, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(kb))
            except:
                await update.callback_query.message.edit_text(msg, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(kb))
    except Exception as e:
        logger.error(f"Error in fallback_handler: {e}")
    return ConversationHandler.END


async def global_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return
    logger.warning(f"Unhandled callback query from user {update.effective_user.id}: {query.data}")
    context.user_data.clear()
    await query.answer("Sesi lama sudah tidak berlaku")
    msg = (
        "⚠️ *Sesi Sudah Berakhir*\n\n"
        "Tombol ini dari sesi lama yang sudah tidak berlaku.\n\n"
        "💡 *Kemungkinan penyebab:*\n"
        "• Bot baru saja di-restart\n"
        "• Sesi Anda telah timeout setelah 10 menit tidak aktif\n"
        "• Anda mengklik tombol dari pesan lama\n\n"
        "Silakan ketik /start untuk memulai booking baru."
    )
    try:
        await query.message.edit_text(msg, parse_mode='Markdown')
    except Exception as e:
        logger.debug(f"Could not edit message, sending new message: {e}")
        try:
            await query.message.reply_text(msg, parse_mode='Markdown')
        except Exception as e2:
            logger.error(f"Error in global_callback_handler: {e2}")
