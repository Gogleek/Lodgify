import os
os.environ.setdefault("MONDAY_BOARD_ID", "1")

from mapping import map_booking_to_columns, RESERVATION_COLUMN, COLUMN_MAP


def test_map_booking_to_columns_basic():
    booking = {
        "id": "ABC123",
        "unit": "Unit 7",
        "status": "confirmed",
        "check_in": "2024-08-01",
        "check_out": "2024-08-05",
        "total": "123.45",
        "currency": "USD",
        "guest": {"email": "test@example.com", "phone": "+1 (555) 000-1111"},
    }
    cols = map_booking_to_columns(booking)
    assert cols[RESERVATION_COLUMN] == "ABC123"
    assert cols[COLUMN_MAP["unit"]] == "Unit 7"
    assert cols[COLUMN_MAP["email"]] == {"email": "test@example.com", "text": "test@example.com"}
    assert cols[COLUMN_MAP["phone"]] == {"phone": "+15550001111"}
    assert cols[COLUMN_MAP["check_in"]] == {"date": "2024-08-01"}
    assert cols[COLUMN_MAP["total"]] == 123.45
    assert cols[COLUMN_MAP["currency"]] == "USD"
    assert cols[COLUMN_MAP["status"]] == {"label": "Confirmed"}


def test_map_booking_to_columns_edge_cases():
    booking = {
        "reservation_id": "XYZ",
        "check_in": "2024-09-01T15:00:00Z",
        "total": "abc",
        "status": "unknown",
        "guest": {"email": "", "phone": "12345"},
    }
    cols = map_booking_to_columns(booking)
    assert cols[RESERVATION_COLUMN] == "XYZ"
    # ISO datetime should be truncated to date
    assert cols[COLUMN_MAP["check_in"]] == {"date": "2024-09-01"}
    # invalid phone and empty email should be omitted
    assert COLUMN_MAP["phone"] not in cols
    assert COLUMN_MAP["email"] not in cols
    # non-numeric total should be ignored
    assert COLUMN_MAP["total"] not in cols
    # unknown status should fall back to Pending
    assert cols[COLUMN_MAP["status"]] == {"label": "Pending"}
