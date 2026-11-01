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

  it("says a refused login stopped the mail and is never tried again", async () => {
    const stopped = systemStatus({
      mail: { connector: "imap", configured: true, last_run: "", last_error: "giriş reddedildi", stopped: true },
    });
    server.use(http.get("/api/system", () => HttpResponse.json(stopped)));
    renderScreen(<SystemPage />);
    expect(await screen.findByText("Giriş reddedildi; e-posta alımı durdu")).toBeInTheDocument();
    expect(screen.getByText("Durdu")).toBeInTheDocument();
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
