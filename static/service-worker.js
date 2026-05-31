/**
 * Quant AI Dashboard — Service Worker
 *
 * Strateji:
 *   - PWA shell (HTML/CSS/JS/icons/manifest) cache-first (offline destegi).
 *   - Streamlit dashboard (her zaman canli, network-only) cache'lenmez.
 *   - Offline durumunda PWA shell yine de acilir, dashboard'a baglanmayi dener.
 *
 * Web Push:
 *   - LAN modunda calismaz (HTTPS sart). Streamlit Cloud / Cloudflare Tunnel
 *     ile HTTPS'e gecince push subscription aktiflesir.
 *   - Bu sirada Telegram push birincil kanal olarak kalir.
 */

const CACHE_NAME = 'quant-ai-v1';
const PWA_SHELL_FILES = [
  '/',
  '/index.html',
  '/manifest.webmanifest',
  '/icons/icon-192.png',
  '/icons/icon-512.png',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(PWA_SHELL_FILES).catch((err) => {
        console.warn('SW install: bazi dosyalar cache\'lenemedi:', err);
      });
    })
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((names) =>
      Promise.all(
        names.filter((n) => n !== CACHE_NAME).map((n) => caches.delete(n))
      )
    )
  );
  self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  const req = event.request;
  const url = new URL(req.url);

  if (url.port === '8501' || req.url.includes(':8501/')) {
    return;
  }

  if (req.method !== 'GET') return;
  if (!url.protocol.startsWith('http')) return;

  event.respondWith(
    caches.match(req).then((cached) => {
      if (cached) return cached;
      return fetch(req)
        .then((res) => {
          if (res && res.status === 200 && res.type === 'basic') {
            const clone = res.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(req, clone));
          }
          return res;
        })
        .catch(() => {
          if (req.mode === 'navigate') {
            return caches.match('/index.html');
          }
        });
    })
  );
});

self.addEventListener('push', (event) => {
  let data = { title: 'Quant AI', body: 'Yeni olay var', tag: 'quant-ai' };
  if (event.data) {
    try { data = event.data.json(); }
    catch (e) { data.body = event.data.text(); }
  }
  const options = {
    body: data.body || 'Yeni olay',
    icon: '/icons/icon-192.png',
    badge: '/icons/icon-192.png',
    vibrate: [120, 60, 120],
    tag: data.tag || 'quant-ai',
    requireInteraction: data.severity === 'critical',
    data: { url: data.url || '/' },
  };
  event.waitUntil(self.registration.showNotification(data.title || 'Quant AI', options));
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const targetUrl = (event.notification.data && event.notification.data.url) || '/';
  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then((all) => {
      for (const client of all) {
        if (client.url.includes(targetUrl) && 'focus' in client) return client.focus();
      }
      if (clients.openWindow) return clients.openWindow(targetUrl);
    })
  );
});

self.addEventListener('message', (event) => {
  if (event.data && event.data.type === 'SKIP_WAITING') self.skipWaiting();
});
