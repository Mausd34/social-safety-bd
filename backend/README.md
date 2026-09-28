# Social Safety BD — Django API

## Setup (Windows PowerShell)

```powershell
python -m venv venv
.env\Scripts\Activate.ps1
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo
python manage.py seed_journal
python manage.py seed_district_photos
python manage.py runserver
```

`seed_demo` loads all 64 districts, demo cases, and 14 fictional hotels with
placeholder photos and moderated reviews. Use `seed_demo --reset` to rebuild
from scratch; it is safe to re-run either way.

`seed_journal` adds the citizen-journal demo content (5 posts, 3 comments,
likes, a share, a pending journalist application and a moderation report). It
is separate from `seed_demo` so you can rebuild one without the other, and
takes `--reset` too.

`seed_district_photos` generates one illustrative image per district into
`media/district-photos/`. These are **generated artwork, not photographs** — a
stock photo captioned "Sylhet" would imply it depicts Sylhet, which is the kind
of claim this project avoids. Each card's colour comes from a stable hash of
the district slug and its pin from the real latitude and longitude, so the set
looks varied and geographically sensible. Use `--force` to rebuild, or
`--only <slug>` for a single district. Images are written to `media/`, which is
gitignored, so run this once after cloning.

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
- http://127.0.0.1:8000/api/journal/posts/
- http://127.0.0.1:8000/api/journal/feed/
- http://127.0.0.1:8000/api/journal/posts/trending/
- http://127.0.0.1:8000/api/journal/stats/
- http://127.0.0.1:8000/admin/

## Admin

```powershell
python manage.py createsuperuser
```

Hotels are managed at http://127.0.0.1:8000/admin/api/hotel/ — tick **Verified**
before a listing is visible publicly, and upload a photo to the same form. Hotel
reviews are moderated at `/admin/api/hotelreview/`.

Photos are optional. A hotel with no photo still renders, using an initial
placeholder. In development Django serves `/media/` and Vite proxies it, so
uploaded images load; production needs a real media host.

## Tests

```powershell
python manage.py test api journal
```

190 tests. CI runs the same command; see `../.github/workflows/ci.yml`.

## Production note
Change SECRET_KEY, DEBUG, ALLOWED_HOSTS, database configuration, CORS, file storage and authentication before deployment.
