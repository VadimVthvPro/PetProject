from app.calendar import build_month_keyboard

def test_calendar_keyboard():
    kb = build_month_keyboard(2025,8,'startcal')
    assert isinstance(kb, list)
    # header row + weeks + nav row
    assert len(kb) >= 5
