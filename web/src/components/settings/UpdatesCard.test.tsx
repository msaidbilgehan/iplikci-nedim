import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import type { UpdateState } from "../../api/types";
import { renderScreen } from "../../test/render";
import { server, UPDATE_CURRENT, UPDATE_FOUND } from "../../test/server";
import { notesParts, UpdatesCard } from "./UpdatesCard";

function answer(state: UpdateState) {
  return http.get("/api/update", () => HttpResponse.json(state));
}

describe("UpdatesCard", () => {
  it("says the running version is the newest and that new ones install by themselves", async () => {
    renderScreen(<UpdatesCard />);
    expect(await screen.findByText("Güncel")).toBeInTheDocument();
    expect(screen.getByText("0.10.0")).toBeInTheDocument();
    expect(screen.getByText("Kullandığınız sürüm en yenisi.")).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: /Kendiliğinden kur/ })).toBeChecked();
  });

  it("shows a new version with its notes and installs it when asked", async () => {
    server.use(answer(UPDATE_FOUND));
    let asked = 0;
    server.use(
      http.post("/api/update/install", () => {
        asked += 1;
        return HttpResponse.json({ queued: true, version: "0.11.0" }, { status: 202 });
      }),
    );
    const user = userEvent.setup();
    renderScreen(<UpdatesCard />);
    expect(await screen.findByText("Yeni sürüm var")).toBeInTheDocument();
    const release = screen.getByRole("region", { name: /Yeni sürüm: 0.11.0/ });
    expect(within(release).getByRole("heading", { name: "Eklenenler" })).toBeInTheDocument();
    expect(within(release).getByText("Yeni bir ekran. İki satırlık bir madde.")).toBeInTheDocument();
    expect(within(release).getByText("Kalan doğru.")).toBeInTheDocument();
    await user.click(within(release).getByRole("button", { name: "Şimdi güncelle (71,5 MB)" }));
    expect(await screen.findByText("Güncelleme başladı")).toBeInTheDocument();
    expect(asked).toBe(1);
  });

  it("leads a copy installed by hand to the release's page instead of installing", async () => {
    server.use(answer({ ...UPDATE_FOUND, automatic: false, installation: "manual" }));
    renderScreen(<UpdatesCard />);
    const link = await screen.findByRole("link", { name: "Sürümün sayfasını aç (yeni sekmede açılır)" });
    expect(link).toHaveAttribute("href", UPDATE_FOUND.available?.page);
    expect(screen.queryByRole("button", { name: /Şimdi güncelle/ })).not.toBeInTheDocument();
  });

  it("says why the last check or install failed", async () => {
    server.use(
      answer({
        ...UPDATE_CURRENT,
        check_error: "Güncelleme kaynağına ulaşılamadı: github.com adresine ulaşılamadı (URLError)",
        last: { from_version: "0.9.17", to_version: "0.10.0", at: "2026-11-11T05:01:00+00:00", ok: false, error: "yeni sürüm açılamadı", tries: 1 },
      }),
    );
    renderScreen(<UpdatesCard />);
    expect(await screen.findByText("Son denetim yapılamadı")).toBeInTheDocument();
    expect(screen.getByText(/github.com adresine ulaşılamadı/)).toBeInTheDocument();
    expect(screen.getByText("0.10.0 kurulamadı")).toBeInTheDocument();
  });

  it("tells an install under way", async () => {
    server.use(answer({ ...UPDATE_CURRENT, installing: "0.11.0" }));
    renderScreen(<UpdatesCard />);
    expect(await screen.findByText("0.11.0 kuruluyor")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Şimdi denetle" })).toBeDisabled();
  });

  it("checks now and changes the mode", async () => {
    let checks = 0;
    server.use(
      http.post("/api/update/check", () => {
        checks += 1;
        return HttpResponse.json({ queued: true, version: "" }, { status: 202 });
      }),
    );
    const user = userEvent.setup();
    renderScreen(<UpdatesCard />);
    await user.click(await screen.findByRole("button", { name: "Şimdi denetle" }));
    expect(await screen.findByText(/Yeni sürüm denetleniyor/)).toBeInTheDocument();
    expect(checks).toBe(1);
    await user.click(screen.getByRole("radio", { name: /Önce bana sor/ }));
    expect(await screen.findByText("Kaydedildi.")).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: /Önce bana sor/ })).toBeChecked();
  });
});

describe("notesParts", () => {
  it("reads the changelog's headings, list items and their wrapped lines, without marks", () => {
    expect(notesParts("### Eklenenler\n\n- Bir **yeni** [ekran](docs/x.md).\n  Devamı.\n\nSon söz.")).toEqual([
      { kind: "heading", text: "Eklenenler" },
      { kind: "item", text: "Bir yeni ekran. Devamı." },
      { kind: "text", text: "Son söz." },
    ]);
  });
});
