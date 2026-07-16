// Bump this version string whenever any file changes (especially the map
// tiles) so installed phones pick up the update next time they're online.
const CACHE_NAME = 'subway-map-v8';

const TILE = 1024;
const LEVELS = [
  { z: 1, w: 4000, h: 4870 },
  { z: 2, w: 8000, h: 9739 }
];
const TILE_DIRS = ['./tiles', './tiles-night'];

const ASSETS = [
  './',
  './index.html',
  './manifest.json',
  './base.png',
  './base-night.png',
  './icon-180.png',
  './icon-512.png'
];
TILE_DIRS.forEach(function (dir) {
  LEVELS.forEach(function (lev) {
    const cols = Math.ceil(lev.w / TILE), rows = Math.ceil(lev.h / TILE);
    for (let x = 0; x < cols; x++) {
      for (let y = 0; y < rows; y++) {
        ASSETS.push(dir + '/' + lev.z + '/' + x + '_' + y + '.png');
      }
    }
  });
});

self.addEventListener('install', function (event) {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(function (cache) { return cache.addAll(ASSETS); })
      .then(function () { return self.skipWaiting(); })
  );
});

self.addEventListener('activate', function (event) {
  event.waitUntil(
    caches.keys().then(function (keys) {
      return Promise.all(
        keys.filter(function (k) { return k !== CACHE_NAME; })
            .map(function (k) { return caches.delete(k); })
      );
    }).then(function () { return self.clients.claim(); })
  );
});

self.addEventListener('fetch', function (event) {
  event.respondWith(
    caches.match(event.request, { ignoreSearch: true }).then(function (cached) {
      return cached || fetch(event.request);
    })
  );
});
