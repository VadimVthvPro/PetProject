# app/calendar.py - Inline calendar for Telegram using inline keyboards
from datetime import date, datetime, timedelta
import calendar

# returns keyboard as list of lists for InlineKeyboardMarkup

def build_month_keyboard(year: int, month: int, prefix: str):
    cal = calendar.Calendar()
    month_days = cal.monthdayscalendar(year, month)
    kb = []
    # week day names
    kb.append([{'text': d[:2], 'callback_data': 'noop'} for d in ['Mo','Tu','We','Th','Fr','Sa','Su']])
    for week in month_days:
        row = []
        for d in week:
            if d == 0:
                row.append({'text': ' ', 'callback_data': 'noop'})
            else:
                ds = f"{year}-{month:02d}-{d:02d}"
                row.append({'text': str(d), 'callback_data': f"{prefix}:day:{ds}"})
        kb.append(row)
    # prev / next row
    prev_month = (datetime(year, month, 1) - timedelta(days=1)).replace(day=1)
    next_month = (datetime(year, month, 28) + timedelta(days=8)).replace(day=1)
    kb.append([
        {'text': '<', 'callback_data': f"{prefix}:month:{prev_month.year}-{prev_month.month:02d}"},
        {'text': f"{calendar.month_name[month]} {year}", 'callback_data': 'noop'},
        {'text': '>', 'callback_data': f"{prefix}:month:{next_month.year}-{next_month.month:02d}"}
    ])
    return kb
