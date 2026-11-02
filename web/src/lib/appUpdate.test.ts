import { describe, expect, it, vi } from "vitest";

import { checkOnReturn, reloadOnUpdate } from "./appUpdate";

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

/** A page whose visibility a test sets, and the workers' registration whose update checks it counts. */
function shown() {
  const page = Object.assign(new EventTarget(), { visibilityState: "visible" as DocumentVisibilityState });
  const update = vi.fn(() => Promise.resolve());
  const container = { getRegistration: () => Promise.resolve({ update }) };
  const show = (state: DocumentVisibilityState) => {
    page.visibilityState = state;
    page.dispatchEvent(new Event("visibilitychange"));
  };
  // Only the visibility and the registration are read; the rest is the browser's.
  return { page: page as unknown as Document, workers: container as unknown as ServiceWorkerContainer, update, show };
}

describe("checkOnReturn", () => {
  it("asks for a new build when the page is shown again a minute or more after the last time", async () => {
    let clock = 0;
    const { page, workers, update, show } = shown();
    checkOnReturn(workers, page, () => clock);
    clock = 61_000;
    show("hidden");
    show("visible");
    await vi.waitFor(() => expect(update).toHaveBeenCalledOnce());
  });

  it("asks at most once a minute however often the tab comes back", async () => {
    let clock = 0;
    const { page, workers, update, show } = shown();
    checkOnReturn(workers, page, () => clock);
    clock = 61_000;
    show("visible");
    clock = 90_000;
    show("visible");
    await vi.waitFor(() => expect(update).toHaveBeenCalledOnce());
    clock = 122_000;
    show("visible");
    await vi.waitFor(() => expect(update).toHaveBeenCalledTimes(2));
  });

  it("does not ask while the page is hidden", () => {
    let clock = 0;
    const { page, workers, update, show } = shown();
    checkOnReturn(workers, page, () => clock);
    clock = 61_000;
    show("hidden");
    expect(update).not.toHaveBeenCalled();
  });
});
