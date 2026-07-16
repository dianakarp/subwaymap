# NYC Subway Map

A personal, ad-free, offline NYC subway map. One zoomable map, nothing else.

- **Zoom/pan**: pinch, drag, double-tap. Scroll wheel on desktop.
- **Day / late-night toggle**: the moon button (top right) switches to the official MTA Late Nights map (~11 PM–5 AM service). It keeps your position and remembers your choice.
- **Offline**: a service worker caches everything on first load, so both maps work underground with no signal.
- **Install on iPhone**: open the site in Safari → Share → Add to Home Screen.

## How the map is stored

The maps are tiled like a real map app, so phones never decode one giant image:

- `base.png` / `base-night.png` — 2000px overviews, always visible.
- `tiles/1/`, `tiles-night/1/` — each map at 4000px wide, cut into 1024px tiles (mid zoom).
- `tiles/2/`, `tiles-night/2/` — each map at 8000px wide, cut into 1024px tiles (deep zoom).

The page loads only the tiles visible at the current zoom, for the active map. Sources: `mta-subway-map.pdf` (day) and `mta-subway-map-night.pdf` (late nights).

## Updating the map

When the MTA publishes a new map:

1. Render the new PDF at 8000px wide (`mta-subway-map.pdf` is the current source), then regenerate `base.png` and the `tiles/` folders (1024px grid at 8000 and 4000 wide — ask Claude, or see git history for the PowerShell script).
2. If the rendered size changes, update `WORLD_W`/`WORLD_H`/`LEVELS` in `index.html` and `LEVELS` in `sw.js`.
3. Bump `CACHE_NAME` in `sw.js` (e.g. `subway-map-v6` → `subway-map-v7`).
4. Commit and push. Installed phones pick up the new map automatically next time they open the app with a connection.

## Local preview

Run `serve.ps1` (PowerShell) and open http://localhost:8420.

---

Subway map © Metropolitan Transportation Authority, used for personal reference. Not affiliated with the MTA.
