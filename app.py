import os
import logging
from typing import Any, Dict, Optional

import requests
from flask import Flask, jsonify, request

from mapping import map_booking_to_columns, RESERVATION_COLUMN, COLUMN_MAP

# Configuration
LODGY_API_KEY = os.getenv("LODGY_API_KEY", "")
MONDAY_API_KEY = os.getenv("MONDAY_API_KEY", "")
MONDAY_BOARD_ID = os.getenv("MONDAY_BOARD_ID", "")
LODGY_ENDPOINT = "https://api.lodgify.com/v2/reservations/bookings"
MONDAY_ENDPOINT = "https://api.monday.com/v2"

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

def monday_graphql(query: str, variables: Dict[str, Any]) -> Dict[str, Any]:
    headers = {"Authorization": MONDAY_API_KEY}
    resp = requests.post(MONDAY_ENDPOINT, json={"query": query, "variables": variables}, headers=headers, timeout=15)
    if resp.status_code != 200:
        raise RuntimeError(f"Monday API HTTP {resp.status_code}")
    data = resp.json()
    if data.get("errors"):
        raise RuntimeError(data["errors"][0].get("message"))
    return data["data"]


def lookup_monday_item(reservation_id: str) -> Optional[str]:
    query = (
        "query($board_id: ID!, $column_id: String!, $value: String!) { "
        "items_page_by_column_values(board_id: $board_id, column_id: $column_id, column_value: $value, limit: 1) { "
        "items { id } } }"
    )
    variables = {
        "board_id": MONDAY_BOARD_ID,
        "column_id": RESERVATION_COLUMN,
        "value": reservation_id,
    }
    try:
        data = monday_graphql(query, variables)
        items = data["items_page_by_column_values"].get("items") or []
        if items:
            return items[0]["id"]
    except RuntimeError as exc:
        if "Column not found" in str(exc):
            return None
        raise
    return None


def create_monday_item(column_values: Dict[str, Any]) -> str:
    query = (
        "mutation($board_id: ID!, $item_name: String!, $column_values: JSON!) { "
        "create_item(board_id: $board_id, group_id: \"topics\", item_name: $item_name, column_values: $column_values) { id } }"
    )
    rid = column_values.get(RESERVATION_COLUMN)
    item_name = f"Reservation {rid}" if rid else "Reservation"
    variables = {
        "board_id": MONDAY_BOARD_ID,
        "item_name": item_name,
        "column_values": column_values,
    }
    data = monday_graphql(query, variables)
    return data["create_item"]["id"]


def update_monday_item(item_id: str, column_values: Dict[str, Any]) -> str:
    query = (
        "mutation($item_id: ID!, $board_id: ID!, $column_values: JSON!) { "
        "change_multiple_column_values(item_id: $item_id, board_id: $board_id, column_values: $column_values) { id } }"
    )
    variables = {
        "item_id": item_id,
        "board_id": MONDAY_BOARD_ID,
        "column_values": column_values,
    }
    data = monday_graphql(query, variables)
    return data["change_multiple_column_values"]["id"]


def upsert_booking(booking: Dict[str, Any]) -> Dict[str, Any]:
    columns = map_booking_to_columns(booking)
    reservation_id = columns.get(RESERVATION_COLUMN)
    result: Dict[str, Any] = {"reservation_id": reservation_id}
    try:
        item_id = None
        if reservation_id:
            try:
                item_id = lookup_monday_item(str(reservation_id))
            except Exception as exc:
                logging.error("Lookup failed: %s", exc)
        if item_id:
            updated_id = update_monday_item(item_id, columns)
            logging.info("Updated item %s", updated_id)
            result.update({"id": updated_id, "action": "updated"})
        else:
            new_id = create_monday_item(columns)
            logging.info("Created item %s", new_id)
            result.update({"id": new_id, "action": "created"})
    except Exception as exc:
        logging.error("Upsert error for %s: %s", reservation_id, exc)
        result.update({"error": str(exc)})
    return result


def fetch_lodgify_bookings(limit: int = 50, skip: int = 0) -> Dict[str, Any]:
    params = {"take": limit, "skip": skip}
    headers = {"X-ApiKey": LODGY_API_KEY}
    resp = requests.get(LODGY_ENDPOINT, params=params, headers=headers, timeout=15)
    if resp.status_code == 400:
        params = {"pageSize": limit, "pageNumber": skip // limit + 1}
        resp = requests.get(LODGY_ENDPOINT, params=params, headers=headers, timeout=15)
    resp.raise_for_status()
    return resp.json()


@app.route("/health")
def health() -> Any:
    return jsonify({"ok": True, "service": "lodgify-monday-sync", "board_id": MONDAY_BOARD_ID})


@app.route("/lodgify-sync-all")
def lodgify_sync_all() -> Any:
    limit = int(request.args.get("limit", 50))
    skip = int(request.args.get("skip", 0))
    debug = request.args.get("debug") == "1"

    bookings_data = fetch_lodgify_bookings(limit=limit, skip=skip)
    bookings = bookings_data.get("results") or bookings_data.get("items") or []
    logging.info("Fetched %d bookings", len(bookings))

    results = []
    errors = []
    sample_raw = None
    sample_mapped = None

    for idx, booking in enumerate(bookings):
        res = upsert_booking(booking)
        results.append(res)
        if res.get("error"):
            errors.append(res)
        if debug and sample_raw is None:
            sample_raw = booking
            sample_mapped = map_booking_to_columns(booking)

    response: Dict[str, Any] = {"ok": True, "count": len(results), "results": results}
    if errors:
        response["errors"] = errors
    if debug:
        response["sample"] = {"raw": sample_raw, "mapped": sample_mapped}
    return jsonify(response)


@app.route("/webhook/lodgify", methods=["POST"])
def webhook_lodgify() -> Any:
    payload = request.get_json(force=True, silent=True) or {}
    booking = payload.get("booking") if isinstance(payload, dict) else None
    if not booking:
        booking = payload
    result = upsert_booking(booking)
    return jsonify({"ok": True, "result": result})


@app.errorhandler(Exception)
def handle_exception(e: Exception):
    logging.exception("Unhandled error: %s", e)
    return jsonify({"ok": False, "error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")))
