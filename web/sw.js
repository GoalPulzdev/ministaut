// Ministaut service worker: shows push alerts only. No caching, so the page is always fresh.
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (event) =>
  event.waitUntil(self.clients.claim()),
);
self.addEventListener("push", (event) => {
  let data = {};
  try {
    data = event.data ? event.data.json() : {};
  } catch {
    data = { body: event.data?.text() || "" };
  }
  event.waitUntil(
    self.registration.showNotification(data.title || "Ministaut", {
      body: data.body || "",
      tag: data.tag || undefined,
      data: { url: data.url || self.registration.scope },
      icon: new URL("icon-192.png", self.registration.scope).href,
      badge: new URL("icon-192.png", self.registration.scope).href,
    }),
  );
});
self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const url = new URL(
    event.notification.data?.url || self.registration.scope,
    self.registration.scope,
  ).href;
  event.waitUntil(
    self.clients
      .matchAll({ type: "window", includeUncontrolled: true })
      .then((list) => {
        for (const client of list) {
          if ("navigate" in client && "focus" in client)
            return client.navigate(url).then((c) => (c || client).focus());
        }
        return self.clients.openWindow(url);
      }),
  );
});
