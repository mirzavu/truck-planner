# Truck HOS Planner

Full-stack assessment project for planning a truck trip, generating route guidance, and rendering daily paper log sheets under FMCSA-style hours-of-service assumptions.

## Stack

- `frontend/`: React, Vite, TypeScript, Leaflet
- `backend/`: Django JSON API

## What It Does

- Accepts current location, pickup location, dropoff location, cycle used hours, and optional trip start time
- Builds a truck route with OSRM and geocodes locations with Nominatim
- Applies core HOS assumptions:
  - property-carrying, `70h / 8 day` cycle
  - `11h` driving limit
  - `14h` duty window
  - `30 minute` break before exceeding `8h` of driving
  - `10h` off-duty reset
  - `34h` restart when the cycle is exhausted
  - fuel at least once every `1000` miles
  - `1h` pickup and `1h` dropoff service time
- Produces:
  - route map
  - stop timeline
  - turn instructions
  - rendered daily paper log sheets

## Repo Layout

- `backend/`: Django project, planner engine, API endpoint, tests
- `frontend/`: React UI, Leaflet map, SVG paper-log renderer

## Local Setup

### Backend

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
python backend/manage.py migrate
python backend/manage.py runserver
```

Runs at `http://127.0.0.1:8000`.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Runs at `http://127.0.0.1:5173`.

### Frontend Environment

Set `VITE_API_BASE_URL` if the backend is not running at the local default:

```bash
VITE_API_BASE_URL=http://127.0.0.1:8000
```

## API

### `POST /api/trips/plan`

Request body:

```json
{
  "currentLocation": "Dallas, TX",
  "pickupLocation": "Oklahoma City, OK",
  "dropoffLocation": "Denver, CO",
  "cycleUsedHours": 18,
  "startAt": "2026-04-26T08:00:00.000Z"
}
```

## Verification

Backend:

```bash
cd backend
../.venv/bin/python manage.py test planner
../.venv/bin/python manage.py check
```

Frontend:

```bash
cd frontend
npm run lint
npm run build
```

## Deployment

### Frontend on Vercel

- Root directory: `frontend`
- Build command: `npm run build`
- Output directory: `dist`
- Environment variable:
  - `VITE_API_BASE_URL=<your backend url>`

### Backend on Render

- Root directory: repo root or `backend`
- Build command:

```bash
pip install -r backend/requirements.txt
python backend/manage.py migrate
```

- Start command:

```bash
gunicorn --chdir backend config.wsgi:application
```

- Suggested environment variables:
  - `DJANGO_DEBUG=false`
  - `DJANGO_ALLOWED_HOSTS=.onrender.com,<your-render-host>`
  - `CORS_ALLOW_ALL_ORIGINS=false`
  - `CORS_ALLOWED_ORIGINS=<your-vercel-url>`

## Notes

- The backend uses public OSM services, so requests should stay light.
- Free hosting can introduce cold starts on the backend.
