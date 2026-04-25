const CACHE = 'bl-predictor-v1'

self.addEventListener('install', () => self.skipWaiting())

self.addEventListener('activate', e => {
  // Remove any old cache versions
  e.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))
    )
  )
  self.clients.claim()
})

self.addEventListener('fetch', e => {
  const { pathname } = new URL(e.request.url)

  // API calls: always network — never serve stale prediction data
  if (pathname.startsWith('/api/')) return

  // App shell: serve from cache instantly, refresh in background
  e.respondWith(
    caches.open(CACHE).then(cache =>
      cache.match(e.request).then(cached => {
        const fresh = fetch(e.request)
          .then(res => {
            if (res.ok) cache.put(e.request, res.clone())
            return res
          })
          .catch(() => cached)
        return cached ?? fresh
      })
    )
  )
})
