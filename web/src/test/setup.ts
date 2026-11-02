import "@testing-library/jest-dom/vitest";
// The interface's words, as the app loads them: every test renders in Turkish.
import "../i18n";

import { cleanup, configure } from "@testing-library/react";
import { afterAll, afterEach, beforeAll } from "vitest";

import { server } from "./server";

// jsdom has no ResizeObserver; Radix measures its tooltips' and popovers' arrows with one. Nothing resizes in a test.
class StillResizeObserver {
  observe(): void {}
  unobserve(): void {}
  disconnect(): void {}
}
globalThis.ResizeObserver ??= StillResizeObserver;

// A busy machine can take more than the default second to answer from the mock service and render the answer.
configure({ asyncUtilTimeout: 5_000 });

beforeAll(() => server.listen({ onUnhandledFrame: "error" }));
afterEach(() => {
  cleanup();
  server.resetHandlers();
});
afterAll(() => server.close());
