# app/utils.py
from datetime import datetime

def parse_yyyy_mm_dd(text: str):
    try:
        return datetime.strptime(text.strip(), '%Y-%m-%d').date()
    except Exception:
        return None

def days_between(start, end):
    return (end - start).days + 1

def ranges_overlap(a_start, a_end, b_start, b_end) -> bool:
    """Return True if two closed date ranges overlap."""
    return (a_start <= b_end) and (a_end >= b_start)
