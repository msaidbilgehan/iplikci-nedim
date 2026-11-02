// The interface installs as an app (ADR-0008): the page names its manifest, the browser reads the manifest and its
// icons, and the service worker that keeps the app shell starts. Only the app shell: the API's answers stay out of
// its caches.

import { expect, test } from "@playwright/test";

test("arayüz uygulama olarak kurulabilir ve kabuğunu saklayan hizmet çalışanı başlar", async ({ page }) => {
  await page.goto("/sistem");
  await expect(page.getByRole("heading", { level: 1, name: "Sistem" })).toBeVisible();
  const manifest = await page.evaluate(async () => {
    const link = document.querySelector<HTMLLinkElement>('link[rel="manifest"]');
    const answer = await fetch(link?.href ?? "", { credentials: "omit" });
    return (await answer.json()) as { name: string; start_url: string; icons: { src: string }[] };
  });
  expect(manifest.name).toBe("İplikçi Nedim");
  expect(manifest.start_url).toBe("/");
  for (const icon of manifest.icons) {
    expect((await page.request.get(icon.src)).ok()).toBe(true);
  }
  const shell = await page.evaluate(async () => {
    const registration = await navigator.serviceWorker.ready;
    const cached = (await Promise.all((await caches.keys()).map(async (name) => (await caches.open(name)).keys())))
      .flat()
      .map((request) => new URL(request.url).pathname);
    return { scope: new URL(registration.scope).pathname, cached };
  });
  expect(shell.scope).toBe("/");
  expect(shell.cached).toContain("/index.html");
  expect(shell.cached.filter((path) => path.startsWith("/api/"))).toEqual([]);
});
