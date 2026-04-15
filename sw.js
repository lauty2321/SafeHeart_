// SafeClick Service Worker - PWA Support

const CACHE_NAME = 'safeclick-v2';
const urlsToCache = [
  '/',
  '/app.html',
  '/index.html',
  '/styles.css',
  '/app.js',
  '/manifest.json'
];

// Instalacion del Service Worker
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => {
        console.log('SafeClick: Cache abierto');
        return cache.addAll(urlsToCache);
      })
      .catch((err) => {
        console.log('SafeClick: Error al cachear', err);
      })
  );
  self.skipWaiting();
});

// Activacion del Service Worker
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames.map((cacheName) => {
          if (cacheName !== CACHE_NAME) {
            console.log('SafeClick: Limpiando cache antigua:', cacheName);
            return caches.delete(cacheName);
          }
        })
      );
    })
  );
  self.clients.claim();
});

// Interceptar peticiones
self.addEventListener('fetch', (event) => {
  // No cachear peticiones API
  if (event.request.url.includes('/api/')) {
    event.respondWith(fetch(event.request));
    return;
  }
  
  event.respondWith(
    caches.match(event.request)
      .then((response) => {
        // Devolver de cache si existe
        if (response) {
          return response;
        }
        
        // Si no, buscar en la red
        return fetch(event.request).then((response) => {
          // No cachear si no es una respuesta valida
          if (!response || response.status !== 200 || response.type !== 'basic') {
            return response;
          }
          
          // Clonar la respuesta para cachearla
          const responseToCache = response.clone();
          
          caches.open(CACHE_NAME)
            .then((cache) => {
              cache.put(event.request, responseToCache);
            });
          
          return response;
        });
      })
      .catch(() => {
        // Fallback para paginas offline
        if (event.request.mode === 'navigate') {
          return caches.match('/app.html');
        }
      })
  );
});

// Manejar notificaciones push
self.addEventListener('push', (event) => {
  const options = {
    body: event.data ? event.data.text() : 'Alerta de emergencia SafeClick',
    icon: '/logo-192.png',
    badge: '/logo-192.png',
    vibrate: [200, 100, 200, 100, 200],
    tag: 'safeclick-emergency',
    requireInteraction: true,
    actions: [
      { action: 'open', title: 'Abrir App' },
      { action: 'dismiss', title: 'Cerrar' }
    ]
  };
  
  event.waitUntil(
    self.registration.showNotification('SafeClick - EMERGENCIA', options)
  );
});

// Manejar clicks en notificaciones
self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  
  if (event.action === 'open' || !event.action) {
    event.waitUntil(
      clients.openWindow('/app.html')
    );
  }
});

// Sincronizacion en background (para enviar ubicacion cuando vuelva la conexion)
self.addEventListener('sync', (event) => {
  if (event.tag === 'emergency-sync') {
    event.waitUntil(syncEmergencyData());
  }
});

async function syncEmergencyData() {
  // Intentar enviar datos pendientes al servidor
  try {
    const pendingData = await getPendingEmergencyData();
    if (pendingData.length > 0) {
      for (const data of pendingData) {
        await fetch('/api/emergency', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(data)
        });
      }
      await clearPendingEmergencyData();
    }
  } catch (error) {
    console.error('SafeClick: Error sincronizando datos', error);
  }
}

async function getPendingEmergencyData() {
  // En una implementacion real, esto leeria de IndexedDB
  return [];
}

async function clearPendingEmergencyData() {
  // En una implementacion real, esto limpiaria IndexedDB
}
