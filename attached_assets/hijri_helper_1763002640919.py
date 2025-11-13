from hijri_converter import Hijri, Gregorian
from datetime import date, timedelta, datetime
from typing import List, Dict, Optional
import pytz

# Nama-nama bulan Hijriyah (bahasa Indonesia)
HIJRI_MONTHS_ID = [
    'Muharram', 'Safar', 'Rabiul Awal', 'Rabiul Akhir', 'Jumadil Awal', 'Jumadil Akhir',
    'Rajab', 'Syaban', 'Ramadan', 'Syawal', 'Dzulqaidah', 'Dzulhijjah'
]

# Tanggal sunnah bekam (17, 19, 21 Hijriyah)
SUNNAH_DAYS = [17, 19, 21]


def get_upcoming_sunnah_date(today: Optional[date] = None) -> Optional[Dict]:
    """
    Mengambil tanggal bekam sunnah berikutnya berdasarkan waktu Asia/Jakarta.
    """
    jakarta = pytz.timezone("Asia/Jakarta")
    if today is None:
        today = datetime.now(jakarta).date()

    for days_ahead in range(0, 90):  # cek 3 bulan ke depan
        check_date = today + timedelta(days=days_ahead)
        hijri_date = Gregorian.fromdate(check_date).to_hijri()

        if hijri_date.day in SUNNAH_DAYS:
            return {
                'gregorian_date': check_date,
                'hijri_day': hijri_date.day,
                'hijri_month': hijri_date.month,
                'hijri_month_name': HIJRI_MONTHS_ID[hijri_date.month - 1],
                'hijri_year': hijri_date.year
            }
    return None


def get_days_until_next_sunnah(sunnah_date: Optional[Dict] = None) -> int:
    """
    Menghitung berapa hari lagi menuju tanggal bekam sunnah berikutnya.
    Sekarang menggunakan hasil dari get_upcoming_sunnah_date() agar sinkron.
    """
    jakarta = pytz.timezone("Asia/Jakarta")
    today = datetime.now(jakarta).date()

    if not sunnah_date:
        sunnah_date = get_upcoming_sunnah_date(today)

    if not sunnah_date:
        return -1

    return (sunnah_date['gregorian_date'] - today).days


def get_next_sunnah_dates(months_ahead: int = 1) -> List[Dict]:
    """
    Mengembalikan daftar semua tanggal bekam sunnah dalam rentang bulan tertentu.
    """
    jakarta = pytz.timezone("Asia/Jakarta")
    today = datetime.now(jakarta).date()
    end_date = today + timedelta(days=months_ahead * 30)

    sunnah_dates = []
    check_date = today

    while check_date <= end_date:
        hijri_date = Gregorian.fromdate(check_date).to_hijri()

        if hijri_date.day in SUNNAH_DAYS:
            sunnah_dates.append({
                'gregorian_date': check_date,
                'hijri_day': hijri_date.day,
                'hijri_month': hijri_date.month,
                'hijri_month_name': HIJRI_MONTHS_ID[hijri_date.month - 1],
                'hijri_year': hijri_date.year
            })

        check_date += timedelta(days=1)

    return sunnah_dates


def format_sunnah_notification(sunnah_date: Dict) -> str:
    """
    Format pesan pengingat untuk hari bekam sunnah.
    """
    gregorian_str = sunnah_date['gregorian_date'].strftime('%d-%m-%Y')
    hijri_day = sunnah_date['hijri_day']
    hijri_month = sunnah_date['hijri_month_name']

    msg = (
        f"🌙 *PENGINGAT HARI BEKAM SUNNAH*\n\n"
        f"Assalamu'alaikum warahmatullahi wabarakatuh,\n\n"
        f"📅 *Tanggal Masehi:* {gregorian_str}\n"
        f"🌙 *Tanggal Hijriyah:* {hijri_day} {hijri_month}\n\n"
        f"🕌 Rasulullah ﷺ bersabda:\n"
        f"_“Sebaik-baik hari untuk berbekam adalah hari ke-17, 19, dan 21 Hijriyah.”_ (HR. Tirmidzi)\n\n"
        f"💡 Jangan lewatkan kesempatan untuk menjaga kesehatan dan mengikuti sunnah Nabi ﷺ.\n"
        f"Hubungi kami untuk reservasi bekam.\n\n"
        f"_Jazakallahu khairan_ 🤲"
    )
    return msg
