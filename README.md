# Store Monitoring System by Ayush

This project is a backend system that monitors uptime and downtime for restaurant locations across the U.S. It ingests CSV data and provides API endpoints for restaurant owners to request detailed uptime/downtime reports.

---

## Features
- **Real-time monitoring** using periodic polls (status data).
- **Business hour awareness** with timezone conversion.
- **Smart interpolation** of uptime/downtime even with sparse data.
- **Report generation API** to trigger and retrieve historical analytics.

---

## Data Sources
1. `store_status.csv`: Poll data containing `store_id`, `timestamp_utc`, and `status` (active/inactive).
2. `business_hours.csv`: Operating hours in local time.
3. `store_timezones.csv`: Timezone information per store.

---

## Tech Stack
- **FastAPI** - Web framework
- **Pandas** - Data processing
- **SQLite** - Lightweight relational database
- **SQLAlchemy** - ORM

---

## Setup Instructions
```bash
git clone https://github.com/ayushtjsr/ayush_22-04-2025.git
cd store-monitoring-system

# Build and run


# App runs at http://localhost:3000
```

---

## API Endpoints
### `POST /trigger_report`
Triggers report generation.
Returns:
```json
{ "report_id": "some-uuid" }
```

### `GET /get_report?report_id=...`
Fetch report status or CSV file.
Returns:
```json
{ "status": "Running" }
```
Or downloadable CSV if complete.

---

## Smart Interpolation
If a store is open 9AM–12PM and we have logs only at 10:15AM (active) and 11:15AM (inactive), we interpolate for the full business interval to estimate uptime/downtime.

---

## Sample Report Output
| store_id | uptime_last_hour | uptime_last_day | update_last_week | downtime_last_hour | downtime_last_day | downtime_last_week |
|----------|------------------|------------------|-------------------|---------------------|--------------------|---------------------|
| 111      | 45.0             | 22.3             | 120.5             | 15.0                | 1.7                | 47.5                |

---

## Ideas for Improvement
- [ ] WebSocket updates for real-time report progress.
- [ ] Data ingestion scheduler for automatic hourly ingestion.
- [ ] Admin dashboard to visualize reports.


---

## Author
**Ayush** — backend developer with a passion for clean APIs and observability systems.

---



