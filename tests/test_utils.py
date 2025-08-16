from app.utils import parse_yyyy_mm_dd, days_between, ranges_overlap
from datetime import date

def test_parse_date():
    assert parse_yyyy_mm_dd('2025-08-13') == date(2025,8,13)
    assert parse_yyyy_mm_dd('invalid') is None

def test_days_between():
    assert days_between(date(2025,1,1), date(2025,1,1)) == 1
    assert days_between(date(2025,1,1), date(2025,1,3)) == 3

def test_ranges_overlap():
    assert ranges_overlap(date(2025,1,1), date(2025,1,5), date(2025,1,4), date(2025,1,10))
    assert not ranges_overlap(date(2025,1,1), date(2025,1,3), date(2025,1,4), date(2025,1,5))
