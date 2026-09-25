# Social Safety BD — Professional Prototype

A React + Vite prototype for a public-safety awareness platform focused on:
- Bangladesh city/area statistics
- Interactive map
- Case-status dashboard
- Privacy-aware case records
- Community reporting workflow
- Emergency resources
- Admin moderation interface

## Important
All numbers in this prototype are DEMO data. They must not be presented as real crime statistics.
Before production, connect the application to authoritative, verifiable sources and add a source + last-updated field to every published dataset. Do not publish victim identities, private addresses, phone numbers, or unverified accusations.

## Run

Requirements: Node.js 20.19+ or a current supported Node release.

```bash
npm install
npm run dev
```

Then open the URL shown by Vite (normally http://localhost:5173).

## Build

```bash
npm run build
npm run preview
```

Vite's production build creates the deployable static bundle in `dist/`.

## Routes

/                   Home
/map                Interactive Safety Map
/statistics         Analytics
/cities             City directory
/cities/<slug>      District profile
/cases              Case records
/cases/<case_id>    Case detail
/report             Community reporting
/emergency          Emergency help
/login              Login UI
/register           Registration UI
/admin              Admin UI

## Next step
## API

`src/api.js` talks to the Django backend over a relative `/api` path. In
development the Vite dev server proxies that to `http://127.0.0.1:8000`, so no
CORS setup is needed. The backend must be running or every page will render
empty — see the root `README.md` for the full setup.

## Next step

The hotel safety directory (`/api/hotels/`) is implemented on the backend but
has no client functions in `api.js` and no page. Add both, plus a route in
`App.jsx`, to finish it.
