// Minimal service worker — exists only to satisfy the browser's PWA
// installability requirement. Deliberately does not cache anything: a
// store's prices/stock change too often to risk serving stale data.
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', event => event.waitUntil(self.clients.claim()));
self.addEventListener('fetch', () => {});
