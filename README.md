# NYC Subway Map

A personal, ad-free, offline NYC subway map. One zoomable map, nothing else.

**Open it:** https://dianakarp.github.io/subwaymap/

<!-- map-version -->Current map: the MTA's subway diagram dated **November 19, 2026**.<!-- /map-version -->

- **Zoom/pan**: pinch, drag (with momentum), double-tap. One-handed: double-tap and hold, then slide down to zoom in or up to zoom out. Scroll wheel or +/− keys on desktop (0 shows the whole map).
- **Day / late-night toggle**: the moon button (top right) switches to the official MTA Late Nights map (~11 PM–5 AM service). It keeps your position and remembers your choice.
- **Picks up where you left off**: reopening the app returns to the same spot and zoom.
- **Offline**: a service worker caches everything on first load, so both maps work underground with no signal.
- **Install on iPhone**: open the site in Safari → Share → Add to Home Screen.

## Keeping the map current

The **Update subway map** GitHub Action (`.github/workflows/update-map.yml`) checks the MTA's maps every Monday. When the MTA has published a new edition, it downloads the PDFs, rebuilds the images, commits them and republishes the site. Installed phones get the new map the next time they open the app with a connection.

- **Update right now:** Actions → Update subway map → Run workflow. Tick "force" to rebuild even if the MTA map hasn't changed.
- **Update by hand:** replace `mta-subway-map.pdf` / `mta-subway-map-night.pdf`, then run `pip install -r tools/requirements.txt` and `python tools/build_map.py --no-download`, and commit.

## How the map is stored

The maps are tiled like a real map app, so phones never decode one giant image:

- `base.png` / `base-night.png` — 2000px overviews, always visible.
- `tiles/1/`, `tiles-night/1/` — each map at 4000px wide, cut into 1024px tiles (mid zoom).
- `tiles/2/`, `tiles-night/2/` — each map at 8000px wide, cut into 1024px tiles (deep zoom).

The page loads only the tiles visible at the current zoom, for the active map. Images are 256-colour PNGs, which look the same as full colour on this map at about half the size. Sources: `mta-subway-map.pdf` (day) and `mta-subway-map-night.pdf` (late nights), from [mta.info/maps](https://www.mta.info/maps).

`tools/build_map.py` writes `MAP_VERSION` and `MAP_SIZE` in `sw.js` and `index.html`; don't edit those by hand. If you change `index.html`, `manifest.json` or the icons, bump `SHELL_VERSION` in `sw.js` so installed phones refresh right away (otherwise they pick it up one launch later).

## Local preview

Run `serve.ps1` (PowerShell) or `python -m http.server 8420`, and open http://localhost:8420.

---

Subway map © Metropolitan Transportation Authority, used for personal reference. Not affiliated with the MTA.
