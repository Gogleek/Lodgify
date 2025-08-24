import re
from datetime import datetime
from typing import Any, Dict, Optional

STATUS_MAP = {
    "confirmed": "Confirmed",
    "booked": "Confirmed",
    "pending": "Pending",
    "paid": "Paid",
    "cancelled": "Cancelled",
    "canceled": "Cancelled",
}

RESERVATION_COLUMN = "text_mkv47vb1"
COLUMN_MAP = {
    "unit": "text_mkv49eqm",
    "email": "email_mkv4mbte",
    "phone": "phone_mkv4yk8k",
    "check_in": "date_mkv4npgx",
    "check_out": "date_mkv46w1t",
    "total": "numeric_mkv4n3qy",
    "currency": "text_mkv497t1",
    "status": "color_mkv4zrs6",
}


def _first(d: Dict[str, Any], *keys: str) -> Optional[Any]:
    for k in keys:
        if isinstance(d, dict) and d.get(k) not in (None, ""):
            return d.get(k)
    return None


def normalize_phone(phone: str) -> Optional[str]:
    if not phone:
        return None
    phone = re.sub(r"[^\d+]", "", phone)
    if phone.startswith("00"):
        phone = "+" + phone[2:]
    if not phone.startswith("+"):
        return None
    return phone if len(phone) > 4 else None


def parse_date(value: str) -> Optional[str]:
    if not value:
        return None
    value = value.split("T")[0]
    try:
        dt = datetime.strptime(value, "%Y-%m-%d")
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        return None


def map_booking_to_columns(booking: Dict[str, Any]) -> Dict[str, Any]:
    guest = booking.get("guest") or booking.get("customer") or {}
    price = booking.get("price") or {}

    reservation_id = _first(booking, "reservation_id", "id", "reservationId")
    unit = _first(booking, "unit", "unit_name", "unitName", "rental_name")
    email = _first(guest, "email")
    phone = normalize_phone(_first(guest, "phone", "telephone", "mobile"))
    check_in = parse_date(_first(booking, "check_in", "arrival", "checkIn", "stayArrival"))
    check_out = parse_date(_first(booking, "check_out", "departure", "checkOut", "stayDeparture"))
    total = _first(booking, "total", "total_amount", "totalAmount", "price_total") or price.get("total")
    currency = _first(booking, "currency", "currency_code") or price.get("currency")
    status_raw = str(_first(booking, "status") or "").lower()
    status = STATUS_MAP.get(status_raw, "Pending")

    columns: Dict[str, Any] = {}
    if reservation_id:
        columns[RESERVATION_COLUMN] = str(reservation_id)
    if unit:
        columns[COLUMN_MAP["unit"]] = unit
    if email:
        columns[COLUMN_MAP["email"]] = {"email": email, "text": email}
    if phone:
        columns[COLUMN_MAP["phone"]] = {"phone": phone}
    if check_in:
        columns[COLUMN_MAP["check_in"]] = {"date": check_in}
    if check_out:
        columns[COLUMN_MAP["check_out"]] = {"date": check_out}
    try:
        if total is not None:
            columns[COLUMN_MAP["total"]] = float(total)
    except (TypeError, ValueError):
        pass
    if currency:
        columns[COLUMN_MAP["currency"]] = currency
    if status:
        columns[COLUMN_MAP["status"]] = {"label": status}
    return columns
