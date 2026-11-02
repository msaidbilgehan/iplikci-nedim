// The computer's colour scheme as a test sets it: jsdom has no matchMedia, so a test that cares installs this one and
// calls vi.unstubAllGlobals() afterwards.

import { vi } from "vitest";

type Listener = (event: MediaQueryListEvent) => void;

export interface SystemScheme {
  /** The computer turns dark or light, as when the user changes it in the system's settings. */
  set: (dark: boolean) => void;
}

export function stubSystemScheme(dark: boolean): SystemScheme {
  let matches = dark;
  const listeners = new Set<Listener>();
  const query = {
    media: "(prefers-color-scheme: dark)",
    get matches() {
      return matches;
    },
    addEventListener: (_type: string, listener: Listener) => listeners.add(listener),
    removeEventListener: (_type: string, listener: Listener) => listeners.delete(listener),
  };
  vi.stubGlobal("matchMedia", () => query);
  return {
    set: (next) => {
      matches = next;
      for (const listener of listeners) {
        listener({ matches } as MediaQueryListEvent);
      }
    },
  };
}
