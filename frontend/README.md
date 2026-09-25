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
/cities/dhaka       Dhaka profile
/cities/dhaka/uttara Uttara profile
/cases              Case records
/report             Community reporting
/emergency          Emergency help
/login              Login UI
/register           Registration UI
/admin              Admin UI

## Next step
Replace `src/data.js` with API calls to the Django backend in the project root.
