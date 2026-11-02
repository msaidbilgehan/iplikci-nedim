import { waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { afterEach, describe, expect, it } from "vitest";

import { renderScreen, type ScreenResult } from "../../test/render";
import { server, SETUP } from "../../test/server";
import { Layout } from "../Layout";

afterEach(() => sessionStorage.clear());

function firstRun(on: boolean) {
  server.use(http.get("/api/setup", () => HttpResponse.json({ ...SETUP, first_run: on })));
}

/** The setup's answer has arrived, and what the screen does with it is done. */
async function answered(screen: ScreenResult): Promise<void> {
  await waitFor(() => expect(screen.client.getQueryState(["system", "setup"])?.status).toBe("success"));
}

describe("useFirstRun", () => {
  it("opens the setup wizard instead of the home page when nothing is set up yet", async () => {
    firstRun(true);
    const { location } = renderScreen(<Layout />, { path: "/" });
    await waitFor(() => expect(location()).toBe("/kurulum"));
  });

  it("does so once a session: the home page stays the home page after that", async () => {
    firstRun(true);
    sessionStorage.setItem("iplikci.kurulum", "1");
    const screen = renderScreen(<Layout />, { path: "/" });
    await answered(screen);
    expect(screen.location()).toBe("/");
  });

  it("leaves another screen where it is", async () => {
    firstRun(true);
    const screen = renderScreen(<Layout />, { path: "/islemler" });
    await answered(screen);
    expect(screen.location()).toBe("/islemler");
  });

  it("leaves the home page of a computer that is set up", async () => {
    firstRun(false);
    const screen = renderScreen(<Layout />, { path: "/" });
    await answered(screen);
    expect(screen.location()).toBe("/");
  });
});
