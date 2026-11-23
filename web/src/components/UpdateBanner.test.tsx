import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import type { UpdateState } from "../api/types";
import { renderScreen } from "../test/render";
import { server, UPDATE_CURRENT, UPDATE_FOUND } from "../test/server";
import { UpdateBanner } from "./UpdateBanner";

function answer(state: UpdateState) {
  return http.get("/api/update", () => HttpResponse.json(state));
}

describe("UpdateBanner", () => {
  it("says nothing while the running version is the newest", async () => {
    let asked = 0;
    server.use(
      http.get("/api/update", () => {
        asked += 1;
        return HttpResponse.json(UPDATE_CURRENT);
      }),
    );
    renderScreen(<UpdateBanner />);
    await answered(() => asked);
    expect(screen.queryByText(/Yeni sürüm/)).not.toBeInTheDocument();
  });

  it("asks to install the version found, folds what it brings, and says it installs once asked", async () => {
    let state: UpdateState = UPDATE_FOUND;
    let asked = 0;
    server.use(
      http.get("/api/update", () => HttpResponse.json(state)),
      http.post("/api/update/install", () => {
        asked += 1;
        state = { ...UPDATE_FOUND, installing: "0.11.0" }; // queued: under way from now on
        return HttpResponse.json({ queued: true, version: "0.11.0" }, { status: 202 });
      }),
    );
    const user = userEvent.setup();
    renderScreen(<UpdateBanner />);
    const banner = await screen.findByRole("region", { name: "Yeni sürüm hazır: 0.11.0" });
    expect(within(banner).getByText(/Kurmadan önce verilerinizin yedeği alınır/)).toBeInTheDocument();
    await user.click(within(banner).getByText("Neler yeni?"));
    expect(within(banner).getByRole("region", { name: "Neler yeni?" })).toHaveTextContent("Yeni bir ekran.");
    await user.click(within(banner).getByRole("button", { name: "Şimdi güncelle (71,5 MB)" }));
    expect(await screen.findByRole("status")).toHaveTextContent("0.11.0 kuruluyor");
    expect(asked).toBe(1);
    expect(screen.queryByRole("button", { name: /Şimdi güncelle/ })).not.toBeInTheDocument();
  });

  it("says a version installing by itself is under way, and asks nothing", async () => {
    server.use(answer({ ...UPDATE_FOUND, mode: "auto", installing: "0.11.0" }));
    renderScreen(<UpdateBanner />);
    const status = await screen.findByRole("status");
    expect(status).toHaveTextContent("0.11.0 kuruluyor");
    expect(status).toHaveTextContent("Bu sayfa birkaç saniye bağlantısız kalabilir");
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("says an install by itself did not come up, with where the reason is, and asks again", async () => {
    const at = "2026-11-20T05:01:00+00:00";
    const last = { from_version: "0.10.0", to_version: "0.11.0", at, ok: false, error: "açılamadı", tries: 2 };
    server.use(answer({ ...UPDATE_FOUND, mode: "auto", last }));
    renderScreen(<UpdateBanner />);
    const banner = await screen.findByRole("region", { name: "Yeni sürüm hazır: 0.11.0" });
    expect(within(banner).getByText(/Kendiliğinden kurulamadı/)).toBeInTheDocument();
    expect(within(banner).getByRole("link", { name: "Ayarlar'da yazıyor." })).toHaveAttribute("href", "/ayarlar");
    expect(within(banner).getByRole("button", { name: "Şimdi güncelle (71,5 MB)" })).toBeEnabled();
  });

  it("leads a copy installed by hand to the release's page", async () => {
    server.use(answer({ ...UPDATE_FOUND, automatic: false, installation: "manual" }));
    renderScreen(<UpdateBanner />);
    const banner = await screen.findByRole("region", { name: "Yeni sürüm çıktı: 0.11.0" });
    const link = within(banner).getByRole("link", { name: "Sürümün sayfasını aç (yeni sekmede açılır)" });
    expect(link).toHaveAttribute("href", UPDATE_FOUND.available?.page);
    expect(within(banner).queryByRole("button")).not.toBeInTheDocument();
  });

  it("leaves the Settings screen alone, whose card says the same", async () => {
    let asked = 0;
    server.use(
      http.get("/api/update", () => {
        asked += 1;
        return HttpResponse.json(UPDATE_FOUND);
      }),
    );
    renderScreen(<UpdateBanner />, { path: "/ayarlar" });
    await answered(() => asked);
    expect(screen.queryByRole("region", { name: /Yeni sürüm/ })).not.toBeInTheDocument();
  });
});

/** Waits until the service was asked once, and a moment more for its answer to be shown. */
async function answered(asked: () => number): Promise<void> {
  await waitFor(() => expect(asked()).toBe(1));
  await new Promise((resolve) => setTimeout(resolve, 20));
}
