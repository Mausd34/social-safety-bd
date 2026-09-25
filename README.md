# Social Safety BD 🇧🇩

A professional public-safety awareness and verified-statistics prototype for Bangladesh.

## Stack
- **Frontend:** React, Vite, React Router, Leaflet, Recharts
- **Backend:** Django + Django REST Framework
- **Database:** SQLite for development
- **Authentication:** Django session authentication
- **Uploads:** Django media storage

## Features
- Responsive public safety dashboard
- All 64 districts of Bangladesh with real map coordinates, division grouping and area-level statistics
- Interactive safety map
- Verified case directory and case details
- Search and filtering support
- User registration, login, logout and current-user API
- Community safety report submission with optional evidence
- Staff-only report review API
- Admin management for cities, areas, cases and reports
- Environment-based CORS, hosts and secret configuration

## Local setup

### Backend — Windows PowerShell
```powershell
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo --reset
python manage.py runserver
```

If PowerShell blocks activation, run the commands without activation using `venv\Scripts\python.exe`.

### Frontend
Open a second terminal:
```bash
cd frontend
npm install
npm run dev
```

The frontend calls `/api` as a **relative path**. In development the Vite dev
server proxies `/api` to `http://127.0.0.1:8000`, so the browser only ever
talks to one origin and CORS is never involved.

To point the dev proxy at a different backend, set `VITE_BACKEND_URL`. To send
requests to an absolute API host instead, set `VITE_API_URL`. Both are shown in
`frontend/.env.example`.

## API
- `GET /api/health/`
- `POST /api/register/`
- `POST /api/login/`
- `GET /api/me/`
- `POST /api/logout/`
- `GET /api/cities/`
- `GET /api/areas/?city=dhaka`
- `GET /api/cases/`
- `GET /api/cases/<case_id>/`
- `GET /api/statistics/`
- `GET /api/dashboard/`
- `POST /api/reports/`
- `GET/PATCH /api/admin/reports/` — staff only

## Production configuration
Set these environment variables on the backend:
```text
DJANGO_SECRET_KEY=<strong-random-secret>
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=<your-backend-domain>
CORS_ALLOWED_ORIGINS=https://<your-frontend-domain>
```

Run production static collection with:
```bash
python manage.py collectstatic --noinput
```
Use a production WSGI server such as Gunicorn and a persistent database/storage service for real deployment.

## Demo-data warning
`seed_demo` loads **all 64 districts** of Bangladesh (8 divisions) with real names, coordinates and population, plus real thanas/upazilas for the largest districts, synthetic area/case records, and synthetic city-level statistics.

**Every statistic produced is fabricated for UI development.** The numbers are
derived from a stable hash of each district name so that repeated seeding is
idempotent, and they are scaled by population only to keep the demo visually
plausible. They are not measurements. Each seeded case is tagged
`SYNTHETIC demo record - fabricated for prototyping, not real data` and the UI
shows a persistent banner, so synthetic figures cannot be mistaken for real ones.

Use `--reset` to clear existing cities/areas/cases before seeding. Without it the
command is safe to re-run and will update rows in place.

Replace all synthetic values with authoritative, verifiable data before
publication. Case records exposed publicly are limited to verified records.

## Responsible-data policy
Do not publish victim identities, private addresses, phone numbers, or other sensitive personal information. Do not publish unverified accusations or label a person a criminal based only on a complaint. Public case information should be based on lawful, authoritative sources and clearly show verification/source metadata.
