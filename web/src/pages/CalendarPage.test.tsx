import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { afterEach, describe, expect, it } from "vitest";

import { FORECAST, server } from "../test/server";
import { renderScreen } from "../test/render";
import CalendarPage from "./CalendarPage";

afterEach(() => localStorage.clear());

describe("CalendarPage", () => {
  it("lists the next sixty days' items by day with their kind, account and amount, each leading on", async () => {
    renderScreen(<CalendarPage />);
    const agenda = await screen.findByRole("region", { name: "Önümüzdeki 60 gün" });
    expect(await within(agenda).findByText(/^15\.11\.2026 – 13\.01\.2027: geçmiş ödemelerden/)).toBeInTheDocument();
    const salary = within(agenda).getByText("Örnek İşveren A.Ş.").closest("tr")!;
    expect(within(salary).getByText("01.12.2026")).toBeInTheDocument();
    expect(within(salary).getByText("Düzenli gelir")).toBeInTheDocument();
    expect(within(salary).getByText("+40.000,00 TL")).toBeInTheDocument();
    expect(within(salary).getByRole("link", { name: "Örnek İşveren A.Ş." })).toHaveAttribute(
      "href",
      "/abonelikler?seri=fp-maas",
    );
    const card = within(agenda).getAllByText("Örnek Kart •1234")[0]!.closest("tr")!;
    expect(within(card).getByText("Kart son ödemesi")).toBeInTheDocument();
    expect(within(card).getByText("asgari 1.800,00 TL")).toBeInTheDocument();
    expect(within(card).getByRole("link", { name: "Örnek Kart •1234" })).toHaveAttribute("href", "/hesaplar/teb-1234");
    const rent = within(agenda).getByText("Ev kirası").closest("tr")!;
    expect(within(rent).getByText("−15.000,00 TL")).toBeInTheDocument();
    expect(within(agenda).getByText("giriş +40.000,00 TL")).toBeInTheDocument();
    expect(within(agenda).getByText("çıkış −24.000,00 TL")).toBeInTheDocument();
    expect(within(agenda).getByText("Tahmin")).toBeInTheDocument();
  });

  it("says in a sentence what the days hold and which comes first", async () => {
    renderScreen(<CalendarPage />);
    const agenda = await screen.findByRole("region", { name: "Önümüzdeki 60 gün" });
    expect(
      await within(agenda).findByText(
        "15.11.2026 – 13.01.2027 arasında 2 ödeme bekleniyor, toplam 24.000,00 TL. 1 gelir bekleniyor, toplam " +
          "40.000,00 TL. İlki 25.11.2026'da: Örnek Kart •1234.",
      ),
    ).toBeInTheDocument();
    expect(within(agenda).getByRole("link", { name: /Düzenli ödemeleri aç/ })).toHaveAttribute("href", "/abonelikler");
  });

  it("says what each item rests on in the detailed view", async () => {
    localStorage.setItem("iplikci.view", "detailed");
    renderScreen(<CalendarPage />);
    const agenda = await screen.findByRole("region", { name: "Önümüzdeki 60 gün" });
    const rent = (await within(agenda).findByText("Ev kirası")).closest("tr")!;
    expect(within(rent).getByText("son ödeme 03.10.2026: 15.000,00 TL")).toBeInTheDocument();
  });

  it("shows each account's forecast as an estimate, with the day it goes below zero and what it assumes", async () => {
    renderScreen(<CalendarPage />);
    const forecast = await screen.findByRole("region", { name: "Nakit akışı öngörüsü" });
    expect(within(forecast).getByText("Tahmin")).toBeInTheDocument();
    const table = await within(forecast).findByRole("table", { name: "Hesap başına bakiye öngörüsü" });
    const account = within(table).getByText("Örnek Vadesiz TL").closest("tr")!;
    expect(within(account).getByText("1.000,00 TL")).toBeInTheDocument();
    expect(within(account).getByText("31.10.2026 dökümü ve 2 hareket")).toBeInTheDocument();
    expect(within(account).getByText("03.12.2026: −14.019,00 TL")).toBeInTheDocument();
    const assumptions = within(forecast).getByRole("region", { name: "Örnek Vadesiz TL varsayımları" });
    expect(within(assumptions).getByText(/^Seri dışı çıkışlar: Nisan 2026 – Eylül 2026/)).toBeInTheDocument();
    expect(within(forecast).getByText("Garanti Vadesiz TL: bakiyesi hiçbir belgede yazmıyor")).toBeInTheDocument();
    expect(within(forecast).getByText(/Örnek Müzik \(Örnek Kart •1234\): −99,99 TL/)).toBeInTheDocument();
  });

  it("says which account goes below zero first and leads to it", async () => {
    renderScreen(<CalendarPage />);
    const forecast = await screen.findByRole("region", { name: "Nakit akışı öngörüsü" });
    expect(
      await within(forecast).findByText("Örnek Vadesiz TL 03.12.2026'da −14.019,00 TL ile eksiye düşüyor."),
    ).toBeInTheDocument();
    const next = within(forecast).getByRole("link", { name: /Hesabı aç/ });
    expect(next).toHaveAttribute("href", "/hesaplar/teb-123456789");
  });

  it("says the lowest balance when no account goes below zero", async () => {
    const [cash] = FORECAST.accounts;
    const lowest = { day: "2026-11-30", balance: { minor: 50000, currency: "TRY" } };
    const above = { ...cash!, negative: null, lowest };
    server.use(http.get("/api/forecast", () => HttpResponse.json({ ...FORECAST, accounts: [above] })));
    renderScreen(<CalendarPage />);
    expect(
      await screen.findByText(
        "Hiçbir hesap eksiye düşmüyor; en düşük bakiye 30.11.2026'da 500,00 TL (Örnek Vadesiz TL).",
      ),
    ).toBeInTheDocument();
    expect(screen.getByText("Eksiye düşmüyor")).toBeInTheDocument();
  });

  it("draws the balances day by day, with every day's balance in the table view", async () => {
    renderScreen(<CalendarPage />);
    const forecast = await screen.findByRole("region", { name: "Nakit akışı öngörüsü" });
    const chart = await within(forecast).findByRole("img", { name: /^Gün gün bakiye öngörüsü: çizgi grafiği/ });
    expect(chart).toBeInTheDocument();
    await userEvent.click(within(forecast).getByRole("tab", { name: "Tablo" }));
    const table = within(forecast).getByRole("table", { name: "Gün gün bakiye öngörüsü" });
    expect(within(table).getAllByRole("row")).toHaveLength(61); // the header and sixty days
    expect(within(table).getByText("13.01.2027").closest("tr")).toHaveTextContent("−14.060,00 TL");
  });

  it("narrows the list to the day the address names, and goes back to every day", async () => {
    const { location } = renderScreen(<CalendarPage />, { path: "/takvim?gun=2026-12-01" });
    const agenda = await screen.findByRole("region", { name: "Önümüzdeki 60 gün" });
    expect(
      await within(agenda).findByText("01.12.2026'da 1 gelir bekleniyor, toplam 40.000,00 TL."),
    ).toBeInTheDocument();
    expect(within(agenda).getByRole("table", { name: "01.12.2026 günü beklenen ödemeler ve gelirler" })).toBeVisible();
    expect(within(agenda).getByText("Örnek İşveren A.Ş.")).toBeInTheDocument();
    expect(within(agenda).queryByText("Ev kirası")).not.toBeInTheDocument();
    await userEvent.click(within(agenda).getByRole("button", { name: "Bütün günleri göster" }));
    expect(location()).toBe("/takvim");
    expect(within(agenda).getByText("Ev kirası")).toBeInTheDocument();
  });

  it("says when the day the address names holds nothing expected", async () => {
    renderScreen(<CalendarPage />, { path: "/takvim?gun=2026-11-20" });
    const agenda = await screen.findByRole("region", { name: "Önümüzdeki 60 gün" });
    expect(
      await within(agenda).findByText("20.11.2026'da beklenen bir ödeme ya da gelir yok."),
    ).toBeInTheDocument();
    expect(within(agenda).queryByRole("table")).not.toBeInTheDocument();
  });

  it("leads from a day of the forecast to what the list above expects on it", async () => {
    const { location } = renderScreen(<CalendarPage />, { path: "/takvim" });
    const forecast = await screen.findByRole("region", { name: "Nakit akışı öngörüsü" });
    await within(forecast).findByRole("img", { name: /^Gün gün bakiye öngörüsü: çizgi grafiği/ });
    expect(
      within(forecast).getByText("Bir güne tıklayın: o gün beklenenler yukarıdaki listede gösterilir."),
    ).toBeInTheDocument();
    await userEvent.click(within(forecast).getByRole("tab", { name: "Tablo" }));
    await userEvent.click(within(forecast).getByRole("link", { name: "25.11.2026" }));
    expect(location()).toBe("/takvim?gun=2026-11-25");
    const agenda = screen.getByRole("region", { name: "Önümüzdeki 60 gün" });
    expect(await within(agenda).findByText(/^25\.11\.2026'da 1 ödeme bekleniyor/)).toBeInTheDocument();
  });

  it("says when nothing is expected and no account has a balance known", async () => {
    server.use(
      http.get("/api/calendar", () => HttpResponse.json({ today: "2026-11-15", end: "2027-01-13", items: [] })),
      http.get("/api/forecast", () =>
        HttpResponse.json({ ...FORECAST, accounts: [], elsewhere: [], notes: [], skipped: FORECAST.skipped }),
      ),
    );
    renderScreen(<CalendarPage />);
    expect(await screen.findByText("Bu günlerde beklenen ödeme ya da gelir yok")).toBeInTheDocument();
    expect(await screen.findByText("Öngörü için bakiyesi bilinen TL hesabı yok")).toBeInTheDocument();
    expect(screen.getByText("Garanti Vadesiz TL: bakiyesi hiçbir belgede yazmıyor")).toBeInTheDocument();
  });

  it("offers to try again in the part that failed and shows the other", async () => {
    server.use(
      http.get("/api/calendar", () =>
        HttpResponse.json({ code: "internal", title: "Beklenmeyen bir hata oldu." }, { status: 500 }),
      ),
    );
    renderScreen(<CalendarPage />);
    const agenda = await screen.findByRole("region", { name: "Önümüzdeki 60 gün" });
    expect(await within(agenda).findByText("Beklenmeyen bir hata oldu.")).toBeInTheDocument();
    expect(within(agenda).getByRole("button", { name: "Yeniden dene" })).toBeInTheDocument();
    const forecast = screen.getByRole("region", { name: "Nakit akışı öngörüsü" });
    expect((await within(forecast).findAllByText("Örnek Vadesiz TL")).length).toBeGreaterThan(0);
  });
});
