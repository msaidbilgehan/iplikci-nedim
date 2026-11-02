// The app's offline worker (vite-plugin-pwa, vite.config.ts) takes over as soon as a new build is installed: it skips
// waiting and claims the open pages. A page still runs the build it was loaded with, though, so it reloads once as the
// new worker takes control. A first install has no worker before it: the page already runs the build the worker
// brings, and nothing reloads.
//
// The browser looks for a new build only when a page of the app is opened, and a tab of the app may stay open for
// days: the browser extension brings it to the front instead of opening a new one. So the page also asks for one
// each time it is shown again.

const CHECK_EVERY_MS = 60_000; // switching tabs back and forth asks the service at most once a minute

/** Reloads the page once when a new worker takes over from the one the page was loaded under. */
export function reloadOnUpdate(workers: ServiceWorkerContainer | undefined, reload: () => void): void {
  if (!workers?.controller) {
    return;
  }
  let reloading = false;
  workers.addEventListener("controllerchange", () => {
    if (reloading) {
      return;
    }
    reloading = true;
    reload();
  });
}

/** Asks the browser to look for a new build when the page is shown again, at most once a minute. */
export function checkOnReturn(
  workers: ServiceWorkerContainer | undefined,
  page: Document,
  now: () => number = Date.now,
): void {
  if (!workers) {
    return;
  }
  let asked = now();
  page.addEventListener("visibilitychange", () => {
    if (page.visibilityState !== "visible" || now() - asked < CHECK_EVERY_MS) {
      return;
    }
    asked = now();
    workers
      .getRegistration()
      .then((registration) => registration?.update())
      .catch(() => {
        // the service is stopped or the session ended: nothing changes, and the next return asks again
      });
  });
}
