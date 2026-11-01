import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import { server } from "../test/server";
import { renderScreen } from "../test/render";
import SubscriptionsPage from "./SubscriptionsPage";

describe("SubscriptionsPage", () => {
  it("lists the monthly payments with their status, amount, next payment and price change", async () => {
    renderScreen(<SubscriptionsPage />);
    const monthly = await screen.findByRole("region", { name: "Aylık ödemeler" });
    const rent = within(monthly).getByText("Ev kirası").closest("tr")!;
    expect(within(rent).getByText("Devam ediyor")).toBeInTheDocument();
    expect(within(rent).getAllByText("15.000,00 TL").length).toBeGreaterThan(0);
    expect(within(rent).getByText("03.11.2026")).toBeInTheDocument();
    expect(within(rent).getByText("14.000,00 TL → 15.000,00 TL")).toBeInTheDocument();
    expect(within(rent).getByText("Temmuz 2026")).toBeInTheDocument();
    expect(within(monthly).getByText("Örnek Müzik")).toBeInTheDocument();
    expect(
      screen.getByText("Durumlar 31.10.2026 tarihli son ekstreye göre; pencere Nisan 2026 – Eylül 2026 arasındaki 6 tam ay."),
    ).toBeInTheDocument();
  });

  it("shows the periodic payments per period, apart from the monthly ones", async () => {
    renderScreen(<SubscriptionsPage />);
    const periodic = await screen.findByRole("region", { name: "Dönemsel ödemeler" });
    const insurance = within(periodic).getByText("Örnek Sigorta").closest("tr")!;
    expect(within(insurance).getByText("Yılda bir")).toBeInTheDocument();
    expect(within(insurance).getAllByText("4.800,00 TL").length).toBeGreaterThan(0);
    expect(within(insurance).getByText("08.01.2027")).toBeInTheDocument();
    expect(within(screen.getByRole("region", { name: "Aylık ödemeler" })).queryByText("Örnek Sigorta")).toBeNull();
  });

  it("keeps what ended apart, with what its status means, and leaves out what is not listed", async () => {
    renderScreen(<SubscriptionsPage />);
    const ended = await screen.findByRole("region", { name: "Biten ve iptal edilenler" });
    const water = within(ended).getByText("Su faturası").closest("tr")!;
    expect(within(water).getByText("Bitti")).toBeInTheDocument();
    expect(within(water).getByText(/Belgelerde yok/)).toBeInTheDocument();
    expect(screen.queryByText("Eski Dergi")).toBeNull();
  });

  it("shows the regular income and the installments left", async () => {
    renderScreen(<SubscriptionsPage />);
    const income = await screen.findByRole("region", { name: "Düzenli gelirler" });
    const salary = within(income).getByText("Örnek İşveren A.Ş.").closest("tr")!;
    expect(within(salary).getByText("40.000,00 TL")).toBeInTheDocument();
    const installments = screen.getByRole("region", { name: "Taksitli alışverişler" });
    const purchase = within(installments).getByText("Örnek Elektronik").closest("tr")!;
    expect(within(purchase).getByText("8/12")).toBeInTheDocument();
    expect(within(purchase).getByText("2.000,00 TL")).toBeInTheDocument();
    expect(within(purchase).getByText("4 taksit")).toBeInTheDocument();
    expect(within(purchase).getByText("Şubat 2027")).toBeInTheDocument();
  });

  it("opens the rows behind a series, a provisional one marked", async () => {
    renderScreen(<SubscriptionsPage />);
    const monthly = await screen.findByRole("region", { name: "Aylık ödemeler" });
    const rent = within(monthly).getByText("Ev kirası").closest("tr")!;
    await userEvent.click(within(rent).getByText("2 ödeme"));
    expect(within(rent).getByText(/TEB Dekont 03\.11\.2026\.pdf/)).toBeVisible();
    expect(within(rent).getByText("Geçici")).toBeInTheDocument();
  });

  it("says when no series is known yet", async () => {
    server.use(
      http.get("/api/subscriptions", () =>
        HttpResponse.json({ window: [], as_of: "2026-11-01", series: [], income: [], installments: [] }),
      ),
    );
    renderScreen(<SubscriptionsPage />);
    expect(await screen.findByText("Henüz düzenli ödeme bulunmadı")).toBeInTheDocument();
  });

  it("offers to try again when the service fails", async () => {
    server.use(
      http.get("/api/subscriptions", () =>
        HttpResponse.json({ code: "busy", title: "Başka bir işlem belgeleri işliyor." }, { status: 503 }),
      ),
    );
    renderScreen(<SubscriptionsPage />);
    expect(await screen.findByText("Başka bir işlem belgeleri işliyor.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Yeniden dene" })).toBeInTheDocument();
  });
});
