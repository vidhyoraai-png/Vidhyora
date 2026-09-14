// Minimal service worker — exists only to satisfy the browser's PWA
// installability requirement. Deliberately does not cache anything: a
// AI responses and account state should never be served from a stale cache.
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', event => event.waitUntil(self.clients.claim()));
self.addEventListener('fetch', () => {});
