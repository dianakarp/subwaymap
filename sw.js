// Service worker: keeps the whole map available offline.
//
// The app shell (page, manifest, icons) and the map images live in separate
// caches, so a code change doesn't re-download the map, and a new MTA map
// doesn't need a code change.
//  - Changed index.html, manifest.json or the icons? Bump SHELL_VERSION so
//    installed phones refresh right away. (They also pick it up on their own,
//    one launch later.)
//  - MAP_VERSION and MAP_SIZE are rewritten by tools/build_map.py whenever the
//    MTA publishes a new map; don't edit them by hand.

const SHELL_VERSION = 9;
const MAP_VERSION = '2026-11-19-3e30716d'; // @map-version: written by tools/build_map.py
const MAP_SIZE = {"w": 8000, "h": 9739, "levels": [{"z": 1, "w": 4000, "h": 4870}, {"z": 2, "w": 8000, "h": 9739}]}; // @map-size: written by tools/build_map.py

const PREFIX = 'subwaymap-';
const SHELL_CACHE = PREFIX + 'shell-' + SHELL_VERSION;
const MAP_CACHE = PREFIX + 'map-' + MAP_VERSION;
const LEGACY_CACHE = /^subway-map-v\d+$/; // from before the site moved to /subwaymap/

const TILE = 1024;
const SHELL_FILES = ['./index.html', './manifest.json', './icon-180.png', './icon-512.png'];
const MAP_FILES = ['./base.png', './base-night.png'];
['./tiles', './tiles-night'].forEach(function (dir) {
  MAP_SIZE.levels.forEach(function (lev) {
    const cols = Math.ceil(lev.w / TILE), rows = Math.ceil(lev.h / TILE);
    for (let x = 0; x < cols; x++) {
      for (let y = 0; y < rows; y++) {
        MAP_FILES.push(dir + '/' + lev.z + '/' + x + '_' + y + '.png');
      }
    }
  });
});

const SCOPE = new URL(self.registration.scope).pathname;            // e.g. /subwaymap/
const SHELL_PATHS = SHELL_FILES.map(function (f) { return new URL(f, self.registration.scope).pathname; });

// Fetch past the browser's HTTP cache (GitHub Pages lets browsers reuse files
// for 10 minutes, which could mix old and new tiles), retrying on a flaky
// connection.
function fetchFresh(url, tries) {
  return fetch(url, { cache: 'no-cache' }).then(function (res) {
    if (!res.ok) throw new Error(url + ': HTTP ' + res.status);
    return res;
  }).catch(function (err) {
    if (tries <= 1) throw err;
    return new Promise(function (resolve) { setTimeout(resolve, 1500); })
      .then(function () { return fetchFresh(url, tries - 1); });
  });
}

// Download the given files into the named cache, 6 at a time. With
// skipCached, files already in that cache are kept (the map cache is named
// after the map version, so anything in it is current).
function fillCache(cacheName, urls, skipCached) {
  return caches.open(cacheName).then(function (cache) {
    let next = 0;
    function worker() {
      if (next >= urls.length) return Promise.resolve();
      const url = urls[next++];
      return (skipCached ? cache.match(url) : Promise.resolve(null)).then(function (hit) {
        if (hit) return;
        return fetchFresh(url, 3).then(function (res) { return cache.put(url, res); });
      }).then(worker);
    }
    const workers = [];
    for (let i = 0; i < 6; i++) workers.push(worker());
    return Promise.all(workers);
  });
}

self.addEventListener('install', function (event) {
  event.waitUntil(
    fillCache(SHELL_CACHE, SHELL_FILES, false)
      .then(function () { return fillCache(MAP_CACHE, MAP_FILES, true); })
      .then(function () { return self.skipWaiting(); })
  );
});

self.addEventListener('activate', function (event) {
  event.waitUntil(
    caches.keys().then(function (keys) {
      // Only touch this app's caches: other sites on the same github.io
      // domain share this storage.
      return Promise.all(keys.filter(function (key) {
        return (key.indexOf(PREFIX) === 0 && key !== SHELL_CACHE && key !== MAP_CACHE) || LEGACY_CACHE.test(key);
      }).map(function (key) { return caches.delete(key); }));
    }).then(function () { return self.clients.claim(); })
  );
});

// Shell files: answer from the cache right away, then refresh the cached copy
// in the background so edits show up on the next launch.
function fromShell(event, file) {
  return caches.open(SHELL_CACHE).then(function (cache) {
    return cache.match(file).then(function (hit) {
      const refresh = fetch(file, { cache: 'no-cache' }).then(function (res) {
        if (res.ok) return cache.put(file, res.clone()).then(function () { return res; });
        return res;
      });
      if (hit) {
        event.waitUntil(refresh.catch(function () { /* offline: keep the cached copy */ }));
        return hit;
      }
      return refresh;
    });
  });
}

self.addEventListener('fetch', function (event) {
  const req = event.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  if (url.origin !== self.location.origin || url.pathname.indexOf(SCOPE) !== 0) return;

  if (url.pathname === SCOPE || url.pathname === SCOPE + 'index.html') {
    event.respondWith(fromShell(event, './index.html'));
  } else if (SHELL_PATHS.indexOf(url.pathname) !== -1) {
    event.respondWith(fromShell(event, url.pathname));
  } else {
    // Map images: cache first, network as a fallback.
    event.respondWith(
      caches.open(MAP_CACHE)
        .then(function (cache) { return cache.match(req, { ignoreSearch: true }); })
        .then(function (hit) { return hit || fetch(req); })
    );
  }
});
