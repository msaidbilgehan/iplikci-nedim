// The app's offline worker (vite-plugin-pwa, autoUpdate) takes over as soon as a new build is installed: it skips
// waiting and claims the open pages. A page still runs the build it was loaded with, though, so the first visit after
// an update showed the old interface until the next reload. One reload as the new worker takes control shows the new
// one. A first install has no worker before it: the page already runs the build the worker brings, nothing reloads.

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
