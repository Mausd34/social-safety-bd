# Social Safety BD — Django API

## Setup (Windows PowerShell)

```powershell
python -m venv venv
.env\Scripts\Activate.ps1
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo
python manage.py runserver
```

If PowerShell blocks activation, use:

```powershell
venv\Scripts\activate.bat
```

Or skip activation entirely and call the interpreter directly:

```powershell
.\venv\Scripts\python.exe manage.py runserver
```

API:
- http://127.0.0.1:8000/api/health/
- http://127.0.0.1:8000/api/cities/
- http://127.0.0.1:8000/api/areas/
- http://127.0.0.1:8000/api/cases/
- http://127.0.0.1:8000/api/statistics/
- http://127.0.0.1:8000/api/upazilas/
- http://127.0.0.1:8000/api/hotels/
- http://127.0.0.1:8000/admin/

## Admin

```powershell
python manage.py createsuperuser
```

Hotels are managed at http://127.0.0.1:8000/admin/api/hotel/ — tick **Verified**
before a listing is visible publicly. Hotel reviews are moderated at
`/admin/api/hotelreview/`.

## Tests

```powershell
python manage.py test api
```

107 tests. CI runs the same command; see `../.github/workflows/ci.yml`.

## Production note
Change SECRET_KEY, DEBUG, ALLOWED_HOSTS, database configuration, CORS, file storage and authentication before deployment.
