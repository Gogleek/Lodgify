# Lodgify Monday Sync Service

Simple Flask service that syncs Lodgify reservations with a Monday.com board.

## Endpoints

- `GET /health` – health check.
- `GET /lodgify-sync-all?limit=&skip=&debug=` – pull Lodgify bookings and upsert to Monday.
- `POST /webhook/lodgify` – receive a Lodgify booking webhook and upsert to Monday.

Environment variables:

- `LODGY_API_KEY` – API key for Lodgify.
- `MONDAY_API_KEY` – API key for Monday.com.
- `MONDAY_BOARD_ID` – target Monday board ID.

Install dependencies:

```bash
pip install -r requirements.txt
```

Run the service:

```bash
python app.py
```
