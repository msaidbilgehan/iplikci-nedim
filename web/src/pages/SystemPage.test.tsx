import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import { server, systemStatus } from "../test/server";
import { renderScreen } from "../test/render";
import SystemPage from "./SystemPage";

describe("SystemPage", () => {
  it("shows the service, the mail, the queue, the backups and the readers", async () => {
    renderScreen(<SystemPage />);
    const service = await screen.findByRole("region", { name: "Servis" });
    expect(within(service).getByText("0.4.0")).toBeInTheDocument();
    expect(within(service).getByText("/veri/iplikci")).toBeInTheDocument();
    expect(within(screen.getByRole("region", { name: "E-posta" })).getByText("Çalışıyor")).toBeInTheDocument();
    expect(within(screen.getByRole("region", { name: "Yedek" })).getByText("3 yedek, 10,0 MB")).toBeInTheDocument();
    expect(within(screen.getByRole("region", { name: "Belgeler" })).getByText("Okunamadı")).toBeInTheDocument();
    expect(screen.getByRole("cell", { name: "TEB hesap hareketleri" })).toBeInTheDocument();
    expect(screen.getByRole("cell", { name: "2/3" })).toBeInTheDocument();
  });

  it("shows how much of the bank mail was read or knowingly classified, and what is left", async () => {
    renderScreen(<SystemPage />);
    const card = await screen.findByRole("region", { name: "E-posta" });
    expect(within(card).getByText("E-posta kapsamı: %91", { exact: false })).toBeInTheDocument();
    expect(within(card).getByText("Hedefte")).toBeInTheDocument();
    expect(within(card).getByText("Henüz tanınmayan: 18")).toBeInTheDocument();
    expect(within(card).getByText("banka.example · Haftalık bildiriminiz (18)")).toBeInTheDocument();
  });

  it("says when the coverage is under the target", async () => {
    const coverage = { ...systemStatus().mail.coverage, unknown: 21, share: 0.895 };
    const mail = { ...systemStatus().mail, coverage };
    server.use(http.get("/api/system", () => HttpResponse.json(systemStatus({ mail }))));
    renderScreen(<SystemPage />);
    const card = await screen.findByRole("region", { name: "E-posta" });
    expect(within(card).getByText("E-posta kapsamı: %89", { exact: false })).toBeInTheDocument();
    expect(within(card).getByText("Hedefin altında")).toBeInTheDocument();
  });

  it("says a refused login stopped the mail and is never tried again", async () => {
    const mail = { ...systemStatus().mail, last_run: "", last_error: "giriş reddedildi", stopped: true };
    server.use(http.get("/api/system", () => HttpResponse.json(systemStatus({ mail }))));
    renderScreen(<SystemPage />);
    expect(await screen.findByText("Giriş reddedildi; e-posta alımı durdu")).toBeInTheDocument();
    expect(screen.getByText("Durdu")).toBeInTheDocument();
  });

  it("lists the delivered messages that were not kept, with why", async () => {
    const refused = [
      { taken: "unverified" as const, reason: "no-dmarc", domain: "banka.example", count: 12, label: "DMARC yok" },
      { taken: "unlisted" as const, reason: "", domain: "", count: 3, label: "gönderen hiçbir listede değil" },
    ];
    const mail = { ...systemStatus().mail, connector: "browser_bridge" as const, refused };
    server.use(http.get("/api/system", () => HttpResponse.json(systemStatus({ mail }))));
    renderScreen(<SystemPage />);
    const card = await screen.findByRole("region", { name: "E-posta" });
    expect(within(card).getByText("Alınmayan e-postalar: 15")).toBeInTheDocument();
    expect(within(card).getByText("banka.example: DMARC yok (12)")).toBeInTheDocument();
    expect(within(card).getByText("gönderen hiçbir listede değil (3)")).toBeInTheDocument();
  });

  it("tells two extensions of the same browser apart by when they paired", async () => {
    const mail = { ...systemStatus().mail, connector: "browser_bridge" as const };
    const bridges = [
      { id: "k1", name: "Chrome 140, macOS", created_at: "2026-11-01T08:00:00+00:00", last_seen: "", active: true },
      { id: "k2", name: "Chrome 140, macOS", created_at: "2026-11-02T09:30:00+00:00", last_seen: "", active: true },
      { id: "k3", name: "Edge 140, Windows", created_at: "2026-11-02T10:00:00+00:00", last_seen: "", active: true },
    ];
    server.use(
      http.get("/api/system", () => HttpResponse.json(systemStatus({ mail }))),
      http.get("/api/bridge", () => HttpResponse.json(bridges)),
    );
    renderScreen(<SystemPage />);
    const card = await screen.findByRole("region", { name: "E-posta" });
    expect(await within(card).findByText(/^Chrome 140, macOS \(eşleşme 01\.11\.2026 .+\): son/)).toBeInTheDocument();
    expect(within(card).getByText(/^Chrome 140, macOS \(eşleşme 02\.11\.2026 .+\): son/)).toBeInTheDocument();
    expect(within(card).getByText("Edge 140, Windows: son görülme henüz yok")).toBeInTheDocument();
  });

  it("says the extension has not scanned the history since the start day yet", async () => {
    const mail = { ...systemStatus().mail, connector: "browser_bridge" as const, history_due: true };
    server.use(http.get("/api/system", () => HttpResponse.json(systemStatus({ mail }))));
    renderScreen(<SystemPage />);
    const card = await screen.findByRole("region", { name: "E-posta" });
    expect(within(card).getByText("Geçmiş iletilerin taraması tamamlanmadı")).toBeInTheDocument();
    expect(within(card).getByText(/başlangıç günü: 01\.01\.2024/)).toBeInTheDocument();
  });

  it("asks the service for a backup now", async () => {
    let asked = 0;
    server.use(
      http.post("/api/backups", ({ request }) => {
        asked += request.headers.get("x-iplikci") === "1" ? 1 : 0;
        return HttpResponse.json({ queued: true }, { status: 202 });
      }),
    );
    renderScreen(<SystemPage />);
    await userEvent.click(await screen.findByRole("button", { name: "Şimdi yedek al" }));
    expect(await screen.findByText("Yedek isteği alındı")).toBeInTheDocument();
    expect(asked).toBe(1);
  });

  it("offers to try again when the service cannot be reached", async () => {
    server.use(http.get("/api/system", () => HttpResponse.error()));
    renderScreen(<SystemPage />);
    expect(await screen.findByText("Servise ulaşılamadı; servis çalışıyor mu?")).toBeInTheDocument();
    server.resetHandlers();
    await userEvent.click(screen.getByRole("button", { name: "Yeniden dene" }));
    expect(await screen.findByRole("region", { name: "Servis" })).toBeInTheDocument();
  });

  it("says how to come back in when the session ended", async () => {
    server.use(
      http.get("/api/system", () =>
        HttpResponse.json({ code: "unauthenticated", title: "Oturum açılmamış ya da süresi dolmuş." }, { status: 401 }),
      ),
    );
    renderScreen(<SystemPage />);
    expect(await screen.findByText("Oturum kapandı")).toBeInTheDocument();
    expect(screen.queryByText(/terminal/i)).not.toBeInTheDocument();
  });
});
