def escape_markdown_v2(text: str) -> str:
    special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in special_chars:
        text = text.replace(char, f'\\{char}')
    return text

def format_confirmation_message(name: str, gender: str, therapist: str, datetime_str: str, duration: int, address: str) -> str:
    name_escaped = escape_markdown_v2(name)
    gender_escaped = escape_markdown_v2(gender)
    therapist_escaped = escape_markdown_v2(therapist)
    datetime_escaped = escape_markdown_v2(datetime_str)
    address_escaped = escape_markdown_v2(address)
    duration_escaped = escape_markdown_v2(str(duration))
    
    msg = (
        f"✅ *KONFIRMASI BOOKING*\n\n"
        f"📝 *Nama Pasien:* {name_escaped}\n"
        f"👤 *Jenis Kelamin:* {gender_escaped}\n"
        f"👨‍⚕️ *Terapis:* {therapist_escaped}\n"
        f"🕒 *Waktu:* {datetime_escaped}\n"
        f"⏱ *Durasi:* {duration_escaped} menit\n"
        f"📍 *Alamat:* {address_escaped}\n\n"
        f"_Apakah data sudah benar?_"
    )
    return msg

def format_success_message(name: str, therapist: str, datetime_str: str, duration: int, address: str) -> str:
    name_escaped = escape_markdown_v2(name)
    therapist_escaped = escape_markdown_v2(therapist)
    datetime_escaped = escape_markdown_v2(datetime_str)
    address_escaped = escape_markdown_v2(address)
    duration_escaped = escape_markdown_v2(str(duration))
    
    msg = (
        f"🎉 *BOOKING BERHASIL\\!*\n\n"
        f"Terima kasih\\! Janji Anda telah dikonfirmasi\\.\n\n"
        f"📝 *Detail Janji:*\n"
        f"\\- Nama: {name_escaped}\n"
        f"\\- Terapis: {therapist_escaped}\n"
        f"\\- Waktu: {datetime_escaped}\n"
        f"\\- Durasi: {duration_escaped} menit\n"
        f"\\- Alamat: {address_escaped}\n\n"
        f"⏰ Anda akan menerima pengingat 30 menit sebelum jadwal\\.\n\n"
        f"_Semoga lekas sembuh\\!_ 🤲"
    )
    return msg

def format_reminder_message(name: str, therapist: str, datetime_str: str, is_today: bool) -> str:
    time_prefix = "hari ini" if is_today else ""
    
    msg = (
        f"🔔 *PENGINGAT JANJI BEKAM*\n\n"
        f"Assalamu'alaikum {name},\n\n"
        f"Ini pengingat bahwa Anda memiliki janji bekam {time_prefix}:\n\n"
        f"👨‍⚕️ Terapis: {therapist}\n"
        f"🕒 Waktu: {datetime_str}\n\n"
        f"Silakan bersiap dan datang tepat waktu.\n\n"
        f"_Jazakallahu khairan_ 🤲"
    )
    return msg
