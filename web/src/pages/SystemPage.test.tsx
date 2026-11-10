import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import { server, systemStatus, UPDATE_FOUND } from "../test/server";
import { renderScreen } from "../test/render";
import SystemPage from "./SystemPage";

describe("SystemPage", () => {
  it("says whether a newer version is out and leads to where updates are set", async () => {
    renderScreen(<SystemPage />);
    const card = await screen.findByRole("region", { name: "Servis" });
    expect(await within(card).findByText("Güncel")).toBeInTheDocument();
    expect(within(card).getByRole("link", { name: "Ayarlar'da" })).toHaveAttribute("href", "/ayarlar");
  });

  it("names the newer version the last check found", async () => {
    server.use(http.get("/api/update", () => HttpResponse.json(UPDATE_FOUND)));
    renderScreen(<SystemPage />);
    const card = await screen.findByRole("region", { name: "Servis" });
    expect(await within(card).findByText("Yeni sürüm hazır: 0.11.0")).toBeInTheDocument();
  });

  it("offers the exports the last analysis wrote, each to download, and makes them again on request", async () => {
    const user = userEvent.setup();
    let asked = 0;
    server.use(
      http.post("/api/exports", () => {
        asked += 1;
        return HttpResponse.json({ queued: true }, { status: 202 });
      }),
    );
    renderScreen(<SystemPage />);
    const card = await screen.findByRole("region", { name: "Dışa aktarımlar" });
    const report = await within(card).findByRole("link", { name: "İndir: Rapor (tek dosya, HTML)" });
    expect(report).toHaveAttribute("href", "/api/exports/report");
    expect(within(card).getByRole("link", { name: "İndir: İşlemler (Excel)" })).toHaveAttribute(
      "href",
      "/api/exports/xlsx",
    );
    expect(within(card).queryByText("Ay sonu sayfaları (zip)")).not.toBeInTheDocument(); // not written yet
    await user.click(within(card).getByRole("button", { name: "Yeniden yaz" }));
    expect(await within(card).findByText("İstek alındı")).toBeInTheDocument();
    expect(asked).toBe(1);
  });

  it("says when nothing was exported yet, and offers the log without personal values", async () => {
    server.use(http.get("/api/exports", () => HttpResponse.json([])));
    renderScreen(<SystemPage />);
    const card = await screen.findByRole("region", { name: "Dışa aktarımlar" });
    expect(await within(card).findByText(/Henüz dışa aktarım yok/)).toBeInTheDocument();
    const service = screen.getByRole("region", { name: "Servis" });
    expect(within(service).getByRole("link", { name: "Günlüğü indir" })).toHaveAttribute("href", "/api/system/log");
  });

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

  it("says no e-mail way is set up when the default IMAP account never was, and leads to Ayarlar", async () => {
    const mail = { ...systemStatus().mail, configured: false, last_run: "" };
    server.use(http.get("/api/system", () => HttpResponse.json(systemStatus({ mail }))));
    renderScreen(<SystemPage />);
    const card = await screen.findByRole("region", { name: "E-posta" });
    expect(within(card).getByText("Henüz kurulmadı")).toBeInTheDocument();
    expect(within(card).queryByText("IMAP")).not.toBeInTheDocument();
    expect(within(card).getByRole("link", { name: "E-postayı Ayarlar'da kurun" })).toHaveAttribute("href", "/ayarlar");
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

  it("lists the non-bank senders, saying only verified senders are taken and the history is read again", async () => {
    renderScreen(<SystemPage />);
    const card = await screen.findByRole("region", { name: "Banka dışı göndericiler" });
    const listed = await within(card).findByRole("list", { name: "Banka dışı gönderici alan adları" });
    expect(within(listed).getAllByRole("listitem").map((item) => item.querySelector("code")?.textContent)).toEqual([
      "ornekcell.example",
      "fatura.example",
    ]);
    const about = within(card).getByText(/^Fatura, abonelik ve alışveriş e-postalarının geldiği alan adları/);
    expect(about).toHaveTextContent("Yalnızca göndereni doğrulanan (DMARC denetiminden geçen) e-postalar alınır");
    expect(about).toHaveTextContent("Liste değişince tarayıcı eklentisi geçmiş e-postaları yeniden okur.");
  });

  it("adds a sender from the service's own page and shows the list the service saved", async () => {
    let sent: unknown;
    let fromOwnPage = false;
    server.use(
      http.put("/api/settings/mail/other-senders", async ({ request }) => {
        sent = await request.json();
        fromOwnPage = request.headers.get("x-iplikci") === "1";
        return HttpResponse.json({ domains: ["ornekcell.example", "fatura.example", "magaza.example"] });
      }),
    );
    renderScreen(<SystemPage />);
    const card = await screen.findByRole("region", { name: "Banka dışı göndericiler" });
    const field = await within(card).findByLabelText("Alan adı");
    await userEvent.type(field, " magaza.example {Enter}");
    expect(await within(card).findByText("magaza.example")).toBeInTheDocument();
    expect(sent).toEqual({ domains: ["ornekcell.example", "fatura.example", "magaza.example"] });
    expect(fromOwnPage).toBe(true);
    expect(field).toHaveValue("");
    expect(within(card).getByText("Liste kaydedildi")).toBeInTheDocument();
  });

  it("removes a sender", async () => {
    let sent: unknown;
    server.use(
      http.put("/api/settings/mail/other-senders", async ({ request }) => {
        sent = await request.json();
        return HttpResponse.json({ domains: ["fatura.example"] });
      }),
    );
    renderScreen(<SystemPage />);
    const card = await screen.findByRole("region", { name: "Banka dışı göndericiler" });
    await userEvent.click(await within(card).findByRole("button", { name: "ornekcell.example alan adını kaldır" }));
    await waitFor(() => expect(within(card).queryByText("ornekcell.example")).toBeNull());
    expect(sent).toEqual({ domains: ["fatura.example"] });
    expect(within(card).getByText("fatura.example")).toBeInTheDocument();
  });

  it("shows why the service refused a sender and keeps what was typed", async () => {
    const why = "garantibbva.com.tr bir bankanın alan adı; bankaların e-postaları zaten alınıyor.";
    server.use(
      http.put("/api/settings/mail/other-senders", () =>
        HttpResponse.json({ code: "sender_invalid", title: why }, { status: 400 }),
      ),
    );
    renderScreen(<SystemPage />);
    const card = await screen.findByRole("region", { name: "Banka dışı göndericiler" });
    const field = await within(card).findByLabelText("Alan adı");
    await userEvent.type(field, "garantibbva.com.tr");
    await userEvent.click(within(card).getByRole("button", { name: "Ekle" }));
    expect(await within(card).findByText(why)).toBeInTheDocument();
    expect(within(card).getByText("Liste kaydedilemedi")).toBeInTheDocument();
    expect(field).toHaveValue("garantibbva.com.tr");
    expect(field).toHaveAttribute("aria-invalid", "true");
    expect(field).toHaveAccessibleDescription(expect.stringContaining(why));
    await userEvent.type(field, "x"); // typing again clears the refusal
    expect(within(card).queryByText(why)).toBeNull();
  });

  it("says when no non-bank sender is set and adds nothing empty", async () => {
    server.use(http.get("/api/settings/mail/other-senders", () => HttpResponse.json({ domains: [] })));
    renderScreen(<SystemPage />);
    const card = await screen.findByRole("region", { name: "Banka dışı göndericiler" });
    expect(await within(card).findByText("Henüz banka dışı gönderici yok.")).toBeInTheDocument();
    expect(within(card).getByRole("button", { name: "Ekle" })).toBeDisabled();
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

  it("shows where the exchange rates stand: the providers, the newest bulletin, the days kept and missing", async () => {
    renderScreen(<SystemPage />);
    const card = await screen.findByRole("region", { name: "Döviz kurları" });
    expect(within(card).getByText("TCMB, Frankfurter (ECB)")).toBeInTheDocument();
    expect(within(card).getByText("TCMB son kuru")).toBeInTheDocument();
    expect(within(card).getByText("30.10.2026 · 210 günün kuru")).toBeInTheDocument();
    expect(within(card).getByText("210 gün, 02.01.2026 gününden bu yana")).toBeInTheDocument();
    expect(within(card).getByText("4 iş günü")).toBeInTheDocument();
  });

  it("asks the service for the day's rates, and for the missing days of the history", async () => {
    const asked: unknown[] = [];
    server.use(
      http.post("/api/fx/fetch", async ({ request }) => {
        asked.push(await request.json());
        return HttpResponse.json({ queued: true }, { status: 202 });
      }),
    );
    renderScreen(<SystemPage />);
    const card = await screen.findByRole("region", { name: "Döviz kurları" });
    await userEvent.click(within(card).getByRole("button", { name: "Kurları şimdi al" }));
    expect(await within(card).findByText("Kur isteği alındı")).toBeInTheDocument();
    await userEvent.click(within(card).getByRole("button", { name: "Eksik günlerin kurlarını al" }));
    await waitFor(() => expect(asked).toEqual([{ history: false }, { history: true }]));
  });

  it("says the rates are not fetched while the settings name no provider, and offers no fetch", async () => {
    const rates = { ...systemStatus().rates!, providers: [], missing: 0, last_run: "" };
    server.use(http.get("/api/system", () => HttpResponse.json(systemStatus({ rates }))));
    renderScreen(<SystemPage />);
    const card = await screen.findByRole("region", { name: "Döviz kurları" });
    expect(within(card).getByText(/Ayarlarda kur sağlayıcısı yok/)).toBeInTheDocument();
    expect(within(card).queryByRole("button", { name: "Kurları şimdi al" })).not.toBeInTheDocument();
  });

  it("says why the last fetch failed and that the documents' rates stand in meanwhile", async () => {
    const rates = { ...systemStatus().rates!, last_error: "TCMB: bağlantı kurulamadı" };
    server.use(http.get("/api/system", () => HttpResponse.json(systemStatus({ rates }))));
    renderScreen(<SystemPage />);
    const card = await screen.findByRole("region", { name: "Döviz kurları" });
    expect(within(card).getByText("Son denemede kurlar alınamadı")).toBeInTheDocument();
    expect(within(card).getByText("TCMB: bağlantı kurulamadı")).toBeInTheDocument();
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
