const CACHE_NAME = 'gutenberg-audio-v1';
const urlsToCache = [
  '/',
  '/static/style.css',
  '/static/icons/icon-192.png',
  '/static/icons/icon-512.png',
  '/static/favicon.ico'
];

// Install and cache shell
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => cache.addAll(urlsToCache))
  );
});

// Serve cached content when offline
self.addEventListener('fetch', (event) => {
  event.respondWith(
    caches.match(event.request).then(response => response || fetch(event.request))
  );
});

