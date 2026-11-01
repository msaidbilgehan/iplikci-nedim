import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import { FORECAST, server } from "../test/server";
import { renderScreen } from "../test/render";
import CalendarPage from "./CalendarPage";

describe("CalendarPage", () => {
  it("lists the next sixty days' items by day with their kind, account, amount and basis", async () => {
    renderScreen(<CalendarPage />);
    const agenda = await screen.findByRole("region", { name: "Önümüzdeki 60 gün" });
    expect(await within(agenda).findByText(/^15\.11\.2026 – 13\.01\.2027/)).toBeInTheDocument();
    const salary = within(agenda).getByText("Örnek İşveren A.Ş.").closest("tr")!;
    expect(within(salary).getByText("01.12.2026")).toBeInTheDocument();
    expect(within(salary).getByText("Düzenli gelir")).toBeInTheDocument();
    expect(within(salary).getByText("+40.000,00 TL")).toBeInTheDocument();
    const card = within(agenda).getAllByText("Örnek Kart •1234")[0]!.closest("tr")!;
    expect(within(card).getByText("Kart son ödemesi")).toBeInTheDocument();
    expect(within(card).getByText("asgari 1.800,00 TL")).toBeInTheDocument();
    const rent = within(agenda).getByText("Ev kirası").closest("tr")!;
    expect(within(rent).getByText("−15.000,00 TL")).toBeInTheDocument();
    expect(within(rent).getByText("son ödeme 03.10.2026: 15.000,00 TL")).toBeInTheDocument();
    expect(within(agenda).getByText("giriş +40.000,00 TL")).toBeInTheDocument();
    expect(within(agenda).getByText("çıkış −24.000,00 TL")).toBeInTheDocument();
    expect(within(agenda).getByText("Tahmin")).toBeInTheDocument();
  });

  it("shows each account's forecast as an estimate, with the day it goes below zero and what it assumes", async () => {
    renderScreen(<CalendarPage />);
    const forecast = await screen.findByRole("region", { name: "Nakit akışı öngörüsü" });
    expect(within(forecast).getByText("Tahmin")).toBeInTheDocument();
    const account = (await within(forecast).findAllByText("Örnek Vadesiz TL"))[0]!.closest("tr")!;
    expect(within(account).getByText("1.000,00 TL")).toBeInTheDocument();
    expect(within(account).getByText("31.10.2026 dökümü ve 2 hareket")).toBeInTheDocument();
    expect(within(account).getByText("03.12.2026: −14.019,00 TL")).toBeInTheDocument();
    const assumptions = within(forecast).getByRole("region", { name: "Örnek Vadesiz TL varsayımları" });
    expect(within(assumptions).getByText(/^Seri dışı çıkışlar: Nisan 2026 – Eylül 2026/)).toBeInTheDocument();
    expect(within(forecast).getByText("Garanti Vadesiz TL: bakiyesi hiçbir belgede yazmıyor")).toBeInTheDocument();
    expect(within(forecast).getByText(/Örnek Müzik \(Örnek Kart •1234\): −99,99 TL/)).toBeInTheDocument();
  });

  it("shows the balances day by day as a table", async () => {
    renderScreen(<CalendarPage />);
    const forecast = await screen.findByRole("region", { name: "Nakit akışı öngörüsü" });
    await userEvent.click(await within(forecast).findByText("Gün gün bakiyeler"));
    const table = within(forecast).getByRole("table", { name: "Her günün sonundaki tahmini bakiye, hesap başına" });
    expect(within(table).getAllByRole("row")).toHaveLength(61); // the header and sixty days
    expect(within(table).getByText("13.01.2027").closest("tr")).toHaveTextContent("−14.060,00 TL");
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
