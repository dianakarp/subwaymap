# NYC Subway Map

A personal, ad-free, offline NYC subway map. One zoomable map, nothing else.

- **Zoom/pan**: pinch, drag, double-tap. Scroll wheel on desktop.
- **Offline**: a service worker caches everything on first load, so the map works underground with no signal.
- **Install on iPhone**: open the site in Safari → Share → Add to Home Screen.

## Updating the map

When the MTA publishes a new map:

1. Replace `map.png` (render the new PDF at ~4000px wide; `mta-subway-map.pdf` is the current source).
2. Bump `CACHE_NAME` in `sw.js` (e.g. `subway-map-v4` → `subway-map-v5`).
3. Commit and push. Installed phones pick up the new map automatically next time they open the app with a connection.

## Local preview

Run `serve.ps1` (PowerShell) and open http://localhost:8420.

---

Subway map © Metropolitan Transportation Authority, used for personal reference. Not affiliated with the MTA.
