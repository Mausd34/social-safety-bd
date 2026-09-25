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
h

If PowerShell blocks activation, use:

```powershell
venv\Scripts\activate.bat
```

API:
- http://127.0.0.1:8000/api/cities/
- http://127.0.0.1:8000/api/areas/
- http://127.0.0.1:8000/api/cases/
- http://127.0.0.1:8000/admin/

## Admin

```powershell
python manage.py createsuperuser
```

## Production note
Change SECRET_KEY, DEBUG, ALLOWED_HOSTS, database configuration, CORS, file storage and authentication before deployment.
