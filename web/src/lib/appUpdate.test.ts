import { describe, expect, it, vi } from "vitest";

import { reloadOnUpdate } from "./appUpdate";

/** A page's service workers: under one already (an earlier visit installed it) or under none yet. */
function workers(underOne: boolean): ServiceWorkerContainer {
  const container = Object.assign(new EventTarget(), { controller: underOne ? {} : null });
  // Only the controller and the events are read; the rest of the container is the browser's.
  return container as unknown as ServiceWorkerContainer;
}

describe("reloadOnUpdate", () => {
  it("reloads once when a new build's worker takes over the page", () => {
    const reload = vi.fn();
    const page = workers(true);
    reloadOnUpdate(page, reload);
    page.dispatchEvent(new Event("controllerchange"));
    page.dispatchEvent(new Event("controllerchange"));
    expect(reload).toHaveBeenCalledOnce();
  });

  it("leaves a first visit alone: the page already runs the build its first worker brings", () => {
    const reload = vi.fn();
    const page = workers(false);
    reloadOnUpdate(page, reload);
    page.dispatchEvent(new Event("controllerchange"));
    expect(reload).not.toHaveBeenCalled();
  });

  it("does nothing where the browser gives no service workers", () => {
    const reload = vi.fn();
    reloadOnUpdate(undefined, reload);
    expect(reload).not.toHaveBeenCalled();
  });
});
