import calendar
from datetime import date, timedelta
from typing import List, Set, Tuple
from telegram import InlineKeyboardButton

MONTH_NAMES_ID = [
    'Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni',
    'Juli', 'Agustus', 'September', 'Oktober', 'November', 'Desember'
]

def get_next_month(year: int, month: int) -> Tuple[int, int]:
    if month == 12:
        return year + 1, 1
    return year, month + 1

def get_prev_month(year: int, month: int) -> Tuple[int, int]:
    if month == 1:
        return year - 1, 12
    return year, month - 1

def create_calendar_keyboard(year: int, month: int, available_dates: Set[date], max_date: date) -> Tuple[List[List[InlineKeyboardButton]], str]:
    cal = calendar.monthcalendar(year, month)
    today = date.today()
    
    header_text = f"📅 *{MONTH_NAMES_ID[month-1]} {year}*"
    
    kb = []
    
    day_headers = ['Sen', 'Sel', 'Rab', 'Kam', 'Jum', 'Sab', 'Min']
    header_row = [InlineKeyboardButton(day, callback_data="cal_noop") for day in day_headers]
    kb.append(header_row)
    
    for week in cal:
        week_row = []
        for i, day in enumerate(week):
            if day == 0:
                week_row.append(InlineKeyboardButton(" ", callback_data="cal_noop"))
            else:
                current_date = date(year, month, day)
                
                if current_date in available_dates:
                    label = str(day)
                    callback = f"date_{current_date.isoformat()}"
                elif current_date < today or current_date > max_date:
                    label = f"({day})"
                    callback = "cal_noop"
                else:
                    label = f"[{day}]"
                    callback = "cal_noop"
                
                week_row.append(InlineKeyboardButton(label, callback_data=callback))
        
        kb.append(week_row)
    
    nav_row = []
    if (year, month) > (today.year, today.month):
        nav_row.append(InlineKeyboardButton("◀ Sebelumnya", callback_data=f"cal_prev_{year}_{month}"))
    
    if date(year, month, 1) < max_date:
        next_year, next_month = get_next_month(year, month)
        nav_row.append(InlineKeyboardButton("Berikutnya ▶", callback_data=f"cal_next_{year}_{month}"))
    
    if nav_row:
        kb.append(nav_row)
    
    return kb, header_text
